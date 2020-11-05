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
            """
            Emit a record.

            Args:
                self: (todo): write your description
                record: (todo): write your description
            """
            pass

logging.getLogger(__name__).addHandler(NullHandler())
