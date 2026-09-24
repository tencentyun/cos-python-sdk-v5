# -*- coding=utf-8
"""高性能桶 session 鉴权本地单测。不依赖 COS 环境变量或真实网络。"""

import json
import os
import select
import signal
import sys
import threading
import time
import unittest
from datetime import datetime, timedelta

import requests
from six.moves.urllib.parse import parse_qs, quote_plus, unquote, urlparse

import qcloud_cos.cos_client as cos_client_module

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
except ImportError:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

from qcloud_cos import (
    CosClientError, CosConfig, CosS3Auth, CosS3Client, CosServiceError,
    is_rapid_bucket)
from qcloud_cos.session_auth import (
    RAPID_REGIONS,
    SESSION_MODE_READ_ONLY,
    SESSION_MODE_READ_WRITE,
    CreateSessionProvider,
    SessionCredential,
    normalize_session_mode,
    normalize_rapid_region,
    parse_bucket_name_from_host,
    parse_create_session_result,
    parse_expiration,
    rapid_endpoint_for_region,
    rapid_service_domain_for_region,
    require_session_ready,
    should_use_session_auth,
)

RAPID_BUCKET = 'rapid-x--1250000000'
ORDINARY_BUCKET = 'example-1250000000'
RAPID_CREATE_NETWORK = {
    # NOCA:InnerIPLeak(Synthetic address for local tests; not production topology)
    'VpcId': 'vpc-test', 'CidrBlock': '10.230.0.0/24',
    'SubnetId': 'subnet-test', 'Zone': 'ap-guangzhou-1',
}
BASE_AK = 'AKIDBASE'
BASE_SK = 'base-secret'
SESSION_AK = 'SKIDSESSION'
SESSION_SK = 'session-secret'
# NOCA:PasswordLeak(Synthetic credential for local test fixtures; not a real account)
SESSION_TOKEN = 'session-token'


def _far_expiration():
    return datetime.utcnow() + timedelta(hours=2)


def _json_session(secret_id=SESSION_AK, secret_key=SESSION_SK, token=SESSION_TOKEN, expiration=None):
    if expiration is None:
        expiration = _far_expiration()
    expired_time = int((expiration - datetime(1970, 1, 1)).total_seconds())
    return json.dumps({
        'Credentials': {
            'TmpSecretId': secret_id,
            'TmpSecretKey': secret_key,
            'Token': token,
        },
        'ExpiredTime': expired_time,
        'Expiration': expiration.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'RequestId': 'req-json',
    })


def _xml_session(secret_id=SESSION_AK, secret_key=SESSION_SK, token=SESSION_TOKEN, expiration=None):
    if expiration is None:
        expiration = _far_expiration()
    return (
        '<CreateSessionResult><Credentials>'
        '<AccessKeyId>%s</AccessKeyId>'
        '<SecretAccessKey>%s</SecretAccessKey>'
        '<SessionToken>%s</SessionToken>'
        '<Expiration>%s</Expiration>'
        '</Credentials></CreateSessionResult>'
    ) % (secret_id, secret_key, token, expiration.strftime('%Y-%m-%dT%H:%M:%SZ'))


class _MockState(object):
    def __init__(self):
        self.lock = threading.Lock()
        self.requests = []
        self.session_status = 200
        self.session_body = _xml_session()
        self.session_location = ''
        self.object_status = 200
        self.object_body = b'ok'
        self.object_headers = {}
        self.object_xml = (
            b'<CopyObjectResult><ETag>"etag"</ETag>'
            b'<LastModified>2026-01-01T00:00:00.000Z</LastModified></CopyObjectResult>'
        )
        self.redirect_hits = 0
        self.object_403_left = 0
        self.session_seq = 0


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _read_body(self):
        length = int(self.headers.get('Content-Length') or 0)
        if length <= 0:
            return b''
        return self.rfile.read(length)

    def _record(self, body):
        parsed = urlparse(self.path)
        rec = {
            'method': self.command,
            'path': parsed.path,
            'query': parse_qs(parsed.query, keep_blank_values=True),
            'headers': dict(self.headers),
            'body': body,
        }
        with self.server.state.lock:
            self.server.state.requests.append(rec)
        return rec

    def _write(self, status, body=b'', headers=None):
        self.send_response(status)
        self.send_header('Content-Type', 'application/xml')
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        payload = body if isinstance(body, bytes) else body.encode('utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(payload)

    def _handle(self):
        body = self._read_body()
        rec = self._record(body)
        state = self.server.state
        parsed = urlparse(self.path)
        if parsed.path == '/redirected-session':
            with state.lock:
                state.redirect_hits += 1
            self._write(200, b'redirected')
            return
        if parsed.path == '/' and 'session' in rec['query']:
            with state.lock:
                state.session_seq += 1
                status = state.session_status
                payload = state.session_body
                location = state.session_location
            if status in (301, 302, 307, 308):
                self._write(status, b'', {'Location': location or '/redirected-session'})
                return
            self._write(status, payload)
            return
        with state.lock:
            if state.object_403_left > 0:
                state.object_403_left -= 1
                self._write(403, b'<Error><Code>AccessDenied</Code><Message>denied</Message></Error>')
                return
            status = state.object_status
            extra_headers = dict(state.object_headers)
        if rec['method'] == 'PUT' and rec['headers'].get('x-cos-copy-source'):
            self._write(status, state.object_xml, extra_headers or None)
            return
        self._write(status, state.object_body, extra_headers or None)

    def do_GET(self):
        self._handle()

    def do_PUT(self):
        self._handle()

    def do_HEAD(self):
        self._handle()

    def do_DELETE(self):
        self._handle()

    def do_POST(self):
        self._handle()


class _MockServer(object):
    def __init__(self):
        self.state = _MockState()
        self.httpd = HTTPServer(('127.0.0.1', 0), _Handler)
        self.httpd.state = self.state
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever)
        self.thread.daemon = True
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)

    def client(self, **kwargs):
        conf_kw = {
            'Region': 'ap-guangzhou',
            'SecretId': BASE_AK,
            'SecretKey': BASE_SK,
            'Scheme': 'http',
            'Domain': '127.0.0.1:%s' % self.port,
            'EnableSessionAuth': True,
            'KeepAlive': False,
            'AllowRedirects': False,
            'Timeout': 5,
        }
        conf_kw.update(kwargs)
        conf = CosConfig(**conf_kw)
        return CosS3Client(conf, retry=1, session=requests.Session())

    def session_requests(self):
        out = []
        for rec in self.state.requests:
            if rec['path'] == '/' and 'session' in rec['query']:
                out.append(rec)
        return out

    def object_requests(self):
        out = []
        for rec in self.state.requests:
            if rec['path'] != '/' or 'session' not in rec['query']:
                if rec['path'] != '/redirected-session':
                    out.append(rec)
        return out


class TestParseAndBucket(unittest.TestCase):
    def test_auth_default_params_are_instance_local(self):
        conf = CosConfig(Region='ap-guangzhou', SecretId=BASE_AK, SecretKey=BASE_SK)
        first = CosS3Auth(conf)
        second = CosS3Auth(conf)
        first._params['fixture-query'] = 'first'
        self.assertEqual(second._params, {})
        self.assertEqual(CosS3Auth(conf, params=None)._params, {})

        supplied = {'fixture-query': 'caller'}
        explicit = CosS3Auth(conf, params=supplied)
        cloned = explicit.with_credentials(SESSION_AK, SESSION_SK)
        self.assertIs(explicit._params, supplied)
        self.assertIs(cloned._params, supplied)
        request = requests.Request('GET', 'http://example.test/key').prepare()
        cloned(request)
        self.assertEqual(supplied, {'fixture-query': 'caller'})

    def test_is_rapid_bucket(self):
        self.assertTrue(is_rapid_bucket(RAPID_BUCKET))
        self.assertTrue(is_rapid_bucket('local-smoke-x--1250000000'))
        self.assertFalse(is_rapid_bucket('Rapid-x--1250000000'))
        self.assertFalse(is_rapid_bucket(ORDINARY_BUCKET))
        self.assertFalse(is_rapid_bucket('ab'))
        self.assertFalse(is_rapid_bucket(None))

    def test_parse_bucket_name_from_host(self):
        self.assertEqual(parse_bucket_name_from_host(
            'rapid-x--1250000000.cosrapid.ap-guangzhou.myqcloud.com'),
            RAPID_BUCKET)
        self.assertEqual(parse_bucket_name_from_host(
            'Rapid-x--1250000000.cosrapid.ap-guangzhou.myqcloud.com'), u'')
        self.assertEqual(parse_bucket_name_from_host(
            'rapid-x--1250000000.cosrapid.ap-guangzhou.myqcloud.com.'), u'')
        self.assertEqual(
            parse_bucket_name_from_host(
                'rapid-x--1250000000.cosrapid.ap-guangzhou.myqcloud.com:443'),
            u'')
        self.assertEqual(
            parse_bucket_name_from_host(
                'rapid-x--1250000000.cosrapid.ap-shanghai.myqcloud.com'),
            RAPID_BUCKET)
        self.assertEqual(parse_bucket_name_from_host(
            'rapid-x--1250000000.cosrapid.ap-notexist.myqcloud.com'), u'')
        self.assertEqual(parse_bucket_name_from_host(
            'ordinary.cosrapid.ap-guangzhou.myqcloud.com'), u'')
        self.assertEqual(parse_bucket_name_from_host(
            'service.cosrapid.ap-guangzhou.myqcloud.com'), u'')
        self.assertEqual(parse_bucket_name_from_host(
            'rapid-x--1250000000.gz.tencentcos.com'), u'')
        self.assertEqual(parse_bucket_name_from_host('example.cos.ap-guangzhou.myqcloud.com'), u'')

    def test_rapid_regions_match_gateway_contract(self):
        expected = frozenset((
            u'ap-guangzhou', u'ap-shanghai', u'ap-hongkong', u'ap-beijing',
            u'ap-singapore', u'na-siliconvalley', u'ap-chengdu',
            u'eu-frankfurt', u'ap-seoul', u'ap-chongqing', u'na-ashburn',
            u'ap-bangkok', u'ap-tokyo', u'ap-nanjing', u'ap-tianjin',
            u'ap-shenzhen', u'ap-taipei', u'sl-saopaulo', u'ap-others',
            u'ap-qingyuan', u'ap-jakarta', u'sa-saopaulo', u'ap-guiyang',
            u'me-saudi-arabia', u'ap-zhongwei', u'na-queretaro',
            u'ap-johorbahru', u'ap-osaka',
        ))
        self.assertEqual(RAPID_REGIONS, expected)
        self.assertEqual(normalize_rapid_region('cosgz'), u'ap-guangzhou')
        self.assertEqual(
            rapid_endpoint_for_region('ap-guangzhou'),
            u'cosrapid.ap-guangzhou.myqcloud.com')
        self.assertEqual(
            rapid_service_domain_for_region('ap-nanjing'),
            u'service.cosrapid.ap-nanjing.myqcloud.com')
        with self.assertRaises(CosClientError):
            rapid_endpoint_for_region('ap-unsupported')

    def test_rapid_endpoint_or_domain_can_supply_missing_region(self):
        endpoint_conf = CosConfig(
            SecretId=BASE_AK, SecretKey=BASE_SK,
            Endpoint='cosrapid.ap-nanjing.myqcloud.com')
        self.assertEqual(
            endpoint_conf._rapid_service_domain,
            'service.cosrapid.ap-nanjing.myqcloud.com')
        self.assertTrue(should_use_session_auth(endpoint_conf, RAPID_BUCKET))

        domain_conf = CosConfig(
            SecretId=BASE_AK, SecretKey=BASE_SK,
            Domain=(
                'rapid-x--1250000000.cosrapid.'
                'ap-nanjing.myqcloud.com'),
            EnableRapidDomain=True)
        self.assertEqual(
            domain_conf._rapid_service_domain,
            'service.cosrapid.ap-nanjing.myqcloud.com')

        # Domain-only（Endpoint 未指定）也要被 auto 识别为 Rapid 主机。
        auto_domain_conf = CosConfig(
            SecretId=BASE_AK, SecretKey=BASE_SK,
            Domain=(
                'rapid-x--1250000000.cosrapid.'
                'ap-nanjing.myqcloud.com'))
        self.assertTrue(should_use_session_auth(auto_domain_conf, RAPID_BUCKET))
        self.assertFalse(should_use_session_auth(auto_domain_conf, ORDINARY_BUCKET))
        self.assertEqual(
            auto_domain_conf._rapid_service_domain,
            'service.cosrapid.ap-nanjing.myqcloud.com')

    def test_auto_rapid_endpoint_honors_explicit_service_domain(self):
        conf = CosConfig(
            Region='ap-guangzhou', SecretId=BASE_AK, SecretKey=BASE_SK,
            Endpoint='cosrapid.ap-guangzhou.myqcloud.com',
            ServiceDomain='127.0.0.1:19000')
        self.assertEqual(conf._service_domain, '127.0.0.1:19000')
        self.assertEqual(conf._rapid_service_domain, '127.0.0.1:19000')

    def test_parse_json_legacy_proxy(self):
        parsed = parse_create_session_result(_json_session())
        cred = parsed['credential']
        self.assertEqual(cred.secret_id, SESSION_AK)
        self.assertEqual(cred.secret_key, SESSION_SK)
        self.assertEqual(cred.session_token, SESSION_TOKEN)
        self.assertIsNotNone(cred.expiration)

    def test_parse_xml_aws(self):
        parsed = parse_create_session_result(_xml_session())
        cred = parsed['credential']
        self.assertEqual(cred.secret_id, SESSION_AK)
        self.assertEqual(cred.session_token, SESSION_TOKEN)

    def test_parse_incomplete_and_empty(self):
        self.assertRaises(CosClientError, parse_create_session_result, '{}')
        self.assertRaises(CosClientError, parse_create_session_result, '')
        self.assertRaises(CosClientError, parse_create_session_result, 'not-xml-or-json')

    def test_parse_expiration_unix(self):
        dt = parse_expiration(None, 4070912645)
        self.assertEqual(dt.year, 2099)

    def test_parse_expiration_converts_numeric_offsets_to_utc(self):
        self.assertEqual(
            parse_expiration('2026-07-03T11:55:41+08:00'),
            datetime(2026, 7, 3, 3, 55, 41))
        self.assertEqual(
            parse_expiration('2026-07-03T03:55:41-08:00'),
            datetime(2026, 7, 3, 11, 55, 41))
        self.assertEqual(
            parse_expiration('2026-07-03T03:55:41.123Z'),
            datetime(2026, 7, 3, 3, 55, 41, 123000))
        self.assertEqual(
            parse_expiration('2026-07-03T03:55:41'),
            datetime(2026, 7, 3, 3, 55, 41))

    def test_normalize_mode(self):
        self.assertEqual(normalize_session_mode(None), SESSION_MODE_READ_WRITE)
        self.assertEqual(normalize_session_mode('ReadOnly'), SESSION_MODE_READ_ONLY)
        self.assertRaises(CosClientError, normalize_session_mode, 'WriteOnly')

    def test_create_session_parser_rejects_malformed_payload_matrix(self):
        credentials_body = (
            '<AccessKeyId>%s</AccessKeyId>'
            '<SecretAccessKey>%s</SecretAccessKey>'
            '<SessionToken>%s</SessionToken>'
        ) % (SESSION_AK, SESSION_SK, SESSION_TOKEN)
        cases = [
            (None, 'response is empty'),
            ('   ', 'response is empty'),
            ('{', 'JSON decode failed'),
            ('{"Credentials": []}', 'credentials are incomplete'),
            # NOCA:PasswordLeak(Synthetic credential for local test fixtures; not a real account)
            ('{"Credentials": [{"TmpSecretId": "x"}]}',
             'credentials are incomplete'),
            ('<CreateSessionResult><Foo/></CreateSessionResult>',
             'credentials are incomplete'),
            ('<', 'XML decode failed'),
            ('<CreateSessionResult><Credentials>%s</Credentials>'
             '</CreateSessionResult>' % credentials_body,
             'expiration is missing'),
            (json.dumps({'Credentials': {
                'TmpSecretId': SESSION_AK,
                'TmpSecretKey': SESSION_SK,
                'Token': SESSION_TOKEN,
            }}), 'expiration is missing'),
            ('<CreateSessionResult><ExpiredTime>not-a-number</ExpiredTime>'
             '<Credentials>%s</Credentials></CreateSessionResult>'
             % credentials_body,
             'expiration is missing'),
            (json.dumps({
                'Credentials': {
                    'TmpSecretId': SESSION_AK,
                    'TmpSecretKey': SESSION_SK,
                    'Token': SESSION_TOKEN,
                },
                'ExpiredTime': 'not-a-number',
            }), 'expiration is missing'),
        ]
        for payload, expected in cases:
            try:
                parse_create_session_result(payload)
                self.fail('expected rejection for payload %r' % (payload,))
            except CosClientError as e:
                self.assertIn(expected, str(e))

        # 非法 ExpiredTime 必须解析为 None，由上层 fail-closed。
        self.assertIsNone(parse_expiration(None, 'not-a-number'))
        self.assertIsNone(parse_expiration('', 0))
        self.assertIsNone(parse_expiration('2026-13-99T99:99:99Z'))
        self.assertEqual(
            parse_expiration('2026-07-03T03:55:41.123'),
            datetime(2026, 7, 3, 3, 55, 41, 123000))

        # 根节点直接是 Credentials 的兼容形态仍需正常解析。
        expiration = _far_expiration().replace(microsecond=0)
        parsed = parse_create_session_result(
            '<Credentials>%s<Expiration>%s</Expiration></Credentials>' % (
                credentials_body, expiration.strftime('%Y-%m-%dT%H:%M:%SZ')))
        self.assertEqual(parsed['credential'].secret_id, SESSION_AK)
        self.assertEqual(parsed['credential'].secret_key, SESSION_SK)
        self.assertEqual(parsed['credential'].session_token, SESSION_TOKEN)
        self.assertEqual(parsed['credential'].expiration, expiration)

        # 带默认命名空间的 AWS 兼容 XML 也必须解析（tag 形如 {ns}Credentials）。
        namespaced = parse_create_session_result((
            '<CreateSessionResult xmlns="http://cos.tencentyun.com/doc/api">'
            '<Credentials>%s<Expiration>%s</Expiration></Credentials>'
            '<RequestId>req-ns</RequestId>'
            '</CreateSessionResult>') % (
                credentials_body,
                expiration.strftime('%Y-%m-%dT%H:%M:%SZ')))
        self.assertEqual(namespaced['credential'].secret_id, SESSION_AK)
        self.assertEqual(namespaced['credential'].expiration, expiration)
        self.assertEqual(namespaced['RequestId'], 'req-ns')

        # bytes 响应体与 bytes/None 凭证字段都要归一为文本。
        self.assertEqual(
            parse_create_session_result(
                _xml_session().encode('utf-8'))['credential'].secret_id,
            SESSION_AK)
        coerced = SessionCredential(b'sid', b'sk', b'tok', None)
        self.assertEqual(coerced.secret_id, u'sid')
        self.assertEqual(coerced.session_token, u'tok')
        self.assertEqual(SessionCredential(None, None, None, None).secret_id, u'')
        # 没有 expiration 的凭证不能覆盖任何窗口。
        self.assertIsNone(coerced.remaining())
        self.assertFalse(coerced.covers(0))

    def test_enable_rapid_domain_rejects_invalid_region_endpoint_and_domain(self):
        cases = [
            ({'EnableRapidDomain': True}, 'Region is required'),
            ({'EnableRapidDomain': True, 'Region': 'ap-guangzhou',
              'Domain': 'service.cosrapid.ap-guangzhou.myqcloud.com'},
             'requires Domain'),
            ({'EnableRapidDomain': True, 'Region': 'ap-guangzhou',
              'Domain': 'example-1250000000.cos.ap-guangzhou.myqcloud.com'},
             'requires Domain'),
            ({'EnableRapidDomain': True, 'Region': 'ap-guangzhou',
              'Endpoint': 'cosrapid.ap-shanghai.myqcloud.com'},
             'requires Endpoint'),
            ({'EnableRapidDomain': True, 'Region': 'ap-notexist'},
             'does not support region'),
            ({'EnableRapidDomain': True, 'Domain': 'example.com'},
             'Region or a valid Rapid Endpoint/Domain is required'),
        ]
        for kwargs, expected in cases:
            values = {'SecretId': BASE_AK, 'SecretKey': BASE_SK}
            values.update(kwargs)
            try:
                CosConfig(**values)
                self.fail('expected rejection for %r' % (kwargs,))
            except CosClientError as e:
                self.assertIn(expected, str(e))

        for bad_region in (None, u'', 'ap-notexist', 'cos-unknown'):
            self.assertRaises(
                CosClientError, rapid_service_domain_for_region, bad_region)
            self.assertRaises(
                CosClientError, rapid_endpoint_for_region, bad_region)


