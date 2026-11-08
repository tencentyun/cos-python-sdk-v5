# -*- coding: utf-8 -*-
"""
Role-based credential provider for COS SDK.

Fetches temporary credentials (SecretId / SecretKey / Token) via the
qcloud-python-sts SDK using role authorization (AssumeRole), and
automatically refreshes them before they expire.

Usage::

    import os
    from qcloud_cos import CosConfig, CosS3Client, RoleCredentialProvider

    provider = RoleCredentialProvider(
        SecretId=os.getenv('COS_SECRET_ID'),
        SecretKey=os.getenv('COS_SECRET_KEY'),
        RoleArn='qcs::cam::uin/100000000001:roleName/COS_Access_Role',
        DurationSeconds=1800,
        Region='ap-guangzhou',
    )
    config = CosConfig(Region='ap-guangzhou', CredentialInstance=provider)
    client = CosS3Client(config)
"""

import logging
import threading
import time

logger = logging.getLogger(__name__)

# Advance refresh window: refresh the credential this many seconds before it
# actually expires so that in-flight requests are never rejected.
_DEFAULT_REFRESH_BEFORE = 300  # 5 minutes


class RoleCredentialProvider(object):
    """Obtain and auto-refresh temporary credentials via the COS STS SDK.

    The provider uses role authorization (``AssumeRole``) to obtain a
    temporary ``SecretId`` / ``SecretKey`` / ``Token`` triple.  It exposes
    the ``secret_id``, ``secret_key``, and ``token`` attributes expected by
    :class:`~qcloud_cos.CosConfig` when passed as ``CredentialInstance``.

    :param SecretId(str):           Permanent SecretId of the caller.
    :param SecretKey(str):          Permanent SecretKey of the caller.
    :param RoleArn(str):            ARN of the role to assume, e.g.
                                    ``qcs::cam::uin/100000000001:roleName/MyRole``.
    :param DurationSeconds(int):    Lifetime of the temporary credential in
                                    seconds (60–43200, default 1800).
    :param Region(str):             STS service region, e.g. ``ap-guangzhou``.
    :param Policy(dict):            Optional inline policy to further restrict
                                    the permissions of the temporary credential.
    :param Proxy(str):              Optional HTTP proxy URL.
    :param RefreshBefore(int):      Seconds before expiry to proactively
                                    refresh the credential (default 300).
    :param URL(str):                Optional custom STS request URL.
    """

    def __init__(
        self,
        SecretId,
        SecretKey,
        RoleArn,
        DurationSeconds=1800,
        Region='ap-guangzhou',
        Policy=None,
        Proxy=None,
        RefreshBefore=_DEFAULT_REFRESH_BEFORE,
        URL=None,
    ):
        try:
            from sts.sts import Sts  # noqa: F401 – validate import early
        except ImportError:
            raise ImportError(
                'qcloud-python-sts is required for RoleCredentialProvider. '
                'Install it with: pip install -U qcloud-python-sts'
            )

        self._secret_id = SecretId
        self._secret_key = SecretKey
        self._role_arn = RoleArn
        self._duration_seconds = DurationSeconds
        self._region = Region
        self._policy = Policy
        self._proxy = Proxy
        self._refresh_before = RefreshBefore
        self._url = URL

        # Cached credential fields (thread-safe via _lock).
        self._lock = threading.Lock()
        self._tmp_secret_id = None
        self._tmp_secret_key = None
        self._tmp_token = None
        self._expired_time = 0  # unix timestamp

    # ------------------------------------------------------------------
    # CredentialInstance interface expected by CosConfig / CosS3Auth
    # ------------------------------------------------------------------

    @property
    def secret_id(self):
        """Return a valid temporary SecretId, refreshing if necessary."""
        self._ensure_fresh()
        return self._tmp_secret_id

    @property
    def secret_key(self):
        """Return a valid temporary SecretKey, refreshing if necessary."""
        self._ensure_fresh()
        return self._tmp_secret_key

    @property
    def token(self):
        """Return a valid temporary Token, refreshing if necessary."""
        self._ensure_fresh()
        return self._tmp_token

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_expired(self):
        """Return True if the cached credential needs to be refreshed."""
        return time.time() >= self._expired_time - self._refresh_before

    def _ensure_fresh(self):
        """Refresh the credential if it is absent or about to expire."""
        if not self._is_expired():
            return
        with self._lock:
            # Double-checked locking: another thread may have refreshed already.
            if not self._is_expired():
                return
            self._refresh()

    def _refresh(self):
        """Call the STS SDK to obtain a new temporary credential."""
        from sts.sts import Sts

        # When policy is None the STS SDK's parse_parameters() requires bucket
        # to be set (legacy validation).  For role authorization the permissions
        # are governed by the CAM role itself, so we pass a permissive policy
        # that does not restrict anything, which also skips the bucket check.
        default_policy = {
            'version': '2.0',
            'statement': [{'action': '*', 'effect': 'allow', 'resource': '*'}],
        }
        sts_config = {
            'secret_id': self._secret_id,
            'secret_key': self._secret_key,
            'duration_seconds': self._duration_seconds,
            'region': self._region,
            'policy': self._policy if self._policy is not None else default_policy,
        }
        if self._proxy is not None:
            sts_config['proxy'] = self._proxy
        if self._url is not None:
            sts_config['url'] = self._url
            # STS SDK computes the signature against `domain` and sends the
            # request to `url` independently.  When a custom URL is provided
            # we must also set `domain` to the same host, otherwise the
            # signature is calculated with the default domain and the server
            # rejects it with AuthFailure.SignatureFailure.
            try:
                from urllib.parse import urlparse
            except ImportError:
                from urlparse import urlparse  # Python 2
            sts_config['domain'] = urlparse(self._url).netloc

        logger.debug(
            'RoleCredentialProvider: refreshing temporary credential via STS, '
            'role_arn=%s',
            self._role_arn,
        )

        sts = Sts(sts_config)
        response = sts.get_role_credential(self._role_arn)

        credentials = response.get('credentials', {})
        tmp_secret_id = credentials.get('tmpSecretId')
        tmp_secret_key = credentials.get('tmpSecretKey')
        tmp_token = credentials.get('sessionToken')
        expired_time = response.get('expiredTime')  # unix timestamp (int)

        if not tmp_secret_id or not tmp_secret_key or not tmp_token:
            raise RuntimeError(
                'RoleCredentialProvider: STS response is missing credentials: %r'
                % response
            )
        if not expired_time:
            raise RuntimeError(
                'RoleCredentialProvider: STS response is missing expiredTime: %r'
                % response
            )

        self._tmp_secret_id = tmp_secret_id
        self._tmp_secret_key = tmp_secret_key
        self._tmp_token = tmp_token
        self._expired_time = int(expired_time)

        logger.info(
            'RoleCredentialProvider: temporary credential refreshed, '
            'expires at unix=%s', self._expired_time,
        )

    def refresh(self):
        """Manually force a credential refresh (thread-safe).

        Useful for proactive refresh or after receiving a 403 response.
        """
        with self._lock:
            self._refresh()
