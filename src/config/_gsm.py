import logging
from contextvars import ContextVar
from functools import cache, lru_cache

from google.cloud.secretmanager import SecretManagerServiceClient
from google_crc32c import Checksum
from pydantic import PlainValidator

_logger = logging.getLogger(__name__)


@cache
def get_gsm_client():
    return SecretManagerServiceClient()

def get_secret_value(project: str, secret_name: str) -> str:
    """
    Gets a secret from GSM, for the configured data project
    """
    secret_name = f"projects/{project}/secrets/{secret_name}/versions/latest"

    _logger.debug("Getting GSM secret %s", secret_name)
    response = get_gsm_client().access_secret_version(request={"name": secret_name})

    crc32c = Checksum()
    crc32c.update(response.payload.data)
    if response.payload.data_crc32c != int(crc32c.hexdigest(), 16):
        raise ValueError("Checksum did not match when attempted to fetch a secret")

    return response.payload.data.decode()

_fetch_secrets = ContextVar(f"{__name__}_fetch_secrets", default=True)

def gsm_secret(project: str, match_prefix: str | None = "gsm:", static_key: str | None = None):
    """
    This can be used to annotate fields on a `Configuration` in order to fetch their value from a secret in Google Secrets Manager (GSM).

    By default, if the annotated field has a value that is prefixed with "gsm:", the remainder of the value in the config file
    will be interpreted as the key to fetch from GSM. This prefix may be adjusted with the `match_prefix` parameter. If the value
    in the config file does not match the prefix its value will be unchanged by this annotation, unless `static_key` is set.

    If `static_key` is set, it will always be used as the key to fetch from GSM, regardless of what is in the config file.

    Use this by annotating the configuration field with `Annotated[str, gsm_secret(<gsm_project_id>)]`
    """

    @lru_cache
    def _possible_gsm_key(value: str) -> str:
        if not _fetch_secrets.get():
            return value
        if static_key is not None:
            return get_secret_value(project, static_key)
        if match_prefix is not None and value.startswith(match_prefix):
            return get_secret_value(project, value.replace(match_prefix, "", 1))

        # Else return value unchanged:
        return value

    return PlainValidator(_possible_gsm_key)
