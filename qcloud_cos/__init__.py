from .cos_client import CosS3Client
from .cos_client import CosConfig
from .cos_exception import CosServiceError
from .cos_exception import CosClientError
from .cos_auth import CosS3Auth
from .cos_comm import get_date

import logging

try:
    from logging import NullHandler
except ImportError:
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass

__version__ = '5.1.6.2'
logging.getLogger(__name__).addHandler(NullHandler())