class TestProvider(unittest.TestCase):
    def test_same_bucket_create_session_is_singleflight(self):
        entered = threading.Event()
        release = threading.Event()
        calls = []
        results = []

        def create_fn(bucket, mode):
            calls.append((bucket, mode))
            entered.set()
            release.wait(5)
            return SessionCredential(
                'sid', 'sk', 'tok', _far_expiration(), mode=mode)

        provider = CreateSessionProvider(create_fn, lambda: u'AK')

        def worker():
            results.append(provider.get_credential('bucket-a').secret_id)

        first = threading.Thread(target=worker)
        second = threading.Thread(target=worker)
        first.daemon = True
        second.daemon = True
        first.start()
        self.assertTrue(entered.wait(2), 'CreateSession did not start')
        second.start()
        release.set()
        first.join(2)
        second.join(2)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(calls, [('bucket-a', SESSION_MODE_READ_WRITE)])
        self.assertEqual(results, ['sid', 'sid'])

    def test_cache_and_fingerprint_and_fallback(self):
        calls = []
        base_ak = [u'AK1']
        fail_next = [False]

        def create_fn(bucket, mode):
            calls.append((bucket, mode))
            if fail_next[0]:
                raise CosClientError('create failed')
            return {
                'credential': SessionCredential(
                    'sid-%s' % bucket, 'sk', 'tok', _far_expiration(), mode=mode)
            }

        provider = CreateSessionProvider(
            create_fn, lambda: base_ak[0], refresh_before=60, evict_debounce=1)
        a1 = provider.get_credential('bucket-a', mode=SESSION_MODE_READ_WRITE)
        a2 = provider.get_credential('bucket-a', mode=SESSION_MODE_READ_WRITE)
        b1 = provider.get_credential('bucket-b', mode=SESSION_MODE_READ_WRITE)
        self.assertEqual(a1.secret_id, a2.secret_id)
        self.assertNotEqual(a1.secret_id, b1.secret_id)
        self.assertEqual(len(calls), 2)

        base_ak[0] = u'AK2'
        a3 = provider.get_credential('bucket-a')
        self.assertEqual(len(calls), 3)
        self.assertEqual(a3.secret_id, 'sid-bucket-a')

        fail_next[0] = True
        reused = provider.get_credential('bucket-a', force_refresh=True)
        self.assertEqual(reused.secret_id, a3.secret_id)
        self.assertEqual(len(calls), 4)

    def test_readonly_does_not_cover_readwrite(self):
        calls = []

        def create_fn(bucket, mode):
            calls.append(mode)
            return {'credential': SessionCredential('sid', 'sk', 'tok', _far_expiration(), mode=mode)}

        provider = CreateSessionProvider(create_fn, lambda: u'AK', refresh_before=60)
        provider.get_credential('b', mode=SESSION_MODE_READ_ONLY)
        provider.get_credential('b', mode=SESSION_MODE_READ_WRITE)
        self.assertEqual(calls, [SESSION_MODE_READ_ONLY, SESSION_MODE_READ_WRITE])

    def test_readonly_cache_covers_further_readonly_requests(self):
        calls = []

        def create_fn(bucket, mode):
            calls.append(mode)
            return {'credential': SessionCredential(
                'sid', 'sk', 'tok', _far_expiration(), mode=mode)}

        provider = CreateSessionProvider(create_fn, lambda: u'AK', refresh_before=60)
        first = provider.get_credential('b', mode=SESSION_MODE_READ_ONLY)
        second = provider.get_credential('b', mode=SESSION_MODE_READ_ONLY)
        self.assertTrue(second is first)
        self.assertEqual(calls, [SESSION_MODE_READ_ONLY])

    def test_create_session_failure_without_cache_is_fail_closed(self):
        calls = []

        def create_fn(bucket, mode):
            calls.append(mode)
            raise CosClientError('create failed')

        provider = CreateSessionProvider(create_fn, lambda: u'AK')
        # 无可复用缓存时必须抛出原始错误，不能返回空凭证。
        try:
            provider.get_credential('b')
            self.fail('expected CreateSession failure to propagate')
        except CosClientError as e:
            self.assertIn('create failed', str(e))
        self.assertEqual(calls, [SESSION_MODE_READ_WRITE])

    def test_evict_debounce(self):
        provider = CreateSessionProvider(lambda b, m: None, lambda: u'AK', evict_debounce=10)
        self.assertTrue(provider.evict('b', now=100.0))
        self.assertFalse(provider.evict('b', now=101.0))
        self.assertTrue(provider.evict('b', now=111.0))

    def test_presign_readonly_does_not_reuse_readwrite(self):
        calls = []

        def create_fn(bucket, mode):
            calls.append(mode)
            return {
                'credential': SessionCredential(
                    'sid-%s' % mode, 'sk', 'tok-%s' % mode, _far_expiration(), mode=mode)
            }

        provider = CreateSessionProvider(create_fn, lambda: u'AK', refresh_before=60)
        rw = provider.get_credential('b', mode=SESSION_MODE_READ_WRITE)
        ro = provider.fresh_credential('b', 300, mode=SESSION_MODE_READ_ONLY, isolated_readonly=True)
        self.assertEqual(calls, [SESSION_MODE_READ_WRITE, SESSION_MODE_READ_ONLY])
        self.assertEqual(ro.secret_id, 'sid-ReadOnly')
        self.assertNotEqual(ro.session_token, rw.session_token)

        ro2 = provider.fresh_credential('b', 300, mode=SESSION_MODE_READ_ONLY, isolated_readonly=True)
        self.assertEqual(ro2.secret_id, ro.secret_id)
        self.assertEqual(len(calls), 2)

        rw2 = provider.get_credential('b', mode=SESSION_MODE_READ_WRITE)
        self.assertEqual(rw2.secret_id, rw.secret_id)
        self.assertEqual(len(calls), 2)

        put_url_cred = provider.fresh_credential('b', 300, mode=SESSION_MODE_READ_WRITE)
        self.assertEqual(put_url_cred.secret_id, rw.secret_id)
        self.assertEqual(len(calls), 2)

        self.assertTrue(provider.evict('b', now=100.0, force=True))
        provider.fresh_credential('b', 300, mode=SESSION_MODE_READ_ONLY, isolated_readonly=True)
        self.assertEqual(len(calls), 3)

    @staticmethod
    def _tracked_provider():
        """返回 (provider, state)；state 控制过期时间、基础 AK 与失败注入。"""
        state = {
            'calls': [],
            'fail': False,
            'expiration': _far_expiration(),
            'base_ak': [u'AK1'],
        }

        def create_fn(bucket, mode):
            state['calls'].append(mode)
            if state['fail']:
                raise CosClientError('create failed')
            return {'credential': SessionCredential(
                'sid-%s' % mode, 'sk-%s' % mode, 'tok-%s' % mode,
                state['expiration'], mode=mode)}

        provider = CreateSessionProvider(
            create_fn, lambda: state['base_ak'][0], refresh_before=60)
        return provider, state

    def test_presign_readonly_refresh_failure_fallback_matrix(self):
        # 1. 缓存 RO 不足 300s 但未过期：刷新失败时复用旧 RO，且不污染 RW 槽。
        provider, state = self._tracked_provider()
        state['expiration'] = datetime.utcnow() + timedelta(seconds=200)
        seeded = provider._get_presign_readonly(RAPID_BUCKET, reuse_window=60)
        readwrite = provider.get_credential(
            RAPID_BUCKET, mode=SESSION_MODE_READ_WRITE)
        self.assertEqual(
            state['calls'], [SESSION_MODE_READ_ONLY, SESSION_MODE_READ_WRITE])

        state['fail'] = True
        reused = provider._get_presign_readonly(RAPID_BUCKET, reuse_window=300)
        self.assertTrue(reused is seeded)
        self.assertEqual(reused.mode, SESSION_MODE_READ_ONLY)
        self.assertEqual(reused.session_token, 'tok-ReadOnly')
        self.assertEqual(len(state['calls']), 3)

        still_readwrite = provider.get_credential(
            RAPID_BUCKET, mode=SESSION_MODE_READ_WRITE)
        self.assertTrue(still_readwrite is readwrite)
        self.assertEqual(still_readwrite.session_token, 'tok-ReadWrite')
        self.assertEqual(len(state['calls']), 3)

        # 复用只发生在 provider 层；对外仍必须 fail-closed，不签发短寿命 URL。
        try:
            provider.fresh_credential(
                RAPID_BUCKET, 300, mode=SESSION_MODE_READ_ONLY,
                isolated_readonly=True)
            self.fail('expected fail-closed presign rejection')
        except CosClientError as e:
            self.assertIn('shorter than required 300s', str(e))

        # 2. 缓存已过期：刷新失败时抛出原始错误。
        provider, state = self._tracked_provider()
        state['expiration'] = datetime.utcnow() - timedelta(seconds=10)
        provider._get_presign_readonly(RAPID_BUCKET, reuse_window=1)
        state['fail'] = True
        try:
            provider._get_presign_readonly(RAPID_BUCKET, reuse_window=1)
            self.fail('expected expired ReadOnly cache to be rejected')
        except CosClientError as e:
            self.assertIn('create failed', str(e))
        self.assertEqual(len(state['calls']), 2)

        # 3. 基础 AK 变化：不得复用旧 RO。
        provider, state = self._tracked_provider()
        state['expiration'] = datetime.utcnow() + timedelta(seconds=200)
        provider._get_presign_readonly(RAPID_BUCKET, reuse_window=60)
        state['base_ak'][0] = u'AK2'
        state['fail'] = True
        try:
            provider._get_presign_readonly(RAPID_BUCKET, reuse_window=60)
            self.fail('expected base AK change to invalidate ReadOnly cache')
        except CosClientError as e:
            self.assertIn('create failed', str(e))
        self.assertEqual(len(state['calls']), 2)

        # 4. 缓存 mode 不是 ReadOnly：不得复用。
        provider, state = self._tracked_provider()
        state['expiration'] = datetime.utcnow() + timedelta(seconds=200)
        provider._get_presign_readonly(RAPID_BUCKET, reuse_window=60)
        provider._bucket(RAPID_BUCKET).presign_ro_cred.mode = (
            SESSION_MODE_READ_WRITE)
        state['fail'] = True
        try:
            provider._get_presign_readonly(RAPID_BUCKET, reuse_window=60)
            self.fail('expected ReadWrite cache to be rejected for presign')
        except CosClientError as e:
            self.assertIn('create failed', str(e))
        self.assertEqual(len(state['calls']), 2)

    def test_fresh_credential_rejects_invalid_required_lifetime(self):
        provider, state = self._tracked_provider()
        cases = [
            (None, 'required lifetime is missing'),
            (0, 'must be positive'),
            (-1, 'must be positive'),
        ]
        for min_remaining, expected in cases:
            try:
                provider.fresh_credential(RAPID_BUCKET, min_remaining)
                self.fail('expected rejection for %r' % (min_remaining,))
            except CosClientError as e:
                self.assertIn(expected, str(e))
        # 非法寿命必须在 CreateSession 之前拒绝。
        self.assertEqual(state['calls'], [])

    def test_fresh_credential_rejects_missing_or_short_expiration(self):
        provider, state = self._tracked_provider()
        state['expiration'] = None
        try:
            provider.fresh_credential(RAPID_BUCKET, 300)
            self.fail('expected missing expiration to be rejected')
        except CosClientError as e:
            self.assertIn('expiration is missing', str(e))

        provider, state = self._tracked_provider()
        state['expiration'] = datetime.utcnow() + timedelta(seconds=120)
        try:
            provider.fresh_credential(RAPID_BUCKET, 300)
            self.fail('expected short lifetime to be rejected')
        except CosClientError as e:
            self.assertIn('shorter than required 300s', str(e))
        # 恰好覆盖窗口时可用，说明拒绝只针对越过 token 寿命的情况。
        self.assertTrue(
            provider.fresh_credential(RAPID_BUCKET, 60).covers(60))

    @unittest.skipUnless(hasattr(os, 'fork'), 'requires os.fork')
    def test_fork_resets_inherited_locked_bucket_session(self):
        provider = CreateSessionProvider(
            lambda bucket, mode: SessionCredential(
                'child-ak', 'child-sk', 'child-token', _far_expiration(), mode),
            lambda: u'base-ak')
        parent_session = provider._bucket('bucket-a')
        parent_session.lock.acquire()
        read_fd, write_fd = os.pipe()
        child_pid = os.fork()
        if child_pid == 0:
            try:
                os.close(read_fd)
                cred = provider.get_credential('bucket-a')
                result = {
                    'secret_id': cred.secret_id,
                    'pid_match': provider._pid == os.getpid(),
                    'new_session': provider._bucket('bucket-a') is not parent_session,
                }
                os.write(write_fd, json.dumps(result).encode('utf-8'))
            finally:
                os.close(write_fd)
                os._exit(0)

        os.close(write_fd)
        try:
            readable, _, _ = select.select([read_fd], [], [], 5)
            self.assertTrue(readable, 'child blocked on inherited provider lock')
            result = json.loads(os.read(read_fd, 4096).decode('utf-8'))
            self.assertEqual(result['secret_id'], 'child-ak')
            self.assertTrue(result['pid_match'])
            self.assertTrue(result['new_session'])
            _, status = os.waitpid(child_pid, 0)
            self.assertTrue(os.WIFEXITED(status))
            self.assertEqual(os.WEXITSTATUS(status), 0)
        finally:
            os.close(read_fd)
            parent_session.lock.release()
            try:
                waited, _ = os.waitpid(child_pid, os.WNOHANG)
                if waited == 0:
                    os.kill(child_pid, signal.SIGKILL)
                    os.waitpid(child_pid, 0)
            except OSError:
                pass


