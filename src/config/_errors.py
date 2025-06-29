class EZConfigError(Exception):
    """A known error state of ez-config"""

class ConfigurationError(EZConfigError):
    pass

class ConfigSetupError(EZConfigError):
    pass