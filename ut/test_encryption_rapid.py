# -*- coding=utf-8
"""加密客户端与高性能桶数据面标记的本地单测。不依赖真实网络或凭据。"""

import base64
import unittest

import requests

from qcloud_cos import CosClientError, CosConfig
from qcloud_cos.session_auth import require_session_ready

try:
    from qcloud_cos.cos_encryption_client import CosEncryptionClient
    _IMPORT_ERROR = None
except ImportError as error:  # pragma: no cover - 取决于本机是否安装 pycryptodome
    CosEncryptionClient = None
    _IMPORT_ERROR = str(error)

RAPID_BUCKET = 'rapid-x--1250000000'
ORDINARY_BUCKET = 'example-1250000000'
BASE_AK = 'AKIDBASE'
BASE_SK = 'base-secret'
ENCRYPT_KEY = b'encrypted-data-key'
ENCRYPT_IV = b'encrypted-counter-iv'


class _FakeProvider(object):
    """最小 provider：只记录调用，不做真实密码学运算。"""

    def __init__(self):
        self.adjusted = []
        self.inited = []
        self.decrypt_adapters = []

    def adjust_read_offset(self, start):
        self.adjusted.append(start)
        return (start // 16) * 16

    def init_data_cipter_by_user(self, encrypt_key, encrypt_iv, offset=0):
        self.inited.append((encrypt_key, encrypt_iv, offset))

    def make_data_decrypt_adapter(self, rt, offset):
        adapter = ('decrypted', rt, offset)
        self.decrypt_adapters.append(adapter)
        return adapter


class _FakeResponse(object):
    def __init__(self, status_code=200, headers=None, body=b''):
        self.status_code = status_code
        self.headers = headers or {}
        self.content = body

    @property
    def text(self):
        return self.content.decode('utf-8')

    def close(self):
        pass


def _encrypted_object_headers():
    return {
        'Content-Length': '0',
        'Etag': '"encrypted-etag"',
        'x-cos-meta-client-side-encryption-key':
            base64.b64encode(ENCRYPT_KEY).decode('utf-8'),
        'x-cos-meta-client-side-encryption-iv':
            base64.b64encode(ENCRYPT_IV).decode('utf-8'),
    }


class _RequestCaptured(Exception):
    pass


@unittest.skipIf(CosEncryptionClient is None,
                 'cos_encryption_client is unavailable: %s' % (_IMPORT_ERROR,))
class TestEncryptionRapidDataPlane(unittest.TestCase):
    def _client(self, **kwargs):
        values = {
            'Region': 'ap-guangzhou',
            'SecretId': BASE_AK,
            'SecretKey': BASE_SK,
            'Scheme': 'http',
            'KeepAlive': False,
            'Timeout': 5,
        }
        values.update(kwargs)
        conf = CosConfig(**values)
        provider = _FakeProvider()
        client = CosEncryptionClient(
            conf, provider, retry=0, session=requests.Session())
        return client, provider

    def test_encryption_get_object_marks_rapid_data_plane(self):
        client, provider = self._client(
            EnableRapidDomain=True, EnableSessionAuth=True)
        head_response = _encrypted_object_headers()
        heads = []

        def head_object(Bucket, Key, **kwargs):
            heads.append((Bucket, Key, dict(kwargs)))
            return dict(head_response)

        client.head_object = head_object
        captured = {}
        transport = _FakeResponse(200, {'Content-Length': '80'})

        def capture(*_args, **kwargs):
            captured.update(kwargs)
            return transport

        client.send_request = capture

        response = client.get_object(
            Bucket=RAPID_BUCKET, Key='dir/a.txt', Range='bytes=20-99')

        # Rapid 白名单依赖该标记；缺失会让加密 GET 在 session 前被拒绝。
        self.assertTrue(captured.get('_rapid_data_request'))
        self.assertEqual(captured['bucket'], RAPID_BUCKET)
        self.assertEqual(
            captured['url'],
            'http://rapid-x--1250000000.cosrapid.ap-guangzhou.myqcloud.com/dir/a.txt')
        # Range 必须按 block 对齐下调，并保留原始上界。
        self.assertEqual(captured['headers']['Range'], 'bytes=16-99')
        self.assertTrue(captured['stream'])
        self.assertEqual(provider.adjusted, [20])
        self.assertEqual(
            provider.inited, [(ENCRYPT_KEY, ENCRYPT_IV, 16)])
        self.assertEqual(response['Body'], ('decrypted', transport, 4))
        self.assertEqual(response['Etag'], '"encrypted-etag"')
        self.assertEqual(heads, [(RAPID_BUCKET, 'dir/a.txt',
                                  {'Range': 'bytes=20-99'})])

    def test_encryption_get_object_marker_does_not_start_ordinary_session(self):
        client, provider = self._client(
            Endpoint='cos.ap-guangzhou.myqcloud.com')
        self.assertFalse(require_session_ready(client._conf, ORDINARY_BUCKET))
        applied = []
        client._apply_session_credential = (
            lambda *_args, **_kwargs: applied.append(True))
        requested = []

        def http_once(method, url, timeout, **kwargs):
            requested.append((method, url, dict(kwargs.get('headers') or {})))
            if method == 'HEAD':
                return _FakeResponse(200, _encrypted_object_headers())
            return _FakeResponse(200, {'Content-Length': '80'})

        client._http_once = http_once

        response = client.get_object(Bucket=ORDINARY_BUCKET, Key='a.txt')

        self.assertEqual([item[0] for item in requested], ['HEAD', 'GET'])
        for _method, url, headers in requested:
            self.assertEqual(
                url, 'http://example-1250000000.cos.ap-guangzhou.myqcloud.com/a.txt')
            self.assertNotIn('x-cos-security-token', headers)
        # 普通桶不走 session：既不签发凭证，也不因标记改变响应形态。
        self.assertEqual(applied, [])
        self.assertNotIn('ETag', response)
        self.assertEqual(response['Etag'], '"encrypted-etag"')
        self.assertEqual(provider.adjusted, [])
        self.assertEqual(len(provider.decrypt_adapters), 1)

    def test_encryption_get_object_rejects_malformed_range(self):
        client, _provider = self._client(
            EnableRapidDomain=True, EnableSessionAuth=True)
        client.head_object = (
            lambda Bucket, Key, **kwargs: dict(_encrypted_object_headers()))

        def capture(*_args, **_kwargs):
            raise _RequestCaptured()

        client.send_request = capture
        with self.assertRaises(CosClientError) as caught:
            client.get_object(
                Bucket=RAPID_BUCKET, Key='a.txt', Range='bytes=0-1-2')
        self.assertIn('Range is wrong format', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