class TestClientSession(unittest.TestCase):
    def setUp(self):
        self.server = _MockServer()

    def tearDown(self):
        self.server.close()

    def test_put_uses_session_xml_and_mode_header(self):
        client = self.server.client()
        client.put_object(Bucket=RAPID_BUCKET, Key='a.txt', Body=b'hello')
        sessions = self.server.session_requests()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]['headers'].get('x-cos-create-session-mode'), 'ReadWrite')
        accept = sessions[0]['headers'].get('Accept') or sessions[0]['headers'].get('accept')
        self.assertEqual(accept, 'application/xml')
        auth = sessions[0]['headers'].get('Authorization') or sessions[0]['headers'].get('authorization')
        self.assertIn('q-ak=' + BASE_AK, auth)
        objects = self.server.object_requests()
        self.assertEqual(len(objects), 1)
        obj_auth = objects[0]['headers'].get('Authorization') or objects[0]['headers'].get('authorization')
        self.assertIn('q-ak=' + SESSION_AK, obj_auth)
        self.assertEqual(objects[0]['headers'].get('x-cos-security-token'), SESSION_TOKEN)
        self.assertEqual(objects[0]['body'], b'hello')

    def test_json_session_still_accepted(self):
        """历史 proxy JSON 在过渡期继续兼容。"""
        self.server.state.session_body = _json_session()
        client = self.server.client()
        client.put_object(Bucket=RAPID_BUCKET, Key='a.txt', Body=b'hello')
        objects = self.server.object_requests()
        obj_auth = objects[0]['headers'].get('Authorization') or objects[0]['headers'].get('authorization')
        self.assertIn('q-ak=' + SESSION_AK, obj_auth)

    def test_cache_single_create_session(self):
        client = self.server.client()
        client.put_object(Bucket=RAPID_BUCKET, Key='a.txt', Body=b'1')
        client.put_object(Bucket=RAPID_BUCKET, Key='b.txt', Body=b'2')
        self.assertEqual(len(self.server.session_requests()), 1)

    def test_403_evicts_and_retries_once(self):
        self.server.state.object_403_left = 1
        # NOCA:PasswordLeak(Synthetic credential for local test fixtures; not a real account)
        self.server.state.session_body = _xml_session(secret_id='SKID-1', token='tok-1')
        client = self.server.client()

        orig = client._session_provider._create_fn

        def flipping(bucket, mode):
            n = len(self.server.session_requests()) + 1
            self.server.state.session_body = _xml_session(
                # NOCA:PasswordLeak(Synthetic credential for local test fixtures; not a real account)
                secret_id='SKID-%d' % n, token='tok-%d' % n)
            return orig(bucket, mode)

        client._session_provider._create_fn = flipping
        client.put_object(Bucket=RAPID_BUCKET, Key='a.txt', Body=b'hello')
        self.assertGreaterEqual(len(self.server.session_requests()), 2)
        objects = self.server.object_requests()
        self.assertEqual(len(objects), 2)
        last_auth = objects[-1]['headers'].get('Authorization') or objects[-1]['headers'].get('authorization')
        self.assertIn('q-ak=SKID-2', last_auth)

    def test_upload_part_copy_uses_session(self):
        self.server.state.object_xml = b'<CopyPartResult><ETag>"etag"</ETag></CopyPartResult>'
        client = self.server.client()
        client.upload_part_copy(
            Bucket=RAPID_BUCKET,
            Key='dst.txt',
            PartNumber=1,
            UploadId='upload-1',
            CopySource={'Bucket': RAPID_BUCKET, 'Key': 'src.txt', 'Region': 'ap-guangzhou'})
        objects = self.server.object_requests()
        self.assertEqual(len(objects), 1)
        auth = objects[0]['headers'].get('Authorization') or objects[0]['headers'].get('authorization')
        self.assertIn('q-ak=' + SESSION_AK, auth)
        self.assertTrue(objects[0]['query'].get('partNumber') or objects[0]['query'].get('partnumber'))

    def test_copy_uses_session(self):
        client = self.server.client()
        client.copy_object(
            Bucket=RAPID_BUCKET,
            Key='dst.txt',
            CopySource={'Bucket': RAPID_BUCKET, 'Key': 'src.txt', 'Region': 'ap-guangzhou'})
        objects = self.server.object_requests()
        self.assertEqual(len(objects), 1)
        auth = objects[0]['headers'].get('Authorization') or objects[0]['headers'].get('authorization')
        self.assertIn('q-ak=' + SESSION_AK, auth)
        self.assertTrue(objects[0]['headers'].get('x-cos-copy-source'))

    def test_control_plane_uses_base_ak(self):
        client = self.server.client()
        client.create_bucket(Bucket=RAPID_BUCKET, **RAPID_CREATE_NETWORK)
        client.head_bucket(Bucket=RAPID_BUCKET)
        self.assertEqual(len(self.server.session_requests()), 0)
        for rec in self.server.object_requests():
            auth = rec['headers'].get('Authorization') or rec['headers'].get('authorization')
            self.assertIn('q-ak=' + BASE_AK, auth)
            self.assertFalse(rec['headers'].get('x-cos-security-token'))

    def test_control_plane_with_session_auth_disabled(self):
        for flag in (False, None):
            client = self.server.client(EnableSessionAuth=flag)
            self.server.state.requests[:] = []
            self.server.state.object_body = b'{}'
            client.create_bucket(Bucket=RAPID_BUCKET, **RAPID_CREATE_NETWORK)
            client.head_bucket(Bucket=RAPID_BUCKET)
            client.put_bucket_policy(Bucket=RAPID_BUCKET, Policy={})
            client.get_bucket_policy(Bucket=RAPID_BUCKET)
            client.delete_bucket_policy(Bucket=RAPID_BUCKET)
            client.delete_bucket(Bucket=RAPID_BUCKET)
            self.assertEqual(len(self.server.session_requests()), 0)
            self.assertEqual(len(self.server.object_requests()), 6)
            result = client.create_session(Bucket=RAPID_BUCKET)
            self.assertEqual(result['Credentials']['AccessKeyId'], SESSION_AK)
            self.assertEqual(len(self.server.session_requests()), 1)
            for rec in self.server.state.requests:
                headers = requests.structures.CaseInsensitiveDict(rec['headers'])
                self.assertIn('q-ak=' + BASE_AK, headers['Authorization'])
                self.assertFalse(rec['headers'].get('x-cos-security-token'))

    def test_create_bucket_network_headers_and_signature(self):
        network = {
            'x-cos-vpc-id': 'vpc-test',
            # NOCA:InnerIPLeak(Synthetic address for local tests; not production topology)
            'x-cos-cidr-block': '10.230.0.0/24',
            'x-cos-subnet-id': 'subnet-test',
            'x-cos-zone': 'ap-guangzhou-1',
        }
        for flag in (False, None, True):
            client = self.server.client(
                Domain=None, EnableRapidDomain=True, EnableSessionAuth=flag,
                ServiceDomain='127.0.0.1:%s' % self.server.port)
            try:
                self.server.state.requests[:] = []
                variants = [
                    dict(RAPID_CREATE_NETWORK),
                    {'Metadata': dict(network)},
                    {'VpcId': 'vpc-test', 'Zone': 'ap-guangzhou-1', 'Metadata': {
                        # NOCA:InnerIPLeak(Synthetic address for local tests; not production topology)
                        'X-Cos-Cidr-Block': '10.230.0.0/24', 'X-Cos-Subnet-Id': 'subnet-test'}},
                    dict(RAPID_CREATE_NETWORK, Metadata={
                        'X-Cos-Vpc-Id': b'vpc-test', 'x-cos-vpc-id': 'vpc-test'}),
                    {'VpcId': None, 'Metadata': dict(network)},
                ]
                for options in variants:
                    before = len(self.server.object_requests())
                    self.assertIsNone(client.create_bucket(Bucket=RAPID_BUCKET, **options))
                    self.assertEqual(len(self.server.object_requests()), before + 1)
                    rec = self.server.object_requests()[-1]
                    headers = requests.structures.CaseInsensitiveDict(rec['headers'])
                    self.assertEqual(rec['path'], '/')
                    self.assertEqual(headers['Host'],
                                     RAPID_BUCKET + '.cosrapid.ap-guangzhou.myqcloud.com')
                    # Authorization uses '&' fields; ';' belongs to header lists.
                    auth = dict(pair.split('=', 1) for pair in headers['Authorization'].split('&'))
                    self.assertEqual(auth['q-ak'], BASE_AK)
                    signed = auth['q-header-list'].split(';')
                    self.assertIn('host', signed)
                    for name, value in network.items():
                        self.assertEqual(headers[name], value)
                        self.assertIn(name, signed)
                    self.assertFalse(any(name.lower().startswith('x-cos-meta-')
                                         for name in headers))
                    self.assertNotIn('x-cos-security-token', headers)
                    self.assertEqual(self.server.session_requests(), [])
            finally:
                client._session.close()

    def test_create_bucket_network_validation_before_transport(self):
        client = self.server.client()
        try:
            for name in RAPID_CREATE_NETWORK:
                for empty in (None, '', b'', '   ', b'\t'):
                    options = dict(RAPID_CREATE_NETWORK)
                    options[name] = empty
                    with self.assertRaises(CosClientError) as raised:
                        client.create_bucket(Bucket=RAPID_BUCKET, **options)
                    self.assertIn(name, str(raised.exception))
            with self.assertRaises(CosClientError) as raised:
                client.create_bucket(Bucket=RAPID_BUCKET)
            for name in RAPID_CREATE_NETWORK:
                self.assertIn(name, str(raised.exception))
            for metadata in ({'X-Cos-Vpc-Id': 'other-vpc'},
                             {'x-cos-vpc-id': 'vpc-test', 'X-Cos-Vpc-Id': 'other-vpc'}):
                with self.assertRaises(CosClientError) as raised:
                    client.create_bucket(Bucket=RAPID_BUCKET, Metadata=metadata, **RAPID_CREATE_NETWORK)
                self.assertIn('VpcId', str(raised.exception))
                self.assertIn('conflicting', str(raised.exception))
            for header in ('x-cos-vpc-id', 'x-cos-cidr-block', 'x-cos-subnet-id', 'x-cos-zone'):
                with self.assertRaises(CosClientError):
                    client.create_bucket(Bucket=RAPID_BUCKET, **{header: 'test'})
            self.assertEqual(self.server.state.requests, [])
        finally:
            client._session.close()

    def test_create_bucket_ordinary_isolation_and_global_mapping(self):
        client = self.server.client()
        try:
            client.create_bucket(ORDINARY_BUCKET, 'MAZ', 'OFS', ACL='private',
                                 Metadata={'X-Cos-Vpc-Id': 'legacy-header'})
            rec = self.server.object_requests()[-1]
            headers = requests.structures.CaseInsensitiveDict(rec['headers'])
            self.assertEqual(headers['x-cos-vpc-id'], 'legacy-header')
            self.assertEqual(headers['x-cos-acl'], 'private')
            self.assertIn(b'<BucketAZConfig>MAZ</BucketAZConfig>', rec['body'])
            self.assertIn(b'<BucketArchConfig>OFS</BucketArchConfig>', rec['body'])
            before = len(self.server.state.requests)
            for name, value in RAPID_CREATE_NETWORK.items():
                for supplied in (value, ''):
                    with self.assertRaises(CosClientError):
                        client.create_bucket(Bucket=ORDINARY_BUCKET, **{name: supplied})
                with self.assertRaises(CosClientError):
                    client.head_bucket(Bucket=RAPID_BUCKET, **{name: value})
            self.assertEqual(len(self.server.state.requests), before)
            self.assertEqual(self.server.session_requests(), [])
        finally:
            client._session.close()

    def test_create_bucket_metadata_missing_empty_and_conflicting(self):
        # NOCA:InnerIPLeak(Synthetic address for local tests; not production topology)
        network = {'x-cos-vpc-id': 'vpc-test', 'x-cos-cidr-block': '10.230.0.0/24',
                   'x-cos-subnet-id': 'subnet-test', 'x-cos-zone': 'ap-guangzhou-1'}
        client = self.server.client()
        try:
            for parameter, header in (('VpcId', 'x-cos-vpc-id'), ('CidrBlock', 'x-cos-cidr-block'),
                                      ('SubnetId', 'x-cos-subnet-id'), ('Zone', 'x-cos-zone')):
                for empty in (None, '', b'', '  '):
                    values = dict(network)
                    values[header] = empty
                    with self.assertRaises(CosClientError) as raised:
                        client.create_bucket(Bucket=RAPID_BUCKET, Metadata=values)
                    self.assertIn(parameter, str(raised.exception))
                values = dict(network)
                del values[header]
                with self.assertRaises(CosClientError) as raised:
                    client.create_bucket(Bucket=RAPID_BUCKET, Metadata=values)
                self.assertIn(parameter, str(raised.exception))
                values = dict(network)
                values[header.upper()] = 'different-value'
                with self.assertRaises(CosClientError) as raised:
                    client.create_bucket(Bucket=RAPID_BUCKET, Metadata=values)
                self.assertIn('conflicting', str(raised.exception))
                self.assertIn(parameter, str(raised.exception))
            self.assertEqual(self.server.state.requests, [])
        finally:
            client._session.close()

    def test_rapid_version_requests_fail_before_session_or_network(self):
        client = self.server.client()
        for version in ('old-version', '', 'null', None):
            for api in (client.get_object, client.head_object, client.delete_object):
                with self.assertRaises(CosClientError) as raised:
                    api(Bucket=RAPID_BUCKET, Key='object', VersionId=version)
                self.assertIn('VersionId', str(raised.exception))
            for objects in ([{'Key': 'object', 'VersionId': version}],
                            {'Key': 'object', 'VersionId': version}):
                with self.assertRaises(CosClientError):
                    client.delete_objects(Bucket=RAPID_BUCKET, Delete={'Object': objects})
            for presign in (client.get_presigned_url, client.get_session_presigned_url):
                with self.assertRaises(CosClientError):
                    presign(Bucket=RAPID_BUCKET, Key='object', Method='GET',
                            Params={'versionId': version})
        self.assertEqual(self.server.state.requests, [])

    def test_rapid_copy_rejects_cross_bucket_and_version_before_network(self):
        client = self.server.client()
        source = {'Bucket': RAPID_BUCKET, 'Region': 'ap-guangzhou', 'Key': 'source'}
        cases = [
            (RAPID_BUCKET, dict(source, VersionId='old-version')),
            (RAPID_BUCKET, dict(source, VersionId='')),
            ('another-x--1250000000', source),
            (ORDINARY_BUCKET, source),
            (RAPID_BUCKET, dict(source, Bucket=ORDINARY_BUCKET)),
        ]
        for destination, copy_source in cases:
            for api in (client.copy, client.copy_object, client.upload_part_copy):
                options = {'Bucket': destination, 'Key': 'destination', 'CopySource': copy_source}
                if api == client.upload_part_copy:
                    options.update(PartNumber=1, UploadId='upload')
                with self.assertRaises(CosClientError):
                    api(**options)
        self.assertEqual(self.server.state.requests, [])

    def test_rapid_callback_and_invalid_forbid_overwrite_fail_before_network(self):
        client = self.server.client()
        calls = [
            lambda options: client.put_object(Bucket=RAPID_BUCKET, Key='key', Body=b'x', **options),
            lambda options: client.create_multipart_upload(Bucket=RAPID_BUCKET, Key='key', **options),
            lambda options: client.complete_multipart_upload(
                Bucket=RAPID_BUCKET, Key='key', UploadId='upload',
                MultipartUpload={'Part': [{'PartNumber': 1, 'ETag': 'etag'}]}, **options),
            lambda options: client.rename_object(
                Bucket=RAPID_BUCKET, Key='key', RenameSource='source', **options),
        ]
        for options in ({'Callback': 'callback'}, {'CallbackVar': ''},
                        {'ForbidOverwrite': 'yes'}, {'ForbidOverwrite': 'True'},
                        {'ForbidOverwrite': True}, {'ForbidOverwrite': 1},
                        {'ForbidOverwrite': ''}):
            for call in calls:
                with self.assertRaises(CosClientError):
                    call(options)
        for headers in ({'X-Cos-Callback': 'callback'}, {'X-Cos-Forbid-Overwrite': 'yes'}):
            with self.assertRaises(CosClientError):
                client.get_session_presigned_url(Bucket=RAPID_BUCKET, Key='key', Method='PUT', Headers=headers)
        self.assertEqual(self.server.state.requests, [])

    def test_rapid_copy_normalizes_bucket_appid(self):
        client = self.server.client(Appid='1250000000')
        client.copy_object(Bucket=RAPID_BUCKET, Key='dst', CopySource={
            'Bucket': RAPID_BUCKET, 'Appid': '1250000000', 'Region': 'ap-guangzhou', 'Key': 'src'})
        self.assertEqual(len(self.server.object_requests()), 1)

    def test_rapid_mpu_forbid_overwrite_wire_headers_and_signature(self):
        client = self.server.client()
        header_name = 'x-cos-forbid-overwrite'
        for value, alias in (('true', False), ('false', False), (None, False),
                             (b'true', False), ('true', True), ('false', True)):
            self.server.state.requests[:] = []
            options = {}
            if value is not None:
                if alias:
                    options['Metadata'] = {'X-Cos-Forbid-Overwrite': value}
                else:
                    options['ForbidOverwrite'] = value
            self.server.state.object_body = (
                b'<InitiateMultipartUploadResult><UploadId>upload</UploadId>'
                b'</InitiateMultipartUploadResult>')
            result = client.create_multipart_upload(Bucket=RAPID_BUCKET, Key='mpu.bin', **options)
            self.server.state.object_body = (
                b'<CompleteMultipartUploadResult><ETag>final-etag</ETag>'
                b'</CompleteMultipartUploadResult>')
            client.complete_multipart_upload(
                Bucket=RAPID_BUCKET, Key='mpu.bin', UploadId=result['UploadId'],
                MultipartUpload={'Part': [{'PartNumber': 1, 'ETag': 'part-etag'}]}, **options)
            records = self.server.object_requests()
            self.assertEqual(len(records), 2)
            self.assertIn('uploads', records[0]['query'])
            self.assertEqual(records[1]['query']['uploadId'], ['upload'])
            for rec in records:
                self.assertEqual(rec['method'], 'POST')
                headers = requests.structures.CaseInsensitiveDict(rec['headers'])
                signature = dict(pair.split('=', 1) for pair in headers['Authorization'].split('&'))
                signed_headers = signature['q-header-list'].split(';')
                self.assertEqual(header_name in headers, value is not None)
                self.assertEqual(header_name in signed_headers, value is not None)
                if value is not None:
                    self.assertEqual(headers[header_name], value.decode('ascii') if isinstance(value, bytes) else value)
                self.assertIn('q-ak=' + SESSION_AK, headers['Authorization'])
        # A signed header is not evidence of CAM condition-policy enforcement.

    def test_ordinary_version_callback_and_copy_are_unchanged(self):
        client = self.server.client()
        client.delete_object(Bucket=ORDINARY_BUCKET, Key='object', VersionId='old-version')
        self.assertEqual(self.server.object_requests()[-1]['query']['versionId'], ['old-version'])
        client.put_object(Bucket=ORDINARY_BUCKET, Key='object', Body=b'x',
                          Callback='callback', CallbackVar='vars', ForbidOverwrite='yes')
        headers = self.server.object_requests()[-1]['headers']
        self.assertEqual(headers['x-cos-callback'], 'callback')
        self.assertEqual(headers['x-cos-callback-var'], 'vars')
        self.assertEqual(headers['x-cos-forbid-overwrite'], 'yes')
        client.copy_object(Bucket=ORDINARY_BUCKET, Key='object', CopySource={
            'Bucket': 'another-1250000000', 'Region': 'ap-guangzhou',
            'Key': 'source', 'VersionId': 'source-version'})
        self.assertIn('?versionId=source-version',
                      self.server.object_requests()[-1]['headers']['x-cos-copy-source'])
        self.server.state.object_body = b'<DeleteResult/>'
        client.delete_objects(Bucket=ORDINARY_BUCKET, Delete={'Object': [
            {'Key': 'object', 'VersionId': 'old-version'}]})
        self.assertIn(b'<VersionId>old-version</VersionId>', self.server.object_requests()[-1]['body'])
        self.assertEqual(self.server.session_requests(), [])

    def test_rapid_list_pages_reuse_relative_marker(self):
        client = self.server.client()
        self.server.state.object_body = (
            b'<ListBucketResult><EncodingType>url</EncodingType><Prefix>dir/</Prefix>'
            b'<IsTruncated>true</IsTruncated><NextMarker>a%20b%2B</NextMarker>'
            b'<Contents><Key>dir/a%20b%2B</Key></Contents></ListBucketResult>')
        first = client.list_objects(Bucket=RAPID_BUCKET, Prefix='dir/', MaxKeys=1)
        self.assertEqual(first['Contents'][0]['Key'], 'dir/a b+')
        self.assertEqual(first['NextMarker'], 'a b+')
        self.server.state.object_body = (
            b'<ListBucketResult><EncodingType>url</EncodingType>'
            b'<IsTruncated>false</IsTruncated><Contents><Key>dir/z</Key></Contents></ListBucketResult>')
        second = client.list_objects(Bucket=RAPID_BUCKET, Prefix='dir/',
                                     Marker=first['NextMarker'], MaxKeys=1)
        self.assertEqual(second['Contents'][0]['Key'], 'dir/z')
        query = self.server.object_requests()[-1]['query']
        self.assertEqual(query['marker'], ['a b+'])
        self.assertEqual(query['prefix'], ['dir/'])

    def test_rapid_dot_segments_rejected_before_http_normalization(self):
        client = self.server.client()
        for key in ('a/../b', 'a/./b', 'a/..', 'a/.'):
            for api in (client.delete_object, client.head_object, client.get_object):
                with self.assertRaises(CosClientError):
                    api(Bucket=RAPID_BUCKET, Key=key)
            with self.assertRaises(CosClientError):
                client.rename_object(Bucket=RAPID_BUCKET, Key='dst', RenameSource=key)
            with self.assertRaises(CosClientError):
                client.copy(Bucket=RAPID_BUCKET, Key='dst', CopySource={
                    'Bucket': RAPID_BUCKET, 'Key': key, 'Region': 'ap-guangzhou'})
            with self.assertRaises(CosClientError):
                client.get_presigned_url(Bucket=RAPID_BUCKET, Key=key, Method='DELETE')
        self.assertEqual(self.server.state.requests, [])
        for key in ('a/%2E%2E/b', '.hidden', 'a.../b', 'dir/'):
            url = client._conf.uri(bucket=RAPID_BUCKET, path=key)
            prepared = requests.Request('DELETE', url).prepare()
            self.assertEqual(unquote(urlparse(prepared.url).path), '/' + key)
        # Ordinary COS keeps its existing URL construction, including dot keys.
        self.assertTrue(client._conf.uri(bucket=ORDINARY_BUCKET, path='a/..').endswith('/a/..'))

    def test_bucket_scoped_control_plane_calls_mark_proxy_transport(self):
        client = self.server.client()
        captured = []

        class RequestCaptured(Exception):
            pass

        def capture(*_args, **kwargs):
            captured.append(kwargs)
            raise RequestCaptured()

        client.send_request = capture
        calls = [
            lambda: client.create_session(Bucket=RAPID_BUCKET),
            lambda: client.create_bucket(Bucket=RAPID_BUCKET, **RAPID_CREATE_NETWORK),
            lambda: client.delete_bucket(Bucket=RAPID_BUCKET),
            lambda: client.head_bucket(Bucket=RAPID_BUCKET),
            lambda: client.put_bucket_policy(Bucket=RAPID_BUCKET, Policy={}),
            lambda: client.get_bucket_policy(Bucket=RAPID_BUCKET),
            lambda: client.delete_bucket_policy(Bucket=RAPID_BUCKET),
        ]
        for call in calls:
            with self.assertRaises(RequestCaptured):
                call()
        self.assertEqual(len(captured), len(calls))
        for kwargs in captured:
            self.assertTrue(kwargs.get('skip_session_auth'))
            self.assertTrue(kwargs.get('_rapid_control_request'))

    def test_rapid_list_buckets_uses_service_domain_without_bucket(self):
        conf = CosConfig(
            Region='ap-nanjing', SecretId=BASE_AK, SecretKey=BASE_SK,
            Scheme='http', EnableRapidDomain=True)
        client = CosS3Client(conf, session=requests.Session())
        captured = {}

        class RequestCaptured(Exception):
            pass

        def capture(*_args, **kwargs):
            captured.update(kwargs)
            raise RequestCaptured()

        client.send_request = capture
        with self.assertRaises(RequestCaptured):
            client.list_buckets()
        self.assertEqual(
            captured['url'],
            'http://service.cosrapid.ap-nanjing.myqcloud.com/')
        self.assertIsNone(captured['bucket'])

    def test_ordinary_list_buckets_keeps_original_service_domain(self):
        conf = CosConfig(
            Region='ap-nanjing', SecretId=BASE_AK, SecretKey=BASE_SK,
            Scheme='http')
        client = CosS3Client(conf, session=requests.Session())
        captured = {}

        class RequestCaptured(Exception):
            pass

        def capture(*_args, **kwargs):
            captured.update(kwargs)
            raise RequestCaptured()

        client.send_request = capture
        with self.assertRaises(RequestCaptured):
            client.list_buckets()
        self.assertEqual(
            captured['url'], 'http://service.cos.myqcloud.com/')

    def test_credential_instance_token_is_used_only_for_create_session(self):
        class CredentialInstance(object):
            secret_id = BASE_AK
            secret_key = BASE_SK
            # NOCA:PasswordLeak(Synthetic credential for local test fixtures; not a real account)
            token = 'base-session-token'

        conf = CosConfig(
            Region='ap-guangzhou', CredentialInstance=CredentialInstance(),
            Scheme='http', Domain='127.0.0.1:%s' % self.server.port,
            EnableSessionAuth=True, KeepAlive=False, Timeout=5)
        client = CosS3Client(conf, retry=0, session=requests.Session())
        client.create_session(Bucket=RAPID_BUCKET)
        sessions = self.server.session_requests()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(
            sessions[0]['headers'].get('x-cos-security-token'),
            'base-session-token')
        auth = (sessions[0]['headers'].get('Authorization')
                or sessions[0]['headers'].get('authorization'))
        self.assertIn('q-ak=' + BASE_AK, auth)

    def test_unsupported_rapid_apis_fail_before_session_or_network(self):
        client = self.server.client()
        calls = [
            lambda: client.put_object_acl(
                Bucket=RAPID_BUCKET, Key='a.txt', ACL='private'),
            lambda: client.get_object_acl(Bucket=RAPID_BUCKET, Key='a.txt'),
            lambda: client.put_object_tagging(
                Bucket=RAPID_BUCKET, Key='a.txt',
                Tagging={'TagSet': {'Tag': {'Key': 'k', 'Value': 'v'}}}),
            lambda: client.get_object_tagging(Bucket=RAPID_BUCKET, Key='a.txt'),
            lambda: client.delete_object_tagging(Bucket=RAPID_BUCKET, Key='a.txt'),
            lambda: client.list_objects_versions(Bucket=RAPID_BUCKET),
        ]
        for call in calls:
            with self.assertRaises(CosClientError) as caught:
                call()
            self.assertIn('not supported for rapid bucket', str(caught.exception))
        self.assertEqual(self.server.state.requests, [])

    def test_unsupported_api_guard_does_not_change_ordinary_bucket(self):
        client = self.server.client()
        client.delete_object_tagging(Bucket=ORDINARY_BUCKET, Key='a.txt')
        self.assertEqual(len(self.server.session_requests()), 0)
        requests_seen = self.server.object_requests()
        self.assertEqual(len(requests_seen), 1)
        self.assertEqual(requests_seen[0]['method'], 'DELETE')

    def test_rapid_list_objects_defaults_delimiter_without_changing_ordinary_bucket(self):
        client = self.server.client()
        captured = []

        class RequestCaptured(Exception):
            pass

        def capture(*_args, **kwargs):
            captured.append(kwargs)
            raise RequestCaptured()

        client.send_request = capture
        with self.assertRaises(RequestCaptured):
            client.list_objects(Bucket=RAPID_BUCKET)
        with self.assertRaises(RequestCaptured):
            client.list_objects(Bucket=ORDINARY_BUCKET)
        self.assertEqual(captured[0]['params']['delimiter'], b'/')
        self.assertEqual(captured[1]['params']['delimiter'], b'')

    def _encoded_list_response(self, client, api, wire, declared=True, **kwargs):
        opaque_id = 'upload+id%25%2F'
        fields = {
            'list_objects': '<Prefix>{w}</Prefix><Marker>{w}</Marker><NextMarker>{w}</NextMarker>'
                            '<Delimiter>%2F</Delimiter><Contents><Key>{w}</Key></Contents>'
                            '<CommonPrefixes><Prefix>{w}</Prefix></CommonPrefixes>',
            'list_parts': '<Key>{w}</Key><UploadId>{id}</UploadId>',
            'list_multipart_uploads': '<Prefix></Prefix><KeyMarker>{w}</KeyMarker>'
                                      '<NextKeyMarker>{w}</NextKeyMarker><Delimiter></Delimiter>'
                                      '<UploadIdMarker>{id}</UploadIdMarker>'
                                      '<NextUploadIdMarker>{id}</NextUploadIdMarker>'
                                      '<Upload><Key>{w}</Key><UploadId>{id}</UploadId></Upload>',
        }[api].format(w=wire, id=opaque_id)
        response = requests.Response()
        response.status_code = 200
        response._content = ('<Result>' + ('<EncodingType>url</EncodingType>' if declared else '')
                             + fields + '</Result>').encode('utf-8')
        client.send_request = lambda *_args, **_kwargs: response
        if api == 'list_parts':
            kwargs.update(Key='key', UploadId=opaque_id)
        return getattr(client, api)(**kwargs)

    def test_rapid_list_query_encoding_preserves_names_and_opaque_upload_ids(self):
        client = self.server.client()
        name = u'目录/空 格+literal%25%2F'
        wire = quote_plus(name.encode('utf-8'))
        if sys.version_info[0] == 2:
            name = name.encode('utf-8')  # Preserve the SDK's Python 2 byte-string contract.
        result = self._encoded_list_response(client, 'list_objects', wire, Bucket=RAPID_BUCKET)
        for key in ('Prefix', 'Marker', 'NextMarker'):
            self.assertEqual(result[key], name)
        self.assertEqual(result['Delimiter'], '/')
        self.assertEqual(result['Contents'][0]['Key'], name)
        self.assertEqual(result['CommonPrefixes'][0]['Prefix'], name)
        result = self._encoded_list_response(client, 'list_parts', wire, Bucket=RAPID_BUCKET)
        self.assertEqual(result['Key'], name)
        self.assertEqual(result['UploadId'], 'upload+id%25%2F')
        result = self._encoded_list_response(client, 'list_multipart_uploads', wire, Bucket=RAPID_BUCKET)
        for key in ('KeyMarker', 'NextKeyMarker'):
            self.assertEqual(result[key], name)
        for key in ('UploadIdMarker', 'NextUploadIdMarker'):
            self.assertEqual(result[key], 'upload+id%25%2F')
        self.assertEqual(result['Upload'][0]['Key'], name)
        self.assertEqual(result['Upload'][0]['UploadId'], 'upload+id%25%2F')

    def test_list_query_decoding_is_limited_to_declared_rapid_responses(self):
        client = self.server.client()
        for api, field in (('list_objects', 'Prefix'), ('list_parts', 'Key'),
                           ('list_multipart_uploads', 'KeyMarker')):
            for bucket, declared in ((ORDINARY_BUCKET, True), (RAPID_BUCKET, False)):
                result = self._encoded_list_response(client, api, 'a+b%2Bc%252F',
                                                     declared=declared, Bucket=bucket)
                self.assertEqual(result[field], 'a+b+c%2F')
            for bucket in (RAPID_BUCKET, ORDINARY_BUCKET):
                result = self._encoded_list_response(client, api, 'a+b%2Bc%252F',
                                                     Bucket=bucket, EncodingType='url')
                self.assertEqual(result[field], 'a+b%2Bc%252F')

    def test_rapid_standard_list_xml_decodes_names_once(self):
        # Gateway MR !27 uses %20 for spaces and leaves path separators literal.
        # Keep a fixed wire value rather than deriving the oracle with a URL encoder.
        name = u'dir/a b+c%20中文&<>.txt'
        wire = 'dir/a%20b%2Bc%2520%E4%B8%AD%E6%96%87%26%3C%3E.txt'
        opaque = 'upload+id%25%2F'
        if sys.version_info[0] == 2:
            name = name.encode('utf-8')
        bodies = {
            'list_objects': (
                '<ListBucketResult><EncodingType>url</EncodingType>'
                '<Prefix>dir/</Prefix><Delimiter>/</Delimiter>'
                '<Marker>{w}</Marker><NextMarker>{w}</NextMarker>'
                '<MaxKeys>1</MaxKeys><IsTruncated>true</IsTruncated>'
                '<Contents><Key>{w}</Key></Contents></ListBucketResult>'),
            'list_parts': (
                '<ListPartsResult><EncodingType>url</EncodingType><Key>{w}</Key>'
                '<UploadId>{id}</UploadId><PartNumberMarker>1</PartNumberMarker>'
                '<NextPartNumberMarker>2</NextPartNumberMarker><MaxParts>1</MaxParts>'
                '<IsTruncated>true</IsTruncated><Part><PartNumber>2</PartNumber>'
                '<Size>1</Size></Part></ListPartsResult>'),
            'list_multipart_uploads': (
                '<ListMultipartUploadsResult><EncodingType>url</EncodingType>'
                '<KeyMarker>{w}</KeyMarker><NextKeyMarker>{w}</NextKeyMarker>'
                '<UploadIdMarker>{id}</UploadIdMarker>'
                '<NextUploadIdMarker>{id}</NextUploadIdMarker>'
                '<MaxUploads>1</MaxUploads><IsTruncated>true</IsTruncated>'
                '<Upload><Key>{w}</Key><UploadId>{id}</UploadId></Upload>'
                '</ListMultipartUploadsResult>'),
        }
        for api, body in bodies.items():
            for explicit in (False, True):
                client = self.server.client()
                response = requests.Response()
                response.status_code = 200
                response._content = body.format(w=wire, id=opaque).encode('utf-8')
                requests_seen = []

                def respond(*_args, **kwargs):
                    requests_seen.append(kwargs)
                    return response

                client.send_request = respond
                kwargs = {'Bucket': RAPID_BUCKET}
                if explicit:
                    kwargs['EncodingType'] = 'url'
                if api == 'list_parts':
                    kwargs.update(Key=name, UploadId=opaque)
                result = getattr(client, api)(**kwargs)
                self.assertEqual(requests_seen[0]['params']['encoding-type'], b'url')
                self.assertEqual(result['EncodingType'], 'url')
                expected = wire if explicit else name
                if api == 'list_objects':
                    self.assertEqual(result['Contents'][0]['Key'], expected)
                    self.assertEqual(result['Marker'], expected)
                    self.assertEqual(result['NextMarker'], expected)
                    self.assertEqual(result['Prefix'], 'dir/')
                    self.assertEqual(result['Delimiter'], '/')
                    self.assertFalse(result.get('CommonPrefixes'))
                elif api == 'list_parts':
                    self.assertEqual(result['Key'], expected)
                    self.assertEqual(result['UploadId'], opaque)
                    self.assertEqual(result['PartNumberMarker'], '1')
                    self.assertEqual(result['NextPartNumberMarker'], '2')
                    self.assertEqual(result['Part'][0]['PartNumber'], '2')
                else:
                    self.assertEqual(result['Upload'][0]['Key'], expected)
                    self.assertEqual(result['Upload'][0]['UploadId'], opaque)
                    self.assertEqual(result['KeyMarker'], expected)
                    self.assertEqual(result['NextKeyMarker'], expected)
                    self.assertEqual(result['UploadIdMarker'], opaque)
                    self.assertEqual(result['NextUploadIdMarker'], opaque)

    def test_rapid_standard_common_prefixes_preserve_each_directory(self):
        for count in (0, 1, 3):
            for explicit in (False, True):
                wire_names = ['parent/a%20b/', 'parent/c%2Bd/', 'parent/e%2520f/'][:count]
                names = ['parent/a b/', 'parent/c+d/', 'parent/e%20f/'][:count]
                response = requests.Response()
                response.status_code = 200
                response._content = (
                    '<ListBucketResult><EncodingType>url</EncodingType>'
                    '<Prefix>parent/</Prefix><Delimiter>/</Delimiter>'
                    '<MaxKeys>3</MaxKeys><IsTruncated>false</IsTruncated>'
                    + ''.join(
                        '<CommonPrefixes><Prefix>{0}</Prefix></CommonPrefixes>'.format(n)
                        for n in wire_names) + '</ListBucketResult>').encode('utf-8')
                client = self.server.client()
                client.send_request = lambda *_args, **_kwargs: response
                kwargs = {'Bucket': RAPID_BUCKET, 'Prefix': 'parent/'}
                if explicit:
                    kwargs['EncodingType'] = 'url'
                result = client.list_objects(**kwargs)
                self.assertEqual([p['Prefix'] for p in result.get('CommonPrefixes', [])],
                                 wire_names if explicit else names)

    def test_rapid_response_normalizes_etag_without_changing_ordinary_bucket(self):
        client = self.server.client()
        rapid = client._response_headers(RAPID_BUCKET, {'Etag': 'etag-value'})
        ordinary = client._response_headers(
            ORDINARY_BUCKET, {'Etag': 'etag-value'})
        self.assertEqual(rapid['ETag'], 'etag-value')
        self.assertNotIn('ETag', ordinary)

    def test_rapid_public_responses_accept_header_case_variants(self):
        client = self.server.client()
        expected = {
            'Content-Length': '3',
            'Last-Modified': 'Fri, 04 Sep 2026 00:00:00 GMT',
            'ETag': '"etag-value"',
            'Content-Range': 'bytes 0-2/9',
            'Content-Type': 'application/octet-stream',
            'x-cos-request-id': 'request-mixed',
            'x-cos-trace-id': 'trace-mixed',
            'x-cos-meta-userkey': 'Preserved Value',
            'x-unrecognized-header': 'opaque',
        }
        response = requests.Response()
        response.status_code = 200
        response._content = b'abc'
        client.send_request = lambda *_args, **_kwargs: response
        calls = [
            lambda: client.head_bucket(Bucket=RAPID_BUCKET),
            lambda: client.head_object(Bucket=RAPID_BUCKET, Key='a.txt'),
            lambda: client.get_object(Bucket=RAPID_BUCKET, Key='a.txt'),
            lambda: client.put_object(Bucket=RAPID_BUCKET, Key='a.txt', Body=b'abc'),
            lambda: client.upload_part(Bucket=RAPID_BUCKET, Key='a.txt', Body=b'abc',
                                       PartNumber=1, UploadId='upload-1'),
            lambda: client.delete_object(Bucket=RAPID_BUCKET, Key='a.txt'),
            lambda: client.rename_object(Bucket=RAPID_BUCKET, Key='b.txt', RenameSource='a.txt'),
        ]
        for transform in (lambda value: value, str.lower, str.upper, str.title, str.swapcase):
            wire = dict((transform(key), value) for key, value in expected.items())
            response.headers = requests.structures.CaseInsensitiveDict(wire)
            for call in calls:
                result = call()
                self.assertIs(type(result), dict)
                for key, value in expected.items():
                    self.assertEqual(result[key], value, key)
                    self.assertEqual(result[key.lower()], value, key)
                for key, value in wire.items():
                    self.assertEqual(result[key], value, key)
            self.assertEqual(dict(response.headers), wire)
            self.assertEqual(client._response_headers(ORDINARY_BUCKET, response.headers), wire)
            self.assertEqual(client.head_bucket(Bucket=ORDINARY_BUCKET), wire)
            self.assertEqual(client.delete_object(Bucket=ORDINARY_BUCKET, Key='a.txt'), wire)

    def test_rapid_xml_responses_keep_body_fields_separate_from_headers(self):
        client = self.server.client()
        response = requests.Response()
        response.status_code = 200
        response.headers = requests.structures.CaseInsensitiveDict({
            'X-Cos-Request-Id': 'request-copy', 'eTAG': '"wire-etag"',
            'last-modified': 'Fri, 04 Sep 2026 00:00:00 GMT',
        })
        response._content = (
            b'<CopyObjectResult><ETag>"xml-etag"</ETag>'
            b'<LastModified>2026-09-04T00:00:00Z</LastModified></CopyObjectResult>')
        client.send_request = lambda *_args, **_kwargs: response
        source = {'Bucket': RAPID_BUCKET, 'Region': 'ap-guangzhou', 'Key': 'source'}
        calls = [
            lambda: client.copy_object(Bucket=RAPID_BUCKET, Key='copy', CopySource=source),
            lambda: client.upload_part_copy(Bucket=RAPID_BUCKET, Key='copy', CopySource=source,
                                            PartNumber=1, UploadId='upload-1'),
            lambda: client.complete_multipart_upload(
                Bucket=RAPID_BUCKET, Key='copy', UploadId='upload-1',
                MultipartUpload={'Part': [{'PartNumber': 1, 'ETag': 'part'}]}),
        ]
        for call in calls:
            result = call()
            self.assertEqual(result['ETag'], '"xml-etag"')
            self.assertEqual(result['LastModified'], '2026-09-04T00:00:00Z')
            self.assertEqual(result['Last-Modified'], 'Fri, 04 Sep 2026 00:00:00 GMT')
            self.assertEqual(result['x-cos-request-id'], 'request-copy')
            self.assertNotIn('lastmodified', result)

    def test_rapid_xml_error_preserves_header_request_id(self):
        client = self.server.client()
        response = requests.Response()
        response.status_code = 200
        response.headers = requests.structures.CaseInsensitiveDict({'X-Cos-Request-Id': 'request-xml-error'})
        response._content = b'<Error><Code>InternalError</Code><Message>failed</Message></Error>'
        client.send_request = lambda *_args, **_kwargs: response
        source = {'Bucket': RAPID_BUCKET, 'Region': 'ap-guangzhou', 'Key': 'source'}
        for call in (
            lambda: client.copy_object(Bucket=RAPID_BUCKET, Key='copy', CopySource=source),
            lambda: client.complete_multipart_upload(Bucket=RAPID_BUCKET, Key='copy', UploadId='upload-1',
                                                     MultipartUpload={'Part': [{'PartNumber': 1, 'ETag': 'part'}]}),
        ):
            with self.assertRaises(CosServiceError) as caught:
                call()
            self.assertEqual(caught.exception.get_request_id(), 'request-xml-error')
            self.assertEqual(caught.exception.get_origin_msg(), response.content)

    def test_rapid_error_request_id_survives_head_and_incomplete_xml(self):
        self.server.state.object_status = 404
        self.server.state.object_body = b'<Error><Code>NoSuchKey</Code><Message>missing</Message></Error>'
        self.server.state.object_headers = {
            'X-COS-REQUEST-ID': 'request-error', 'X-Cos-Trace-Id': 'trace-error',
        }
        client = self.server.client()
        for call in (client.head_object, client.get_object):
            with self.assertRaises(CosServiceError) as caught:
                call(Bucket=RAPID_BUCKET, Key='missing')
            self.assertEqual(caught.exception.get_request_id(), 'request-error')
            self.assertEqual(caught.exception.get_trace_id(), 'trace-error')

    def test_rapid_error_request_id_survives_empty_body(self):
        self.server.state.object_status = 403
        self.server.state.object_body = b''
        self.server.state.object_headers = {'X-Cos-Request-Id': 'request-empty'}
        with self.assertRaises(CosServiceError) as caught:
            self.server.client().get_object(Bucket=RAPID_BUCKET, Key='denied')
        self.assertEqual(caught.exception.get_request_id(), 'request-empty')

    def test_service_error_ids_prefer_body_and_handle_missing_fields(self):
        error = CosServiceError('GET', {
            'code': 'NoSuchKey', 'message': 'missing', 'resource': '/missing',
            'requestid': 'body-request', 'traceid': 'body-trace',
        }, 404, headers={'X-Cos-Request-Id': 'header-request', 'X-Cos-Trace-Id': 'header-trace'})
        self.assertEqual(error.get_request_id(), 'body-request')
        self.assertEqual(error.get_trace_id(), 'body-trace')
        for body in ({'code': 'NoSuchResource'}, b'<Error></Error>'):
            error = CosServiceError('HEAD', body, 404)
            self.assertEqual(error.get_request_id(), 'Unknown')
            self.assertEqual(error.get_trace_id(), 'Unknown')

    def test_service_error_xml_optional_fields_preserve_code_and_message(self):
        headers = {'X-Cos-Request-Id': 'header-request', 'X-Cos-Trace-Id': 'header-trace'}
        for resource in ('', '<Resource/>', '<Resource></Resource>'):
            for request in ('', '<RequestId/>', '<RequestId></RequestId>'):
                body = ('<Error><Code>InvalidArgument</Code>'
                        '<Message>prefix must end with /</Message>' + resource + request
                        + '<TraceId/></Error>').encode('utf-8')
                error = CosServiceError('GET', body, 400, headers=headers)
                self.assertEqual(error.get_status_code(), 400)
                self.assertEqual(error.get_error_code(), 'InvalidArgument')
                self.assertEqual(error.get_error_msg(), 'prefix must end with /')
                self.assertEqual(error.get_resource_location(), 'Unknown')
                self.assertEqual(error.get_request_id(), 'header-request')
                self.assertEqual(error.get_trace_id(), 'header-trace')
                self.assertEqual(error.get_origin_msg(), body)
                without_headers = CosServiceError('GET', body, 400)
                self.assertEqual(without_headers.get_request_id(), 'Unknown')
                self.assertEqual(without_headers.get_trace_id(), 'Unknown')

    def test_service_error_xml_complete_fields_and_json_remain_compatible(self):
        fields = {'code': 'InvalidArgument', 'message': 'bad prefix', 'resource': '/',
                  'requestid': 'body-request', 'traceid': 'body-trace'}
        xml = (b'<Error><Code>InvalidArgument</Code><Message>bad prefix</Message>'
               b'<Resource>/</Resource><RequestId>body-request</RequestId>'
               b'<TraceId>body-trace</TraceId></Error>')
        for body in (xml, json.dumps(fields), fields):
            error = CosServiceError('GET', body, 400, headers={
                'X-Cos-Request-Id': 'header-request', 'X-Cos-Trace-Id': 'header-trace'})
            self.assertEqual(error.get_digest_msg(), fields)
            self.assertEqual(error.get_request_id(), 'body-request')
            self.assertEqual(error.get_trace_id(), 'body-trace')

    def test_service_error_malformed_or_missing_required_fields_stay_invalid(self):
        for body in (b'', b'<Error>', b'<Error><Code>InvalidArgument</Code></Error>',
                     b'<Error><Message>bad prefix</Message></Error>'):
            error = CosServiceError('GET', body, 400,
                                    headers={'X-Cos-Request-Id': 'header-request'})
            self.assertEqual(error.get_error_code(), 'Unknown')
            self.assertEqual(error.get_error_msg(), 'Unknown')
            self.assertEqual(error.get_request_id(), 'header-request')

    def test_http_error_with_empty_resource_preserves_details_for_both_bucket_types(self):
        self.server.state.object_status = 400
        self.server.state.object_body = (
            b'<Error><Code>InvalidArgument</Code><Message>bad prefix</Message>'
            b'<Resource></Resource><RequestId>body-request</RequestId><TraceId/></Error>')
        self.server.state.object_headers = {'X-Cos-Request-Id': 'header-request'}
        client = self.server.client()
        for bucket in (RAPID_BUCKET, ORDINARY_BUCKET):
            with self.assertRaises(CosServiceError) as caught:
                client.get_object(Bucket=bucket, Key='missing')
            self.assertEqual(caught.exception.get_status_code(), 400)
            self.assertEqual(caught.exception.get_error_code(), 'InvalidArgument')
            self.assertEqual(caught.exception.get_error_msg(), 'bad prefix')
            self.assertEqual(caught.exception.get_request_id(), 'body-request')

    def test_resumable_upload_lookup_avoids_unsupported_rapid_prefix(self):
        client = self.server.client()
        calls = []
        responses = [
            {
                'Upload': [
                    {'Key': 'other', 'UploadId': 'other-1'},
                    {'Key': 'dir/big.bin', 'UploadId': 'upload-old'},
                ],
                'IsTruncated': 'true',
                'NextKeyMarker': 'dir/big.bin',
                'NextUploadIdMarker': 'upload-old',
            },
            {
                'Upload': [
                    {'Key': 'dir/big.bin', 'UploadId': 'upload-new'},
                ],
                'IsTruncated': 'false',
            },
        ]

        def list_rapid(**kwargs):
            calls.append(kwargs)
            return responses.pop(0)

        client.list_multipart_uploads = list_rapid
        upload_id = client._get_resumable_uploadid(
            RAPID_BUCKET, '/dir/big.bin')
        self.assertEqual(upload_id, 'upload-new')
        self.assertEqual(len(calls), 2)
        self.assertNotIn('Prefix', calls[0])
        self.assertEqual(calls[0]['KeyMarker'], '')
        self.assertEqual(calls[0]['UploadIdMarker'], '')
        self.assertNotIn('Prefix', calls[1])
        self.assertEqual(calls[1]['KeyMarker'], 'dir/big.bin')
        self.assertEqual(calls[1]['UploadIdMarker'], 'upload-old')

        ordinary_calls = []

        def list_ordinary(**kwargs):
            ordinary_calls.append(kwargs)
            return {'Upload': [], 'IsTruncated': 'false'}

        client.list_multipart_uploads = list_ordinary
        self.assertIsNone(client._get_resumable_uploadid(
            ORDINARY_BUCKET, 'ordinary.bin'))
        self.assertEqual(
            ordinary_calls, [{'Bucket': ORDINARY_BUCKET,
                              'Prefix': 'ordinary.bin'}])

    def test_resumable_upload_lookup_rejects_stalled_rapid_pagination(self):
        client = self.server.client()
        client.list_multipart_uploads = lambda **_kwargs: {
            'Upload': [],
            'IsTruncated': 'true',
            'NextKeyMarker': '',
            'NextUploadIdMarker': '',
        }
        with self.assertRaises(CosClientError):
            client._get_resumable_uploadid(RAPID_BUCKET, 'big.bin')

    def test_resumable_upload_lookup_preserves_ordinary_latest_match(self):
        client = self.server.client()
        calls = []

        def list_ordinary(**kwargs):
            calls.append(kwargs)
            return {
                'Upload': [
                    {'Key': 'ordinary.bin', 'UploadId': 'upload-old'},
                    {'Key': 'ordinary.bin', 'UploadId': 'upload-new'},
                    {'Key': 'ordinary.bin.suffix', 'UploadId': 'other'},
                ],
                'IsTruncated': 'false',
            }

        client.list_multipart_uploads = list_ordinary
        self.assertEqual(
            client._get_resumable_uploadid(
                ORDINARY_BUCKET, '/ordinary.bin'),
            'upload-new')
        self.assertEqual(
            calls, [{'Bucket': ORDINARY_BUCKET, 'Prefix': 'ordinary.bin'}])

    def test_supported_rapid_methods_pass_the_explicit_data_plane_marker(self):
        client = self.server.client()
        copy_source = {
            'Bucket': RAPID_BUCKET, 'Key': 'src.txt',
            'Region': 'ap-guangzhou'}
        calls = [
            lambda: client.put_object(Bucket=RAPID_BUCKET, Key='k', Body=b'x'),
            lambda: client.get_object(Bucket=RAPID_BUCKET, Key='k'),
            lambda: client.head_object(Bucket=RAPID_BUCKET, Key='k'),
            lambda: client.delete_object(Bucket=RAPID_BUCKET, Key='k'),
            lambda: client.delete_objects(
                Bucket=RAPID_BUCKET, Delete={'Object': [{'Key': 'k'}]}),
            lambda: client.copy_object(
                Bucket=RAPID_BUCKET, Key='k', CopySource=copy_source),
            lambda: client.upload_part_copy(
                Bucket=RAPID_BUCKET, Key='k', PartNumber=1,
                UploadId='upload', CopySource=copy_source),
            lambda: client.create_multipart_upload(Bucket=RAPID_BUCKET, Key='k'),
            lambda: client.upload_part(
                Bucket=RAPID_BUCKET, Key='k', Body=b'x',
                PartNumber=1, UploadId='upload'),
            lambda: client.complete_multipart_upload(
                Bucket=RAPID_BUCKET, Key='k', UploadId='upload',
                MultipartUpload={'Part': [{'PartNumber': 1, 'ETag': 'etag'}]}),
            lambda: client.abort_multipart_upload(
                Bucket=RAPID_BUCKET, Key='k', UploadId='upload'),
            lambda: client.list_parts(
                Bucket=RAPID_BUCKET, Key='k', UploadId='upload'),
            lambda: client.list_objects(Bucket=RAPID_BUCKET),
            lambda: client.list_multipart_uploads(Bucket=RAPID_BUCKET),
            lambda: client.rename_object(
                Bucket=RAPID_BUCKET, Key='dst', RenameSource='src'),
            lambda: client._head_object_when_copy(copy_source),
        ]

        class RequestCaptured(Exception):
            pass

        for call in calls:
            captured = {}

            def capture(*_args, **kwargs):
                captured.update(kwargs)
                raise RequestCaptured()

            client.send_request = capture
            with self.assertRaises(RequestCaptured):
                call()
            self.assertTrue(captured.get('_rapid_data_request'))

        captured = {}

        def capture_rename(*_args, **kwargs):
            captured.update(kwargs)
            raise RequestCaptured()

        client.send_request = capture_rename
        with self.assertRaises(RequestCaptured):
            client.rename_object(
                Bucket=RAPID_BUCKET, Key='dst', RenameSource='src')
        self.assertFalse(captured.get('_retry_ambiguous'))

    def test_supported_rapid_methods_preserve_success_response_shapes(self):
        self.server.state.object_headers = {
            'Etag': '"rapid-etag"',
            'x-cos-request-id': 'req-object',
        }
        client = self.server.client()

        got = client.get_object(Bucket=RAPID_BUCKET, Key='a.txt')
        self.assertEqual(got['ETag'], '"rapid-etag"')
        self.assertEqual(got['Etag'], '"rapid-etag"')
        self.assertEqual(got['x-cos-request-id'], 'req-object')
        self.assertEqual(got['Body'].read(), b'ok')

        head = client.head_object(Bucket=RAPID_BUCKET, Key='a.txt')
        self.assertEqual(head['ETag'], '"rapid-etag"')
        self.assertEqual(head['Content-Length'], '2')

        part = client.upload_part(
            Bucket=RAPID_BUCKET, Key='a.txt', Body=b'hello',
            PartNumber=1, UploadId='upload-1')
        self.assertEqual(part['ETag'], '"rapid-etag"')
        self.assertEqual(part['x-cos-request-id'], 'req-object')

        put = client.put_object(Bucket=RAPID_BUCKET, Key='a.txt', Body=b'hello')
        self.assertEqual(put['ETag'], '"rapid-etag"')

        # POST 数据面（批量删除）必须解析 XML 结果而不是返回原始响应。
        self.server.state.object_body = (
            b'<DeleteResult><Deleted><Key>a.txt</Key></Deleted></DeleteResult>')
        deleted = client.delete_objects(
            Bucket=RAPID_BUCKET, Delete={'Object': [{'Key': 'a.txt'}]})
        self.assertEqual(deleted['Deleted'], [{'Key': 'a.txt'}])
        self.assertEqual(self.server.object_requests()[-1]['method'], 'POST')

        # 数据面共用一个 session；且普通桶不得被补上 ETag 契约键。
        self.assertEqual(len(self.server.session_requests()), 1)
        ordinary = client.head_object(Bucket=ORDINARY_BUCKET, Key='a.txt')
        self.assertEqual(ordinary['Etag'], '"rapid-etag"')
        self.assertNotIn('ETag', ordinary)
        self.assertEqual(len(self.server.session_requests()), 1)

    def test_rapid_parameter_validation_fails_before_network(self):
        client = self.server.client()
        cases = [
            (lambda: client.create_session(Bucket=ORDINARY_BUCKET),
             'only supported on rapid bucket'),
            (lambda: client.rename_object(
                Bucket=RAPID_BUCKET, Key='', RenameSource='src'),
             'empty object name'),
            (lambda: client.rename_object(
                Bucket=RAPID_BUCKET, Key='/', RenameSource='src'),
             'empty object name'),
            (lambda: client.rename_object(
                Bucket=RAPID_BUCKET, Key='dst', RenameSource=''),
             'empty rename source'),
            (lambda: client.rename_object(
                Bucket=RAPID_BUCKET, Key='dst', RenameSource='/'),
             'empty rename source'),
            (lambda: client.get_session_presigned_url(
                Bucket=RAPID_BUCKET, Key='', Method='GET'),
             'object key is empty'),
            (lambda: client._http_once('PATCH', 'http://127.0.0.1:1/', 1),
             'unsupported method PATCH'),
        ]
        for call, expected in cases:
            try:
                call()
                self.fail('expected rejection containing %r' % (expected,))
            except CosClientError as e:
                self.assertIn(expected, str(e))
        self.assertEqual(self.server.state.requests, [])

    def test_high_level_copy_heads_rapid_source_through_short_domain(self):
        conf = CosConfig(
            Region='ap-guangzhou', SecretId=BASE_AK, SecretKey=BASE_SK,
            Scheme='http', EnableRapidDomain=True, EnableSessionAuth=True)
        client = CosS3Client(conf, session=requests.Session())
        captured = {}

        class RequestCaptured(Exception):
            pass

        def capture(*_args, **kwargs):
            captured.update(kwargs)
            raise RequestCaptured()

        client.send_request = capture
        source = {
            'Bucket': RAPID_BUCKET, 'Key': 'src.txt',
            'Region': 'ap-guangzhou'}
        with self.assertRaises(RequestCaptured):
            client._head_object_when_copy(source)
        self.assertEqual(
            captured['url'],
            'http://rapid-x--1250000000.cosrapid.ap-guangzhou.myqcloud.com/src.txt')
        self.assertTrue(captured['_rapid_data_request'])
        self.assertTrue(client._check_same_region(conf._endpoint, source))

        captured.clear()
        with self.assertRaises(RequestCaptured):
            client._head_object_when_copy(
                source,
                CopySourceSSECustomerAlgorithm='AES256',
                CopySourceSSECustomerKey='key',
                CopySourceSSECustomerKeyMD5='key-md5')
        self.assertEqual(
            captured['headers'][
                'x-cos-server-side-encryption-customer-key-MD5'],
            'key-md5')

        cross_region = dict(source)
        cross_region['Region'] = 'ap-shanghai'
        with self.assertRaises(CosClientError):
            client._head_object_when_copy(cross_region)

    def test_create_session_does_not_follow_redirect(self):
        self.server.state.session_status = 302
        self.server.state.session_location = '/redirected-session'
        client = self.server.client()
        try:
            client.create_session(Bucket=RAPID_BUCKET)
            self.fail('expected redirect rejection')
        except CosClientError as e:
            self.assertIn('unexpected status 302', str(e))
        self.assertEqual(self.server.state.redirect_hits, 0)

    def test_rename_encoding_and_forbid_overwrite(self):
        client = self.server.client()
        client.rename_object(
            Bucket=RAPID_BUCKET,
            Key='dst.txt',
            RenameSource='dir/a b/c!d',
            ForbidOverwrite='true')
        rec = self.server.object_requests()[0]
        self.assertEqual(rec['method'], 'PUT')
        self.assertEqual(rec['path'], '/dst.txt')
        src = rec['headers'].get('x-cos-rename-source')
        self.assertTrue(src.startswith('/'))
        self.assertEqual(unquote(src), '/dir/a b/c!d')
        self.assertIn('a%20b', src)
        self.assertEqual(rec['headers'].get('x-cos-forbid-overwrite'), 'true')

    def test_rename_ordinary_bucket_rejected(self):
        client = self.server.client()
        try:
            client.rename_object(Bucket=ORDINARY_BUCKET, Key='dst', RenameSource='src')
            self.fail('expected ordinary bucket rejection')
        except CosClientError as e:
            self.assertIn('rapid bucket', str(e))
        self.assertEqual(len(self.server.state.requests), 0)

    def test_rename_non_lb_path_does_not_retry_connection_error(self):
        client = self.server.client()
        attempts = []
        client._apply_session_credential = lambda *_args, **_kwargs: None

        def fail(*_args, **_kwargs):
            attempts.append(True)
            raise requests.ConnectionError('response lost')

        client._http_once = fail
        with self.assertRaises(CosClientError):
            client.rename_object(
                Bucket=RAPID_BUCKET, Key='dst', RenameSource='src')
        self.assertEqual(len(attempts), 1)

    def test_rename_non_lb_path_does_not_retry_5xx(self):
        client = self.server.client()
        attempts = []
        client._apply_session_credential = lambda *_args, **_kwargs: None
        response = requests.Response()
        response.status_code = 500
        response._content = b'<Error><Code>InternalError</Code></Error>'

        def fail(*_args, **_kwargs):
            attempts.append(True)
            return response

        client._http_once = fail
        with self.assertRaises(CosServiceError):
            client.rename_object(
                Bucket=RAPID_BUCKET, Key='dst', RenameSource='src')
        self.assertEqual(len(attempts), 1)

    def test_rename_non_lb_path_still_retries_session_403_once(self):
        client = self.server.client()
        attempts = []
        applied = []
        first = requests.Response()
        first.status_code = 403
        first._content = b'<Error><Code>AccessDenied</Code></Error>'
        second = requests.Response()
        second.status_code = 200
        second._content = b''
        outcomes = [first, second]
        client._apply_session_credential = lambda bucket, kwargs, mode=None, force_refresh=False: applied.append(
            (bucket, force_refresh))
        client._session_provider.evict = lambda bucket: True

        def transport(*_args, **_kwargs):
            attempts.append(True)
            return outcomes.pop(0)

        client._http_once = transport
        client.rename_object(
            Bucket=RAPID_BUCKET, Key='dst', RenameSource='src')
        self.assertEqual(len(attempts), 2)
        self.assertEqual(applied, [(RAPID_BUCKET, False), (RAPID_BUCKET, True)])

    def test_presign_get_default_readonly_and_token_in_query(self):
        client = self.server.client()
        caller_params = {'response-content-type': 'text/plain'}
        url = client.get_session_presigned_url(
            Bucket=RAPID_BUCKET, Key='a.txt', Method='GET', Expired=300,
            Params=caller_params)
        parsed = urlparse(url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        self.assertIn('q-sign-algorithm', query)
        self.assertIn('x-cos-security-token', query)
        self.assertNotIn('sign', query)
        self.assertEqual(query['x-cos-security-token'][0], SESSION_TOKEN)
        self.assertEqual(query['response-content-type'][0], 'text/plain')
        # 调用方传入的 Params 不能被写入 token。
        self.assertEqual(caller_params, {'response-content-type': 'text/plain'})
        mode = self.server.session_requests()[0]['headers'].get('x-cos-create-session-mode')
        self.assertEqual(mode, 'ReadOnly')

    def test_base_secret_id_follows_credential_instance_and_anonymous(self):
        class CredentialInstance(object):
            secret_id = BASE_AK
            secret_key = BASE_SK
            # NOCA:PasswordLeak(Synthetic credential for local test fixtures; not a real account)
            token = 'base-session-token'

        conf = CosConfig(
            Region='ap-guangzhou', CredentialInstance=CredentialInstance(),
            Scheme='http', Domain='127.0.0.1:%s' % self.server.port,
            EnableSessionAuth=True, KeepAlive=False, Timeout=5)
        client = CosS3Client(conf, retry=0, session=requests.Session())
        # session 缓存指纹必须跟随 CredentialInstance 的基础 AK。
        self.assertEqual(client._base_secret_id(), BASE_AK)

        anonymous_conf = CosConfig(
            Region='ap-guangzhou', Anonymous=True, Scheme='http',
            Domain='127.0.0.1:%s' % self.server.port)
        anonymous_client = CosS3Client(
            anonymous_conf, retry=0, session=requests.Session())
        self.assertEqual(anonymous_client._base_secret_id(), u'')
        self.assertEqual(self.server.state.requests, [])

    def test_ip_literal_detection_gates_gateway_dns_lb(self):
        cases = [
            (None, False),
            ('', False),
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            ('10.0.0.1', True),
            ('2001:db8::1', True),
            ('rapid-x--1250000000.cosrapid.ap-guangzhou.myqcloud.com', False),
        ]
        for host, expected in cases:
            self.assertEqual(
                CosS3Client._is_ip_literal(host), expected,
                'unexpected result for host %r' % (host,))

    def test_get_auth_optional_mappings_keep_signatures_and_parameter_contract(self):
        client = self.server.client()
        original_time = time.time
        try:
            time.time = lambda: 2000000000
            for bucket in (ORDINARY_BUCKET, RAPID_BUCKET):
                base = dict(Method='GET', Bucket=bucket, Key='object')
                expected = client.get_auth(**base)
                for options in ({'Params': None, 'Headers': None},
                                {'Params': {}, 'Headers': {}}):
                    self.assertEqual(client.get_auth(**dict(base, **options)), expected)
                params = {'fixture-query': 'caller'}
                headers = {'x-cos-meta-fixture': 'caller'}
                signed = client.get_auth(Params=params, Headers=headers, **base)
                self.assertEqual(params, {'fixture-query': 'caller'})
                # Nonempty Headers retain the existing Authorization write-back.
                self.assertEqual(headers['x-cos-meta-fixture'], 'caller')
                self.assertEqual(headers['Authorization'], signed)
                self.assertEqual(set(headers), {'x-cos-meta-fixture', 'Authorization'})
                self.assertEqual(client.get_auth(**base), expected)
            self.assertEqual(self.server.state.requests, [])
        finally:
            time.time = original_time
            client._session.close()

    def test_session_presign_optional_mappings_do_not_leak_between_calls(self):
        client = self.server.client()
        try:
            params = {'fixture-query': 'caller'}
            headers = {'x-cos-meta-fixture': 'caller'}
            base = dict(Bucket=RAPID_BUCKET, Key='object', Method='GET')
            first = client.get_session_presigned_url(Params=params, Headers=headers, **base)
            self.assertEqual(parse_qs(urlparse(first).query)['fixture-query'], ['caller'])
            self.assertEqual(params, {'fixture-query': 'caller'})
            self.assertEqual(headers['x-cos-meta-fixture'], 'caller')
            self.assertEqual(set(headers), {'x-cos-meta-fixture', 'Authorization'})
            for options in ({}, {'Params': None, 'Headers': None},
                            {'Params': {}, 'Headers': {}}):
                url = client.get_session_presigned_url(**dict(base, **options))
                query = parse_qs(urlparse(url).query)
                self.assertNotIn('fixture-query', query)
                self.assertNotIn('x-cos-meta-fixture', query['q-header-list'][0].split(';'))
                self.assertIn('x-cos-security-token', query)
        finally:
            client._session.close()

    def test_presign_get_after_put_uses_isolated_readonly(self):
        client = self.server.client()
        orig = client._session_provider._create_fn

        def tagged(bucket, mode):
            self.server.state.session_body = _xml_session(
                # NOCA:PasswordLeak(Synthetic credential for local test fixtures; not a real account)
                secret_id='SKID-%s' % mode, token='tok-%s' % mode)
            return orig(bucket, mode)

        client._session_provider._create_fn = tagged
        client.put_object(Bucket=RAPID_BUCKET, Key='a.txt', Body=b'hello')
        url = client.get_presigned_url(
            Bucket=RAPID_BUCKET, Key='a.txt', Method='GET', Expired=300)
        sessions = self.server.session_requests()
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0]['headers'].get('x-cos-create-session-mode'), 'ReadWrite')
        self.assertEqual(sessions[1]['headers'].get('x-cos-create-session-mode'), 'ReadOnly')
        query = parse_qs(urlparse(url).query, keep_blank_values=True)
        self.assertEqual(query['x-cos-security-token'][0], 'tok-ReadOnly')
        self.assertEqual(query['q-ak'][0], 'SKID-ReadOnly')

        url2 = client.get_session_presigned_url(
            Bucket=RAPID_BUCKET, Key='a.txt', Method='GET', Expired=300)
        self.assertEqual(len(self.server.session_requests()), 2)
        query2 = parse_qs(urlparse(url2).query, keep_blank_values=True)
        self.assertEqual(query2['x-cos-security-token'][0], 'tok-ReadOnly')

        client.put_object(Bucket=RAPID_BUCKET, Key='b.txt', Body=b'world')
        self.assertEqual(len(self.server.session_requests()), 2)
        put_url = client.get_session_presigned_url(
            Bucket=RAPID_BUCKET, Key='b.txt', Method='PUT', Expired=300)
        self.assertEqual(len(self.server.session_requests()), 2)
        put_query = parse_qs(urlparse(put_url).query, keep_blank_values=True)
        self.assertEqual(put_query['x-cos-security-token'][0], 'tok-ReadWrite')

    def test_presign_rejects_expired_and_sign_merged(self):
        client = self.server.client()
        self.assertRaises(
            CosClientError,
            client.get_session_presigned_url,
            Bucket=RAPID_BUCKET, Key='a.txt', Method='GET', Expired=0)
        self.assertRaises(
            CosClientError,
            client.get_session_presigned_url,
            Bucket=RAPID_BUCKET, Key='a.txt', Method='GET', SignMerged=True)

    def test_l3_fail_fast_when_session_disabled(self):
        for flag in (False, None):
            server = _MockServer()
            try:
                client = server.client(EnableSessionAuth=flag)
                try:
                    client.put_object(Bucket=RAPID_BUCKET, Key='a.txt', Body=b'x')
                    self.fail('expected local fail-fast for EnableSessionAuth=%r' % (flag,))
                except CosClientError as e:
                    self.assertIn('requires session auth', str(e))
                self.assertEqual(len(server.state.requests), 0)
            finally:
                server.close()

    def test_enable_rapid_domain_endpoint(self):
        conf = CosConfig(
            Region='ap-guangzhou',
            SecretId=BASE_AK,
            SecretKey=BASE_SK,
            EnableRapidDomain=True)
        self.assertEqual(
            conf._endpoint, 'cosrapid.ap-guangzhou.myqcloud.com')
        self.assertEqual(
            conf._service_domain,
            'service.cosrapid.ap-guangzhou.myqcloud.com')
        self.assertTrue(should_use_session_auth(conf, RAPID_BUCKET))
        self.assertFalse(should_use_session_auth(conf, ORDINARY_BUCKET))
        self.assertTrue(require_session_ready(conf, RAPID_BUCKET))
        self.assertFalse(require_session_ready(conf, ORDINARY_BUCKET))

        long_conf = CosConfig(
            Region='ap-guangzhou', SecretId=BASE_AK, SecretKey=BASE_SK,
            Endpoint='cos-rapid.ap-guangzhou.tencentcos.com')
        self.assertFalse(should_use_session_auth(long_conf, RAPID_BUCKET))

        with self.assertRaises(CosClientError):
            CosConfig(
                Region='ap-guangzhou', SecretId=BASE_AK, SecretKey=BASE_SK,
                Endpoint='gz.tencentcos.com', EnableRapidDomain=True)


