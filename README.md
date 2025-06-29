Install with `pip install ez-yaml-config`

Then define some configuration files like so:
```python
from config import Configuration, gsm_secret

class ConfigBase(Configuration):
    CONFIG_FILE = "settings.yaml"
    CONFIG_FILE_PATH_ENV_VAR = "SETTINGS_PATH"


class LoggingConfig(ConfigBase):
    CONFIG_SECTION = "logging"
    level: Literal["info", "warning", "error"]


class BackendConfig(ConfigBase):
    CONFIG_SECTION = "server"
    host: str
    api_key: Annotated[str, gsm_secret(project="my-gcp-project")]
```

The above Configurations will load a file named `settings.yaml` in the cwd, or from the location set in the `SETTINGS_PATH` environment variable (if its been set). The file should look like this:
```yaml
logging:
    level: info
server:
    host: "localhost"
    api_key: gsm:name-of-gsm-key
```