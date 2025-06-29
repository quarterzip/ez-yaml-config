import os
from functools import lru_cache

import yaml

from config._errors import ConfigurationError


@lru_cache
def _load_yaml_as_dict(filename: str) -> dict:
    try:
        with open(filename) as config_file:
            loaded = yaml.safe_load(config_file)
    except FileNotFoundError:
        raise ConfigurationError(f"Could not find config file at: {filename}")
    except yaml.YAMLError:
        raise ConfigurationError(f"Config file is not valid yaml: {filename}")
    if not isinstance(loaded, dict):
        raise ConfigurationError(f"Config file is not valid config: {loaded}")
    return loaded


def load_config(config_filename: str, env_var_for_changing_path: str | None = None) -> dict:
    if env_var_for_changing_path:
        config_filename = os.environ.get(env_var_for_changing_path, config_filename)
    return _load_yaml_as_dict(filename=config_filename)