def _event_is_set(event):
    if hasattr(event, 'is_set'):
        return event.is_set()
    return event.isSet()


class _ObservedLock(object):
    def __init__(self, lock, expected_attempts):
        self._lock = lock
        self._count_lock = threading.Lock()
        self._expected_attempts = expected_attempts
        self.attempts = 0
        self.all_attempted = threading.Event()

    def __enter__(self):
        self._count_lock.acquire()
        try:
            self.attempts += 1
            if self.attempts == self._expected_attempts:
                self.all_attempted.set()
        finally:
            self._count_lock.release()
        self._lock.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._lock.release()


class _CountingSession(object):
    def __init__(self):
        self._lock = threading.Lock()
        self.close_calls = 0

    def close(self):
        self._lock.acquire()
        try:
            self.close_calls += 1
        finally:
            self._lock.release()


class TestBuiltInSessionLock(unittest.TestCase):
    _SESSION_ATTR = '_CosS3Client__built_in_sessions'
    _PID_ATTR = '_CosS3Client__built_in_pid'
    _LOCKS_ATTR = '_CosS3Client__built_in_locks'

    def setUp(self):
        self.original_session = getattr(CosS3Client, self._SESSION_ATTR)
        self.original_pid = getattr(CosS3Client, self._PID_ATTR)
        self.original_locks = getattr(CosS3Client, self._LOCKS_ATTR)
        self.original_generate = CosS3Client.__dict__['generate_built_in_connection_pool']
        setattr(CosS3Client, self._SESSION_ATTR, None)
        setattr(CosS3Client, self._PID_ATTR, 0)
        setattr(CosS3Client, self._LOCKS_ATTR, {})

    def tearDown(self):
        current_session = getattr(CosS3Client, self._SESSION_ATTR)
        if current_session is not None and current_session is not self.original_session:
            current_session.close()
        setattr(CosS3Client, self._SESSION_ATTR, self.original_session)
        setattr(CosS3Client, self._PID_ATTR, self.original_pid)
        setattr(CosS3Client, self._LOCKS_ATTR, self.original_locks)
        CosS3Client.generate_built_in_connection_pool = self.original_generate

    def _config(self):
        return CosConfig(
            Region='ap-guangzhou',
            SecretId=BASE_AK,
            SecretKey=BASE_SK)

    def _run_concurrently(self, count, fn):
        ready_lock = threading.Lock()
        ready = [0]
        all_ready = threading.Event()
        start = threading.Event()
        result_lock = threading.Lock()
        results = []
        errors = []

        def worker(index):
            ready_lock.acquire()
            try:
                ready[0] += 1
                if ready[0] == count:
                    all_ready.set()
            finally:
                ready_lock.release()
            start.wait()
            try:
                value = fn(index)
                result_lock.acquire()
                try:
                    results.append(value)
                finally:
                    result_lock.release()
            except Exception as error:
                result_lock.acquire()
                try:
                    errors.append(error)
                finally:
                    result_lock.release()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(count)]
        for thread in threads:
            thread.daemon = True
            thread.start()
        all_ready.wait(5)
        ready = _event_is_set(all_ready)
        start.set()
        deadline = time.time() + 5
        for thread in threads:
            remaining = deadline - time.time()
            if remaining > 0:
                thread.join(remaining)
        self.assertFalse([thread for thread in threads if thread.is_alive()], 'worker thread hung')
        self.assertTrue(ready, 'workers did not become ready')
        if errors:
            raise errors[0]
        return results

    def test_concurrent_clients_create_one_built_in_session(self):
        worker_count = 16
        pid = os.getpid()
        base_lock = threading.Lock()
        observed_lock = _ObservedLock(base_lock, worker_count)
        setattr(CosS3Client, self._LOCKS_ATTR, {pid: observed_lock})
        generated = []
        generated_lock = threading.Lock()

        def generate(client, pool_connections, pool_maxsize):
            generated_lock.acquire()
            try:
                generated.append((pool_connections, pool_maxsize))
            finally:
                generated_lock.release()
            observed_lock.all_attempted.wait(5)
            if not _event_is_set(observed_lock.all_attempted):
                raise AssertionError('not all workers attempted the shared lock')
            return _CountingSession()

        CosS3Client.generate_built_in_connection_pool = generate
        config = self._config()
        clients = self._run_concurrently(worker_count, lambda _index: CosS3Client(config))

        shared_session = getattr(CosS3Client, self._SESSION_ATTR)
        self.assertEqual(len(generated), 1)
        self.assertEqual(observed_lock.attempts, worker_count)
        self.assertTrue(all(client._session is shared_session for client in clients))
        self.assertEqual(getattr(CosS3Client, self._PID_ATTR), pid)

    def test_concurrent_pid_change_rebuilds_one_built_in_session(self):
        worker_count = 16
        pid = os.getpid()
        old_session = _CountingSession()
        setattr(CosS3Client, self._SESSION_ATTR, old_session)
        setattr(CosS3Client, self._PID_ATTR, pid)
        clients = [CosS3Client(self._config()) for _ in range(worker_count)]

        base_lock = threading.Lock()
        observed_lock = _ObservedLock(base_lock, worker_count)
        setattr(CosS3Client, self._LOCKS_ATTR, {pid: observed_lock})
        setattr(CosS3Client, self._PID_ATTR, 0)
        generated = []
        generated_lock = threading.Lock()

        def generate(client, pool_connections, pool_maxsize):
            generated_lock.acquire()
            try:
                session = _CountingSession()
                generated.append(session)
            finally:
                generated_lock.release()
            observed_lock.all_attempted.wait(5)
            if not _event_is_set(observed_lock.all_attempted):
                raise AssertionError('not all workers attempted the shared lock')
            return session

        CosS3Client.generate_built_in_connection_pool = generate
        sessions = self._run_concurrently(
            worker_count,
            lambda index: self._rebind_and_get_session(clients[index]))

        shared_session = getattr(CosS3Client, self._SESSION_ATTR)
        self.assertEqual(len(generated), 1)
        self.assertEqual(old_session.close_calls, 0)
        self.assertEqual(observed_lock.attempts, worker_count)
        self.assertTrue(all(session is shared_session for session in sessions))
        self.assertEqual(getattr(CosS3Client, self._PID_ATTR), pid)

    def test_client_rebinds_after_another_client_rebuilds_session(self):
        old_session = _CountingSession()
        setattr(CosS3Client, self._SESSION_ATTR, old_session)
        setattr(CosS3Client, self._PID_ATTR, os.getpid())
        first = CosS3Client(self._config())
        second = CosS3Client(self._config())

        setattr(CosS3Client, self._PID_ATTR, 0)
        generated = []

        def generate(client, pool_connections, pool_maxsize):
            session = _CountingSession()
            generated.append(session)
            return session

        CosS3Client.generate_built_in_connection_pool = generate
        first.handle_built_in_connection_pool_by_pid()
        second.handle_built_in_connection_pool_by_pid()

        shared_session = getattr(CosS3Client, self._SESSION_ATTR)
        self.assertEqual(len(generated), 1)
        self.assertTrue(first._session is shared_session)
        self.assertTrue(second._session is shared_session)
        self.assertFalse(second._session is old_session)

    @unittest.skipUnless(hasattr(os, 'fork'), 'requires os.fork')
    def test_fork_rebuilds_session_without_inheriting_locked_parent_lock(self):
        pid = os.getpid()
        old_session = _CountingSession()
        setattr(CosS3Client, self._SESSION_ATTR, old_session)
        setattr(CosS3Client, self._PID_ATTR, pid)
        client = CosS3Client(self._config())
        generated = []

        def generate(current_client, pool_connections, pool_maxsize):
            session = _CountingSession()
            generated.append(session)
            return session

        CosS3Client.generate_built_in_connection_pool = generate
        parent_lock = threading.Lock()
        setattr(CosS3Client, self._LOCKS_ATTR, {pid: parent_lock})
        parent_lock.acquire()
        read_fd, write_fd = os.pipe()
        child_pid = os.fork()
        if child_pid == 0:
            try:
                os.close(read_fd)
                client.handle_built_in_connection_pool_by_pid()
                child_lock = CosS3Client._built_in_lock()
                result = {
                    'generated': len(generated),
                    'pid_match': getattr(CosS3Client, self._PID_ATTR) == os.getpid(),
                    'rebound': client._session is getattr(CosS3Client, self._SESSION_ATTR),
                    'new_session': client._session is not old_session,
                    'new_lock': child_lock is not parent_lock,
                    'old_session_close_calls': old_session.close_calls,
                }
                os.write(write_fd, json.dumps(result).encode('utf-8'))
            finally:
                os.close(write_fd)
                os._exit(0)

        os.close(write_fd)
        try:
            readable, _, _ = select.select([read_fd], [], [], 5)
            self.assertTrue(readable, 'child blocked on inherited parent lock')
            result = json.loads(os.read(read_fd, 4096).decode('utf-8'))
            self.assertEqual(result['generated'], 1)
            self.assertTrue(result['pid_match'])
            self.assertTrue(result['rebound'])
            self.assertTrue(result['new_session'])
            self.assertTrue(result['new_lock'])
            self.assertEqual(result['old_session_close_calls'], 0)
            _, status = os.waitpid(child_pid, 0)
            self.assertTrue(os.WIFEXITED(status))
            self.assertEqual(os.WEXITSTATUS(status), 0)
        finally:
            os.close(read_fd)
            parent_lock.release()
            try:
                waited, _ = os.waitpid(child_pid, os.WNOHANG)
                if waited == 0:
                    os.kill(child_pid, signal.SIGKILL)
                    os.waitpid(child_pid, 0)
            except OSError:
                pass

    @staticmethod
    def _rebind_and_get_session(client):
        client.handle_built_in_connection_pool_by_pid()
        return client._session


