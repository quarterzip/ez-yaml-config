import logging
from abc import ABC
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import ClassVar, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    create_model,
)

from config._dicts import inflate_nested_dict, traverse_nested_dict_with_delimited_key
from config._errors import ConfigSetupError, ConfigurationError
from config._gsm import _fetch_secrets
from config._yaml import load_config

_logger = logging.getLogger(__name__)

_configs: list[type["Configuration"]] = []


def _create_model_from_schema(
    model_name: str,
    schema_dict: dict[str, Mapping | type["Configuration"]],
    __config__: ConfigDict | None = None,
) -> type[BaseModel]:
    """
    Recursively creates a Pydantic model class from a schema dictionary.
    """
    fields = {}
    for key, nested_cls in schema_dict.items():
        if isinstance(nested_cls, Mapping):
            sub_model_name = f"{model_name}_{key.capitalize()}"
            intermediate_cls = _create_model_from_schema(sub_model_name, nested_cls)
            fields[key] = (intermediate_cls, Field(default_factory=intermediate_cls))
        else:
            assert issubclass(nested_cls, Configuration)
            fields[key] = nested_cls if key == "__base__" else (nested_cls, Field(default_factory=nested_cls))

    return create_model(model_name, **fields, __config__=__config__)


def validate_config_file(file: str, fetch_secrets: bool = False) -> BaseModel:
    all_sections = {c.CONFIG_SECTION: c for c in _configs if c.CONFIG_FILE == file}
    path_env_var = {c.CONFIG_FILE_PATH_ENV_VAR for c in all_sections.values()}

    if not all_sections:
        raise ConfigurationError(f"No Configurations found for '{file}'")
    if len(path_env_var) > 1:
        raise ConfigSetupError(f"Different 'CONFIG_FILE_PATH_ENV_VAR' values found for Configuration '{file}'")

    all_sections = {k: create_model(f"{v.__name__}", __base__=v) for k, v in all_sections.items()}
    for cls in all_sections.values():
        cls._warn_instantiation = False

    root_modal = all_sections.pop("", None)
    if root_modal:
        all_sections["__base__"] = root_modal

    DynamicModel = _create_model_from_schema(
        f"_CombinedConfig_{file.capitalize()}",
        schema_dict=inflate_nested_dict(all_sections),
        __config__=ConfigDict(extra="forbid"),
    )
    try:
        DynamicModel._warn_instantiation = False
    except AttributeError:
        pass

    _fetch_secrets.set(fetch_secrets)
    config = load_config(config_filename=file, env_var_for_changing_path=path_env_var.pop())
    validated_config = DynamicModel(**config)
    _fetch_secrets.set(False)
    return validated_config


class Configuration(BaseModel, ABC):
    CONFIG_FILE: ClassVar[str] = None
    CONFIG_SECTION: ClassVar[str] = ""
    CONFIG_FILE_PATH_ENV_VAR: ClassVar[str] = None
    """The Environment Variable which may contain the path to the config file"""

    class Default:
        pass

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._nested_overrides = []
        cls._warn_instantiation = True
        _configs.append(cls)

    def __init__(self, **kwargs):
        if self._warn_instantiation:
            _logger.warning(
                f"Instantiated {type(self).__name__} directly, "
                 "you probably want to use .get() classmethod to get the configured values instead"
            )
        super().__init__(**kwargs)

    @classmethod
    def get(cls) -> Self:
        if cls.CONFIG_FILE is None:
            raise ValueError(f"CONFIG_FILE attribute is missing from {cls.__name__}")

        if cls.CONFIG_SECTION is None:
            raise ValueError(f"CONFIG_SECTION attribute is missing from {cls.__name__}")

        config = load_config(config_filename=cls.CONFIG_FILE, env_var_for_changing_path=cls.CONFIG_FILE_PATH_ENV_VAR)
        section = traverse_nested_dict_with_delimited_key(config, cls.CONFIG_SECTION, ".")
        assert isinstance(section, dict)

        for override in cls._nested_overrides:
            section.update(**{k: v for k, v in override.items() if v is not Configuration.Default})
            for reset_to_default in [k for k, v in override.items() if v is Configuration.Default]:
                section.pop(reset_to_default, None)

        try:
            cls._warn_instantiation = False
            return cls(**section)
        finally:
            cls._warn_instantiation = True

    @classmethod
    def section_exists(cls) -> bool:
        try:
            config = load_config(
                config_filename=cls.CONFIG_FILE, env_var_for_changing_path=cls.CONFIG_FILE_PATH_ENV_VAR
            )
            traverse_nested_dict_with_delimited_key(config, cls.CONFIG_SECTION, ".", "raise")
        except KeyError:
            return False
        return True

    @classmethod
    @contextmanager
    def override(cls, **override_values) -> Iterator[None]:
        # Run the override_values through the underlying BaseModel class to ensure that the overrides match actual properties
        # This also raises errors if properties are missing, so we explicitly catch and ignore those
        try:
            cls._warn_instantiation = False
            non_default_values = {k: v for k, v in override_values.items() if v is not Configuration.Default}
            cls(**non_default_values)
        except ValidationError as ve:
            for er in ve.errors():
                if er["type"] == "missing":
                    pass
                else:
                    raise ve
        finally:
            cls._warn_instantiation = True
        cls._nested_overrides.append(override_values)
        yield
        cls._nested_overrides.pop()

