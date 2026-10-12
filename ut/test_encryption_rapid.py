# -*- coding=utf-8
"""加密客户端与高性能桶数据面标记的本地单测。不依赖真实网络或凭据。"""

import base64
import os
import unittest

import requests

from qcloud_cos import CosClientError, CosConfig
from qcloud_cos.session_auth import require_session_ready

try:
    from qcloud_cos.cos_encryption_client import CosEncryptionClient
    from qcloud_cos.crypto import AESProvider, RSAProvider, RSAKeyPair, MetaHandle
    _IMPORT_ERROR = None
except ImportError as error:  # pragma: no cover - 取决于本机是否安装 pycryptodome
    CosEncryptionClient = None
    AESProvider = None
    RSAProvider = None
    RSAKeyPair = None
    MetaHandle = None
    _IMPORT_ERROR = str(error)

RAPID_BUCKET = 'rapid-x--1250000000'
ORDINARY_BUCKET = 'example-1250000000'
BASE_AK = 'AKIDBASE'
BASE_SK = 'base-secret'
ENCRYPT_KEY = b'encrypted-data-key'
ENCRYPT_IV = b'encrypted-counter-iv'


MASTER_IV = b'\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10'


class _FakeProvider(object):
    """最小 provider：只记录调用，不做真实密码学运算。"""

    def __init__(self):
        self.adjusted = []
        self.inited = []
        self.decrypt_adapters = []

    def adjust_read_offset(self, start):
        self.adjusted.append(start)
        return (start // 16) * 16

    def init_data_cipter_by_user(self, encrypt_key, encrypt_iv, offset=0, master_iv=None):
        self.inited.append((encrypt_key, encrypt_iv, offset, master_iv))

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


def _encrypted_object_headers(with_master_iv=False):
    headers = {
        'Content-Length': '0',
        'Etag': '"encrypted-etag"',
        'x-cos-meta-client-side-encryption-key':
            base64.b64encode(ENCRYPT_KEY).decode('utf-8'),
        'x-cos-meta-client-side-encryption-iv':
            base64.b64encode(ENCRYPT_IV).decode('utf-8'),
    }
    if with_master_iv:
        headers['x-cos-meta-client-side-encryption-master-iv'] = \
            base64.b64encode(MASTER_IV).decode('utf-8')
    return headers


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
        # 旧格式 header 无 master-iv，解密时 master_iv 应为 None
        self.assertEqual(
            provider.inited, [(ENCRYPT_KEY, ENCRYPT_IV, 16, None)])
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

    def test_encryption_get_object_with_master_iv_header(self):
        """响应头携带 master-iv 时，master_iv 应正确传递给 provider"""
        client, provider = self._client(
            EnableRapidDomain=True, EnableSessionAuth=True)
        head_response = _encrypted_object_headers(with_master_iv=True)
        client.head_object = lambda Bucket, Key, **kwargs: dict(head_response)
        captured = {}
        transport = _FakeResponse(200, {'Content-Length': '80'})

        def capture(*_args, **kwargs):
            captured.update(kwargs)
            return transport

        client.send_request = capture

        response = client.get_object(
            Bucket=RAPID_BUCKET, Key='dir/b.txt')

        self.assertEqual(len(provider.inited), 1)
        ek, ei, offset, miv = provider.inited[0]
        self.assertEqual(ek, ENCRYPT_KEY)
        self.assertEqual(ei, ENCRYPT_IV)
        self.assertEqual(offset, 0)
        self.assertEqual(miv, MASTER_IV,
                         "master_iv from header must be passed to provider")


@unittest.skipIf(AESProvider is None,
                 'crypto module is unavailable: %s' % (_IMPORT_ERROR,))
class TestAESCTRKeystreamReuse(unittest.TestCase):
    """针对 AES-CTR 静态计数器密钥流重用漏洞 (CWE-323) 的本地验证。"""

    def _make_b64_key(self):
        return base64.b64encode(os.urandom(32)).decode()

    def test_master_iv_is_random_per_operation(self):
        """每次 init_data_cipher 必须生成不同的 master IV"""
        from qcloud_cos.crypto import AESCTRCipher
        b64_key = self._make_b64_key()
        results = []
        for _ in range(5):
            p = AESProvider(aes_key=b64_key, cipher=AESCTRCipher())
            ek, ei, miv = p.init_data_cipher()
            self.assertIsNotNone(miv)
            self.assertEqual(len(miv), 16)
            results.append(miv)
        self.assertEqual(len(set(results)), 5,
                         "all master IVs must be unique across operations")

    def test_no_two_time_pad(self):
        """同一 master key 下两次加密，密钥流必须不同。
        固定相同的 data key，比较 '密文 XOR 明文' 得到的信封密钥流。"""
        from qcloud_cos.crypto import AESCTRCipher
        b64_key = self._make_b64_key()
        fixed_data_key = os.urandom(32)

        def encrypt_fixed_key(master_key_b64, data_key):
            """用 AESProvider 加密固定的 data key，返回密文和 master_iv"""
            p = AESProvider(aes_key=master_key_b64, cipher=AESCTRCipher())
            ek, ei, miv = p.init_data_cipher()
            # 拿到实际 data key 的密文需要重新用同一 master_iv 加密 fixed_data_key
            # 直接用 init_ed_obj 重建 cipher 加密
            p.init_ed_obj(miv)
            ct = p._AESProvider__ed_obj.encrypt(data_key)
            return ct, miv

        ct1, miv1 = encrypt_fixed_key(b64_key, fixed_data_key)
        ct2, miv2 = encrypt_fixed_key(b64_key, fixed_data_key)

        self.assertNotEqual(miv1, miv2, "master IVs must differ")

        # 密钥流 = 密文 XOR 明文；bytearray 保持 Python 2/3 行为一致
        ks1 = bytes(bytearray(c ^ p for c, p in
                              zip(bytearray(ct1), bytearray(fixed_data_key))))
        ks2 = bytes(bytearray(c ^ p for c, p in
                              zip(bytearray(ct2), bytearray(fixed_data_key))))
        self.assertNotEqual(ks1, ks2,
                            "keystreams must differ across operations (Two-Time Pad protection)")

    def test_encrypt_decrypt_roundtrip_data_key_and_iv(self):
        """加密后通过 master IV 解密，断言恢复的 data key 和 data IV 与原值一致，
        并通过 provider.data_cipher 验证真实数据加解密往返正确。"""
        from qcloud_cos.crypto import AESCTRCipher
        b64_key = self._make_b64_key()

        # 加密侧 — 显式传独立 cipher
        enc = AESProvider(aes_key=b64_key, cipher=AESCTRCipher())
        ek, ei, miv = enc.init_data_cipher()
        orig_data_key = enc._AESProvider__data_key
        orig_data_iv = enc._AESProvider__data_iv

        # 用 provider 自身的 data_cipher 加密数据
        plaintext = b'Hello, COS encryption roundtrip test!'
        ciphertext = enc.data_cipher.encrypt(plaintext)

        # 解密侧 — 显式传独立 cipher
        dec = AESProvider(aes_key=b64_key, cipher=AESCTRCipher())
        dec.init_data_cipter_by_user(ek, ei, 0, miv)
        recovered_data_key = dec._AESProvider__data_key
        recovered_data_iv = dec._AESProvider__data_iv

        self.assertEqual(recovered_data_key, orig_data_key,
                         "recovered data key must match original")
        self.assertEqual(recovered_data_iv, orig_data_iv,
                         "recovered data IV must match original")

        # 用解密侧 provider 自身的 data_cipher 解密
        decrypted = dec.data_cipher.decrypt(ciphertext)
        self.assertEqual(decrypted, plaintext,
                         "decrypted data must match original plaintext")

    def test_wrong_master_iv_produces_wrong_data(self):
        """使用错误的 master IV 解密会得到错误的明文"""
        from qcloud_cos.crypto import AESCTRCipher
        b64_key = self._make_b64_key()
        plaintext = b'Sensitive data that must be protected'

        # 加密
        enc = AESProvider(aes_key=b64_key, cipher=AESCTRCipher())
        ek, ei, miv = enc.init_data_cipher()
        ciphertext = enc.data_cipher.encrypt(plaintext)

        # 构造错误 IV（翻转第一个字节）；bytearray 兼容 Python 2/3
        wrong_iv = bytes(bytearray([bytearray(miv)[0] ^ 1])) + miv[1:]

        # 正确 IV 解密
        dec_ok = AESProvider(aes_key=b64_key, cipher=AESCTRCipher())
        dec_ok.init_data_cipter_by_user(ek, ei, 0, miv)
        self.assertEqual(dec_ok.data_cipher.decrypt(ciphertext), plaintext)

        # 错误 IV 解密
        dec_bad = AESProvider(aes_key=b64_key, cipher=AESCTRCipher())
        dec_bad.init_data_cipter_by_user(ek, ei, 0, wrong_iv)
        self.assertNotEqual(dec_bad.data_cipher.decrypt(ciphertext), plaintext,
                            "wrong master IV must produce incorrect plaintext")

    def test_meta_handle_stores_master_iv(self):
        """MetaHandle 必须将 master IV 写入/读出 object metadata"""
        from qcloud_cos.crypto import AESCTRCipher
        b64_key = self._make_b64_key()
        enc = AESProvider(aes_key=b64_key, cipher=AESCTRCipher())
        ek, ei, miv = enc.init_data_cipher()

        meta = MetaHandle(ek, ei, miv)
        headers = meta.set_object_meta({})
        metadata = headers['Metadata']
        self.assertIn('x-cos-meta-client-side-encryption-master-iv', metadata)

        meta2 = MetaHandle()
        ek_r, ei_r, miv_r = meta2.get_object_meta(metadata)
        self.assertEqual(ek_r, ek)
        self.assertEqual(ei_r, ei)
        self.assertEqual(miv_r, miv)

    def test_backward_compat_old_format_decrypt(self):
        """旧格式数据（counter=0 加密）用 master_iv=None 可正确解密"""
        from Crypto.Cipher import AES as RawAES
        from Crypto.Util import Counter as RawCounter
        from qcloud_cos.crypto import AESCTRCipher

        raw_key = os.urandom(32)
        b64_key = base64.b64encode(raw_key).decode()

        # 模拟旧 SDK 行为：用 counter=0 加密 data key 和 data IV
        data_key = os.urandom(32)
        data_iv = os.urandom(16)
        old_counter = RawCounter.new(128, initial_value=0)
        old_cipher = RawAES.new(raw_key, RawAES.MODE_CTR, counter=old_counter)
        old_encrypted_key = old_cipher.encrypt(data_key)
        old_encrypted_iv = old_cipher.encrypt(data_iv)

        # 旧 header 无 master-iv
        meta = MetaHandle()
        old_headers = {
            'x-cos-meta-client-side-encryption-key':
                base64.b64encode(old_encrypted_key).decode(),
            'x-cos-meta-client-side-encryption-iv':
                base64.b64encode(old_encrypted_iv).decode(),
        }
        ek, ei, miv = meta.get_object_meta(old_headers)
        self.assertIsNone(miv)

        # 新 SDK 用 master_iv=None 解密
        dec = AESProvider(aes_key=b64_key, cipher=AESCTRCipher())
        dec.init_data_cipter_by_user(ek, ei, 0, None)
        self.assertEqual(dec._AESProvider__data_key, data_key,
                         "old-format data key must be correctly recovered with counter=0")
        self.assertEqual(dec._AESProvider__data_iv, data_iv,
                         "old-format data IV must be correctly recovered with counter=0")

    def test_rsa_provider_returns_none_master_iv(self):
        """RSAProvider.init_data_cipher 返回 master_iv=None（RSA 不受此漏洞影响）"""
        from Crypto.PublicKey import RSA as CryptoRSA
        from qcloud_cos.crypto import AESCTRCipher
        key = CryptoRSA.generate(2048)
        pair = RSAKeyPair(key.publickey().export_key(), key.export_key())
        rsa = RSAProvider(key_pair_info=pair, cipher=AESCTRCipher())
        ek, ei, miv = rsa.init_data_cipher()
        self.assertIsNone(miv, "RSAProvider should return None for master_iv")


if __name__ == '__main__':
    unittest.main()
