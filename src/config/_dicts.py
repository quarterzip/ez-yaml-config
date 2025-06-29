from collections.abc import Mapping
from typing import Any, Literal


def traverse_nested_dict_with_delimited_key(
    dict_: dict,
    key: str,
    delimiter: str = ".",
    raise_or_default: Literal["raise", "default"] = "default",
) -> Any:
    for sub_key in key.split(delimiter):
        dict_ = dict_.get(sub_key, {}) if raise_or_default == "default" else dict_[sub_key]
    return dict_


def inflate_nested_dict(flattened_dict: dict[str, Any], base_key: str = "__base__") -> dict:
    result = {}
    for key_string, value in flattened_dict.items():
        parts = key_string.split(".")
        current_level = result

        for part in parts[:-1]:
            if part not in current_level:
                current_level[part] = {}
            elif not isinstance(current_level[part], Mapping):
                existing_value = current_level[part]
                current_level[part] = {base_key: existing_value}
            current_level = current_level[part]

        final_key = parts[-1]

        if final_key in current_level and isinstance(current_level[final_key], Mapping):
            current_level[final_key][base_key] = value
        else:
            current_level[final_key] = value

    return result