class _StubResponse(object):
    def __init__(self, status_code, body=b'', headers=None):
        self.status_code = status_code
        self.content = body
        self.headers = headers or {}
        self.closed = False

    @property
    def text(self):
        if isinstance(self.content, bytes):
            return self.content.decode('utf-8')
        return self.content

    def close(self):
        self.closed = True


class TestNonGatewayRetryPath(unittest.TestCase):
    """HTTPS / 非 DNS LB 路径下的 session 403 与 5xx 重试语义。

    Gateway DNS LB 只覆盖 HTTP；HTTPS Rapid 走 send_request 的传统重试循环，
    该循环里的 session 403 重签与 5xx 重试同样属于 Rapid 契约。
    """

    def setUp(self):
        self.original_sleep = cos_client_module.time.sleep
        self.slept = []
        cos_client_module.time.sleep = self._record_sleep

    def tearDown(self):
        cos_client_module.time.sleep = self.original_sleep

    def _record_sleep(self, delay):
        self.slept.append(delay)

    def _client(self, retry=1):
        conf = CosConfig(
            Region='ap-guangzhou', SecretId=BASE_AK, SecretKey=BASE_SK,
            EnableRapidDomain=True, EnableSessionAuth=True,
            KeepAlive=False, Timeout=5)
        client = CosS3Client(conf, retry=retry, session=requests.Session())
        # HTTPS 下 Gateway DNS LB 自动旁路，请求走传统重试循环。
        self.assertIsNone(client._gateway_lb_context(
            conf.uri(bucket=RAPID_BUCKET, path='key'), RAPID_BUCKET))
        return client

    def _install(self, client, outcomes, attempts, applied, evicted=None):
        def transport(method, url, timeout, **kwargs):
            attempts.append((method, url, dict(kwargs.get('headers') or {})))
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        def apply(bucket, kwargs, mode=None, force_refresh=False):
            applied.append((bucket, force_refresh))

        def evict(bucket):
            if evicted is not None:
                evicted.append(bucket)
            return True

        client._http_once = transport
        client._apply_session_credential = apply
        client._session_provider.evict = evict

    def _send(self, client, **kwargs):
        values = {
            'method': 'PUT',
            'url': client._conf.uri(bucket=RAPID_BUCKET, path='key'),
            'bucket': RAPID_BUCKET,
            'auth': CosS3Auth(client._conf, 'key'),
            'data': b'payload',
            '_rapid_data_request': True,
        }
        values.update(kwargs)
        return client.send_request(**values)

    def test_session_403_retry_outcomes_matrix(self):
        def forbidden():
            return _StubResponse(
                403, b'<Error><Code>AccessDenied</Code></Error>')

        cases = [
            # 重签后传输异常：转为客户端错误，不再重试。
            ([forbidden(), requests.ConnectionError('lost')], True,
             CosClientError),
            # 重签后仍是 4xx：直接结束，不再重试。
            ([forbidden(),
              _StubResponse(404, b'<Error><Code>NoSuchKey</Code></Error>')],
             True, CosServiceError),
            # 重签后 5xx 但请求不允许重放：结束并保留服务端响应。
            ([forbidden(),
              _StubResponse(500, b'<Error><Code>InternalError</Code></Error>')],
             False, CosServiceError),
        ]
        for outcomes, retry_ambiguous, expected_error in cases:
            client = self._client(retry=1)
            attempts = []
            applied = []
            evicted = []
            del self.slept[:]
            first = outcomes[0]
            self._install(client, list(outcomes), attempts, applied, evicted)

            with self.assertRaises(expected_error):
                self._send(client, _retry_ambiguous=retry_ambiguous)

            self.assertEqual(len(attempts), 2)
            self.assertEqual(attempts[1][2]['x-cos-sdk-retry'], 'true')
            self.assertTrue(first.closed)
            self.assertEqual(evicted, [RAPID_BUCKET])
            self.assertEqual(
                applied, [(RAPID_BUCKET, False), (RAPID_BUCKET, True)])
            self.assertEqual(self.slept, [])

    def test_session_403_then_5xx_retries_once_more(self):
        client = self._client(retry=1)
        attempts = []
        applied = []
        evicted = []
        first = _StubResponse(403, b'<Error><Code>AccessDenied</Code></Error>')
        self._install(
            client,
            [first, _StubResponse(500, b'<Error/>'), _StubResponse(200)],
            attempts, applied, evicted)

        result = self._send(client)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(attempts), 3)
        self.assertTrue(first.closed)
        self.assertEqual(applied, [(RAPID_BUCKET, False), (RAPID_BUCKET, True)])
        self.assertEqual(evicted, [RAPID_BUCKET])
        self.assertEqual(self.slept, [1])

    def test_non_rewindable_session_403_breaks_without_resign(self):
        client = self._client(retry=1)
        attempts = []
        applied = []
        evicted = []
        forbidden = _StubResponse(403, b'<Error><Code>AccessDenied</Code></Error>')
        self._install(client, [forbidden], attempts, applied, evicted)

        with self.assertRaises(CosServiceError):
            self._send(client, data=(chunk for chunk in [b'payload']))

        self.assertEqual(len(attempts), 1)
        self.assertFalse(forbidden.closed)
        self.assertEqual(evicted, [])
        self.assertEqual(applied, [(RAPID_BUCKET, False)])
        self.assertEqual(self.slept, [])

    def test_5xx_retry_and_non_rewindable_body_stops_after_one_attempt(self):
        client = self._client(retry=1)
        attempts = []
        applied = []
        self._install(
            client, [_StubResponse(500, b'<Error/>'), _StubResponse(200)],
            attempts, applied)
        result = self._send(client)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(attempts[1][2]['x-cos-sdk-retry'], 'true')
        self.assertEqual(self.slept, [1])

        client = self._client(retry=1)
        attempts = []
        applied = []
        del self.slept[:]
        self._install(
            client, [_StubResponse(500, b'<Error/>')], attempts, applied)
        with self.assertRaises(CosServiceError):
            self._send(client, data=(chunk for chunk in [b'payload']))
        # 不可重放的 body 只发一次，并保留服务端 5xx 响应语义。
        self.assertEqual(len(attempts), 1)
        self.assertEqual(self.slept, [])

    def test_client_error_from_transport_is_not_retried_or_wrapped(self):
        client = self._client(retry=3)
        attempts = []
        applied = []
        self._install(
            client, [CosClientError('local guard tripped')], attempts, applied)
        try:
            self._send(client)
            self.fail('expected CosClientError to propagate')
        except CosClientError as e:
            self.assertIn('local guard tripped', str(e))
        self.assertEqual(len(attempts), 1)
        self.assertEqual(self.slept, [])


if __name__ == '__main__':
    unittest.main()
