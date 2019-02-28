from .base import BaseConfig as Config
from .test import TestConfig  # noqa: F401

try:
    from .local import LocalConfig as Config  # noqa: F811,F401
except ImportError:
    pass
