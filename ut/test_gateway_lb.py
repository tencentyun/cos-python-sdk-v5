# -*- coding: utf-8 -*-
"""HTTP Rapid Gateway DNS LB 单测。不依赖真实 DNS 或网络。"""

import os
import socket
import threading
import unittest
from io import BytesIO

import requests
from requests import ConnectionError, Timeout
from requests.exceptions import ChunkedEncodingError

import qcloud_cos.cos_client as cos_client_module

from qcloud_cos import CosClientError, CosConfig, CosS3Auth, CosS3Client, CosServiceError
from qcloud_cos import gateway_dns_lb
from qcloud_cos.cos_comm import client_can_retry


RAPID_BUCKET = 'rapid-x--1250000000'
ORDINARY_BUCKET = 'example-1250000000'
BASE_AK = 'AKIDBASE'
BASE_SK = 'base-secret'
PROXY_ENV = ('http_proxy', 'HTTP_PROXY', 'all_proxy', 'ALL_PROXY')


def _event_is_set(event):
    if hasattr(event, 'is_set'):
        return event.is_set()
    return event.isSet()


class TestGatewayLbGate(unittest.TestCase):
    def setUp(self):
        self.proxy_env = dict((name, os.environ.get(name)) for name in PROXY_ENV)
        for name in PROXY_ENV:
            os.environ.pop(name, None)

    def tearDown(self):
        for name, value in self.proxy_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def _config(self, **kwargs):
        values = {
            'Region': 'ap-guangzhou',
            'SecretId': BASE_AK,
            'SecretKey': BASE_SK,
            'Scheme': 'http',
            'Endpoint': 'cosrapid.ap-guangzhou.myqcloud.com',
        }
        values.update(kwargs)
        return CosConfig(**values)

    def _client_and_url(self, bucket=RAPID_BUCKET, session=None, **kwargs):
        conf = self._config(**kwargs)
        client = CosS3Client(conf, session=session)
        url = conf.uri(bucket=bucket, path='key')
        return client, url

    def _context(self, client, url, bucket=RAPID_BUCKET, **kwargs):
        client._session.trust_env = kwargs.pop('trust_env', False)
        return client._gateway_lb_context(url, bucket, **kwargs)

    def test_http_rapid_auto_enables_and_interval_is_clamped(self):
        client, url = self._client_and_url(GatewayDnsRefreshInterval=0.1)
        context = self._context(client, url)
        self.assertEqual(
            context,
            ('rapid-x--1250000000.cosrapid.ap-guangzhou.myqcloud.com',
             'rapid-x--1250000000.cosrapid.ap-guangzhou.myqcloud.com', 80))
        self.assertEqual(client._conf._gateway_dns_refresh_interval, 1.0)

    def test_invalid_interval_is_rejected(self):
        self.assertEqual(self._config(GatewayDnsRefreshInterval=None)._gateway_dns_refresh_interval, 5.0)
        with self.assertRaises(CosClientError):
            self._config(GatewayDnsRefreshInterval='bad')

    def test_false_and_ordinary_bucket_always_bypass(self):
        client, url = self._client_and_url(EnableGatewayDnsLb=False)
        self.assertIsNone(self._context(client, url))
        client, url = self._client_and_url(bucket=ORDINARY_BUCKET, EnableGatewayDnsLb=True)
        self.assertIsNone(self._context(client, url, bucket=ORDINARY_BUCKET))

    def test_https_auto_bypasses_and_true_rejects(self):
        client, url = self._client_and_url(Scheme='https')
        self.assertIsNone(self._context(client, url))
        client, url = self._client_and_url(Scheme='https', EnableGatewayDnsLb=True)
        with self.assertRaises(CosClientError):
            self._context(client, url)

        applied = []
        client._apply_session_credential = lambda *_args, **_kwargs: applied.append(True)
        with self.assertRaises(CosClientError):
            client.send_request(method='GET', url=url, bucket=RAPID_BUCKET)
        self.assertEqual(applied, [])

    def test_static_ip_proxy_and_custom_session_gate(self):
        cases = [
            {'IP': '127.0.0.1'},
            {'Proxies': {'http': 'http://127.0.0.1:3128'}},
        ]
        for values in cases:
            auto_client, auto_url = self._client_and_url(**values)
            self.assertIsNone(self._context(auto_client, auto_url))
            forced = dict(values)
            forced['EnableGatewayDnsLb'] = True
            client, url = self._client_and_url(**forced)
            with self.assertRaises(CosClientError):
                self._context(client, url)

        custom = requests.Session()
        client, url = self._client_and_url(session=custom)
        self.assertIsNone(self._context(client, url))
        client, url = self._client_and_url(
            session=custom, EnableGatewayDnsLb=True)
        with self.assertRaises(CosClientError):
            self._context(client, url)
        custom.close()

    def test_environment_proxy_gate_ignores_no_proxy(self):
        os.environ['HTTP_PROXY'] = 'http://127.0.0.1:3128'
        os.environ['NO_PROXY'] = '.myqcloud.com'
        try:
            client, url = self._client_and_url()
            self.assertIsNone(self._context(client, url, trust_env=True))
            client, url = self._client_and_url(EnableGatewayDnsLb=True)
            with self.assertRaises(CosClientError):
                self._context(client, url, trust_env=True)

            client, url = self._client_and_url()
            self.assertIsNotNone(self._context(client, url, trust_env=False))
        finally:
            os.environ.pop('NO_PROXY', None)

    def test_ci_and_non_cos_requests_bypass(self):
        client, url = self._client_and_url(EnableGatewayDnsLb=True)
        self.assertIsNone(self._context(client, url, ci_request=True))
        self.assertIsNone(self._context(client, url, cos_request=False))

    def test_wrong_or_unknown_region_is_rejected(self):
        client, url = self._client_and_url(
            Endpoint='cosrapid.ap-shanghai.myqcloud.com')
        self.assertIsNone(self._context(client, url))
        client, url = self._client_and_url(
            Endpoint='cosrapid.ap-shanghai.myqcloud.com',
            EnableGatewayDnsLb=True)
        with self.assertRaises(CosClientError):
            self._context(client, url)
        client, url = self._client_and_url(
            Endpoint='cosrapid.ap-notexist.myqcloud.com')
        self.assertIsNone(self._context(client, url))

    def test_legacy_long_domain_is_not_a_gateway_lb_contract(self):
        endpoint = 'cos-rapid.ap-guangzhou.tencentcos.com'
        client, url = self._client_and_url(Endpoint=endpoint)
        self.assertIsNone(self._context(client, url))
        client, url = self._client_and_url(
            Endpoint=endpoint, EnableGatewayDnsLb=True)
        with self.assertRaises(CosClientError):
            self._context(client, url)

    def test_legacy_abbreviated_domain_is_not_a_gateway_lb_contract(self):
        endpoint = 'gz.tencentcos.com'
        client, url = self._client_and_url(Endpoint=endpoint)
        self.assertIsNone(self._context(client, url))
        client, url = self._client_and_url(
            Endpoint=endpoint, EnableGatewayDnsLb=True)
        with self.assertRaises(CosClientError):
            self._context(client, url)


class TestGatewayDnsState(unittest.TestCase):
    def setUp(self):
        self.original_condition = gateway_dns_lb._condition
        self.original_states = gateway_dns_lb._states
        self.original_pid = gateway_dns_lb._pid
        self.original_thread = gateway_dns_lb._thread
        self.original_pid_locks = gateway_dns_lb._pid_locks
        self.original_start_thread = gateway_dns_lb._start_thread_locked
        self.original_getaddrinfo = gateway_dns_lb.socket.getaddrinfo
        self.original_monotonic = gateway_dns_lb._monotonic
        self.original_cold_wait_timeout = gateway_dns_lb._COLD_WAIT_TIMEOUT
        gateway_dns_lb._condition = threading.Condition()
        gateway_dns_lb._states = {}
        gateway_dns_lb._pid = os.getpid()
        gateway_dns_lb._thread = None
        gateway_dns_lb._pid_locks = {}
        gateway_dns_lb._start_thread_locked = lambda: None

    def tearDown(self):
        gateway_dns_lb._condition = self.original_condition
        gateway_dns_lb._states = self.original_states
        gateway_dns_lb._pid = self.original_pid
        gateway_dns_lb._thread = self.original_thread
        gateway_dns_lb._pid_locks = self.original_pid_locks
        gateway_dns_lb._start_thread_locked = self.original_start_thread
        gateway_dns_lb.socket.getaddrinfo = self.original_getaddrinfo
        gateway_dns_lb._monotonic = self.original_monotonic
        gateway_dns_lb._COLD_WAIT_TIMEOUT = self.original_cold_wait_timeout

    @staticmethod
    def _answer(ip, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, port))]

    def test_same_key_cold_resolution_is_singleflight(self):
        entered = threading.Event()
        release = threading.Event()
        calls = []

        def resolve(host, port, family, socktype):
            calls.append((host, port, family, socktype))
            entered.set()
            release.wait(5)
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            return self._answer('10.0.0.1', port)

        gateway_dns_lb.socket.getaddrinfo = resolve
        results = []
        errors = []

        def worker():
            try:
                results.append(gateway_dns_lb.ensure_snapshot('rapid.test', 80, 5))
            except Exception as error:
                errors.append(error)

        first = threading.Thread(target=worker)
        second = threading.Thread(target=worker)
        first.daemon = True
        second.daemon = True
        first.start()
        entered.wait(2)
        self.assertTrue(_event_is_set(entered), 'resolver did not start')
        second.start()
        release.set()
        first.join(2)
        second.join(2)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        if errors:
            raise errors[0]
        self.assertEqual(len(calls), 1)
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        self.assertEqual(results, [(('10.0.0.1', 80),)] * 2)

    def test_concurrent_first_access_after_pid_change_resets_once(self):
        gateway_dns_lb._pid = 0
        gateway_dns_lb._pid_locks = {}
        entered = threading.Event()
        release = threading.Event()
        calls = []

        def resolve(host, port, family, socktype):
            calls.append((host, port, family, socktype))
            entered.set()
            release.wait(5)
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            return self._answer('10.0.0.1', port)

        gateway_dns_lb.socket.getaddrinfo = resolve
        results = []

        def worker():
            results.append(gateway_dns_lb.ensure_snapshot('rapid.test', 80, 5))

        first = threading.Thread(target=worker)
        second = threading.Thread(target=worker)
        first.daemon = True
        second.daemon = True
        first.start()
        self.assertTrue(entered.wait(2), 'resolver did not start')
        second.start()
        release.set()
        first.join(2)
        second.join(2)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(gateway_dns_lb._pid, os.getpid())
        self.assertEqual(len(calls), 1)
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        self.assertEqual(results, [(('10.0.0.1', 80),)] * 2)

    def test_cold_resolution_wait_is_bounded_and_late_publish_survives(self):
        entered = threading.Event()
        release = threading.Event()
        results = {}
        gateway_dns_lb._COLD_WAIT_TIMEOUT = 0.05

        def resolve(host, port, family, socktype):
            entered.set()
            release.wait(5)
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            return self._answer('10.0.0.1', port)

        gateway_dns_lb.socket.getaddrinfo = resolve

        def resolver():
            results['resolver'] = gateway_dns_lb.ensure_snapshot(
                'rapid.test', 80, 5)

        def waiter():
            results['waiter'] = gateway_dns_lb.ensure_snapshot(
                'rapid.test', 80, 5)

        first = threading.Thread(target=resolver)
        second = threading.Thread(target=waiter)
        first.daemon = True
        second.daemon = True
        first.start()
        self.assertTrue(entered.wait(2), 'resolver did not start')
        second.start()
        second.join(1)
        self.assertFalse(second.is_alive(), 'cold waiter exceeded its deadline')
        self.assertEqual(results.get('waiter'), ())

        release.set()
        first.join(2)
        self.assertFalse(first.is_alive())
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        self.assertEqual(results['resolver'], (('10.0.0.1', 80),))
        self.assertEqual(
            gateway_dns_lb.ensure_snapshot('rapid.test', 80, 5),
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            (('10.0.0.1', 80),))

    def test_different_key_resolution_does_not_hold_global_lock(self):
        first_entered = threading.Event()
        release_first = threading.Event()
        second_done = threading.Event()
        results = {}

        def resolve(host, port, family, socktype):
            if host == 'a.test':
                first_entered.set()
                release_first.wait(5)
                # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
                return self._answer('10.0.0.1', port)
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            return self._answer('10.0.0.2', port)

        gateway_dns_lb.socket.getaddrinfo = resolve

        def first_worker():
            results['a'] = gateway_dns_lb.ensure_snapshot('a.test', 80, 5)

        def second_worker():
            results['b'] = gateway_dns_lb.ensure_snapshot('b.test', 80, 5)
            second_done.set()

        first = threading.Thread(target=first_worker)
        second = threading.Thread(target=second_worker)
        first.daemon = True
        second.daemon = True
        first.start()
        first_entered.wait(2)
        self.assertTrue(_event_is_set(first_entered), 'first resolver did not start')
        second.start()
        second_done.wait(2)
        self.assertTrue(_event_is_set(second_done), 'second key was blocked by first DNS call')
        release_first.set()
        first.join(2)
        second.join(2)
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        self.assertEqual(results['a'], (('10.0.0.1', 80),))
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        self.assertEqual(results['b'], (('10.0.0.2', 80),))

    def test_refresh_failure_preserves_snapshot_and_cold_failure_is_empty(self):
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        gateway_dns_lb.socket.getaddrinfo = lambda host, port, family, socktype: self._answer('10.0.0.1', port)
        nodes = gateway_dns_lb.ensure_snapshot('rapid.test', 80, 5)
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        self.assertEqual(nodes, (('10.0.0.1', 80),))
        key = ('rapid.test', 80)
        with gateway_dns_lb._condition:
            state = gateway_dns_lb._states[key]
            state['resolving'] = True
            gateway_dns_lb._publish_locked(key, state, (), gateway_dns_lb._monotonic())
            self.assertEqual(state['nodes'], nodes)

        def fail(*_args):
            raise socket.gaierror('dns down')

        gateway_dns_lb.socket.getaddrinfo = fail
        self.assertEqual(gateway_dns_lb.ensure_snapshot('cold.test', 80, 5), ())

    def test_cold_failure_recovers_on_later_request(self):
        now = [1000.0]
        gateway_dns_lb._monotonic = lambda: now[0]
        calls = [0]

        def resolve(host, port, family, socktype):
            calls[0] += 1
            if calls[0] == 1:
                raise socket.gaierror('dns down')
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            return self._answer('10.0.0.2', port)

        gateway_dns_lb.socket.getaddrinfo = resolve
        self.assertEqual(gateway_dns_lb.ensure_snapshot('cold.test', 80, 5), ())
        now[0] += 5
        self.assertEqual(
            gateway_dns_lb.ensure_snapshot('cold.test', 80, 5),
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            (('10.0.0.2', 80),))
        self.assertEqual(calls[0], 2)

    def test_minimum_interval_and_idle_eviction(self):
        now = [1000.0]
        gateway_dns_lb._monotonic = lambda: now[0]
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        gateway_dns_lb.socket.getaddrinfo = lambda host, port, family, socktype: self._answer('10.0.0.1', port)
        gateway_dns_lb.ensure_snapshot('rapid.test', 80, 5)
        now[0] += 1
        gateway_dns_lb.ensure_snapshot('rapid.test', 80, 2)
        key = ('rapid.test', 80)
        with gateway_dns_lb._condition:
            state = gateway_dns_lb._states[key]
            self.assertEqual(state['interval'], 2.0)
            state['last_seen'] = now[0] - gateway_dns_lb._IDLE_TTL
            state['resolving'] = True
            gateway_dns_lb._evict_idle_locked(now[0])
            self.assertIn(key, gateway_dns_lb._states)
            state['resolving'] = False
            gateway_dns_lb._evict_idle_locked(now[0])
            self.assertNotIn(key, gateway_dns_lb._states)

    def test_pick_node_excludes_failed_nodes(self):
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        nodes = (('10.0.0.1', 80), ('10.0.0.2', 80))
        self.assertEqual(
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            gateway_dns_lb.pick_node(nodes, set([('10.0.0.1', 80)])),
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            ('10.0.0.2', 80))
        self.assertIsNone(gateway_dns_lb.pick_node(nodes, set(nodes)))

    def test_resolve_nodes_filters_empty_sockaddr_and_warns_on_empty_result(self):
        answers = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ()),
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('10.0.0.1', 80)),
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('10.0.0.1', 80)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, '',
             ('2001:db8::1', 80, 0, 0)),
        ]
        gateway_dns_lb.socket.getaddrinfo = (
            lambda host, port, family, socktype: answers)
        self.assertEqual(
            gateway_dns_lb._resolve_nodes('rapid.test', 80),
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            (('10.0.0.1', 80), ('2001:db8::1', 80)))

        gateway_dns_lb.socket.getaddrinfo = (
            lambda host, port, family, socktype: [
                (socket.AF_INET, socket.SOCK_STREAM, 6, '', ()),
                (socket.AF_INET, socket.SOCK_STREAM, 6, '', None),
            ])
        self.assertEqual(gateway_dns_lb._resolve_nodes('rapid.test', 80), ())
        # 全部结果非法时只返回空快照，不发布伪节点。
        self.assertEqual(gateway_dns_lb.ensure_snapshot('rapid.test', 80, 5), ())
        with gateway_dns_lb._condition:
            self.assertEqual(
                gateway_dns_lb._states[('rapid.test', 80)]['nodes'], ())

    def test_snapshot_does_not_publish_into_replaced_state(self):
        key = ('rapid.test', 80)
        replaced = {}

        def resolve(host, port, family, socktype):
            with gateway_dns_lb._condition:
                now = gateway_dns_lb._monotonic()
                fresh = {
                    'nodes': (),
                    'next_refresh': now + 100,
                    'last_seen': now,
                    'interval': 5.0,
                    'resolving': False,
                }
                gateway_dns_lb._states[key] = fresh
                replaced['state'] = fresh
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            return self._answer('10.0.0.1', port)

        gateway_dns_lb.socket.getaddrinfo = resolve
        # 解析期间 state 被 fork reset/淘汰替换，旧结果不得写入新 state。
        self.assertEqual(gateway_dns_lb.ensure_snapshot('rapid.test', 80, 5), ())
        self.assertEqual(replaced['state']['nodes'], ())
        self.assertFalse(replaced['state']['resolving'])

    def test_start_thread_locked_is_idempotent(self):
        created = []

        class _FakeThread(object):
            def __init__(self, target=None, name=None):
                self.target = target
                self.name = name
                self.daemon = False
                self.started = 0
                self.alive = False
                created.append(self)

            def start(self):
                self.started += 1
                self.alive = True

            def is_alive(self):
                return self.alive

        class _ThreadingShim(object):
            def __init__(self, real):
                self._real = real
                self.Thread = _FakeThread

            def __getattr__(self, name):
                return getattr(self._real, name)

        original_threading = gateway_dns_lb.threading
        gateway_dns_lb.threading = _ThreadingShim(original_threading)
        try:
            gateway_dns_lb._thread = None
            self.original_start_thread()
            self.original_start_thread()
            self.assertEqual(len(created), 1)
            self.assertEqual(created[0].started, 1)
            self.assertTrue(created[0].daemon)
            self.assertEqual(created[0].name, 'cos-gateway-dns-lb')
            self.assertTrue(gateway_dns_lb._thread is created[0])

            created[0].alive = False
            self.original_start_thread()
            self.assertEqual(len(created), 2)
            self.assertEqual(created[1].started, 1)
            self.assertTrue(gateway_dns_lb._thread is created[1])
        finally:
            gateway_dns_lb.threading = original_threading
            gateway_dns_lb._thread = None

    def test_resolving_state_returns_existing_snapshot_without_waiting(self):
        calls = []

        def resolve(host, port, family, socktype):
            calls.append((host, port))
            raise AssertionError('DNS must not be re-resolved')

        gateway_dns_lb.socket.getaddrinfo = resolve
        now = [1000.0]
        gateway_dns_lb._monotonic = lambda: now[0]
        gateway_dns_lb._COLD_WAIT_TIMEOUT = 0.05
        key = ('rapid.test', 80)
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        nodes = (('10.0.0.1', 80),)
        with gateway_dns_lb._condition:
            gateway_dns_lb._states[key] = {
                'nodes': nodes,
                'next_refresh': now[0] - 1,
                'last_seen': now[0],
                'interval': 5.0,
                'resolving': True,
            }

        # 刷新进行中但已有旧快照：立即返回旧快照，不等待也不重复解析。
        self.assertEqual(
            gateway_dns_lb.ensure_snapshot('rapid.test', 80, 5), nodes)

        # 无快照、未在解析且还没到下次刷新时间：直接返回空，不触发解析。
        with gateway_dns_lb._condition:
            gateway_dns_lb._states[key] = {
                'nodes': (),
                'next_refresh': now[0] + 100,
                'last_seen': now[0],
                'interval': 5.0,
                'resolving': False,
            }
        self.assertEqual(gateway_dns_lb.ensure_snapshot('rapid.test', 80, 5), ())
        self.assertEqual(calls, [])


class _FakeResponse(object):
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


class _SeekFailureBody(object):
    def tell(self):
        return 0

    def seek(self, _position):
        raise IOError('seek failed')

    def read(self, _size=-1):
        return b'body'


class _CloseFailureResponse(_FakeResponse):
    """底层响应关闭失败；资源清理是 best-effort，不能改变重试结果。"""

    def close(self):
        self.closed = True
        raise IOError('close failed')


class TestGatewayRequestPath(unittest.TestCase):
    def setUp(self):
        self.proxy_env = dict((name, os.environ.get(name)) for name in PROXY_ENV)
        for name in PROXY_ENV:
            os.environ.pop(name, None)
        self.original_ensure = gateway_dns_lb.ensure_snapshot
        self.original_pick = gateway_dns_lb.pick_node
        self.original_uniform = gateway_dns_lb.random.uniform
        self.original_sleep = cos_client_module.time.sleep

    def tearDown(self):
        gateway_dns_lb.ensure_snapshot = self.original_ensure
        gateway_dns_lb.pick_node = self.original_pick
        gateway_dns_lb.random.uniform = self.original_uniform
        cos_client_module.time.sleep = self.original_sleep
        for name, value in self.proxy_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def _client(self, retry=1, endpoint='cosrapid.ap-guangzhou.myqcloud.com'):
        conf = CosConfig(
            Region='ap-guangzhou',
            SecretId=BASE_AK,
            SecretKey=BASE_SK,
            Scheme='http',
            Endpoint=endpoint,
            EnableSessionAuth=True,
            EnableGatewayDnsLb=True)
        client = CosS3Client(conf, retry=retry)
        client._session.trust_env = False
        return client

    @staticmethod
    def _first_available(nodes, excluded=None):
        excluded = excluded or set()
        for node in nodes:
            if node not in excluded:
                return node
        return None

    def _install_nodes(self, nodes):
        gateway_dns_lb.ensure_snapshot = lambda host, port, interval: nodes
        gateway_dns_lb.pick_node = self._first_available

    @staticmethod
    def _install_transport(client, outcomes, records):
        def http_once(method, url, timeout, **kwargs):
            body = kwargs.get('data')
            payload = body.read() if hasattr(body, 'read') else body
            request = requests.Request(
                method, url, headers=kwargs.get('headers'),
                params=kwargs.get('params'), auth=kwargs.get('auth'))
            prepared = request.prepare()
            records.append({
                'url': prepared.url,
                'headers': dict(prepared.headers),
                'body': payload,
                'timeout': timeout,
                'allow_redirects': kwargs.get('allow_redirects', 'unset'),
            })
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        client._http_once = http_once

    @staticmethod
    def _no_sleep(client, delays):
        def delay(index):
            delays.append(index)
            return 0.0
        client._retry_delay = delay

    def _send(self, client, **kwargs):
        url = client._conf.uri(bucket=RAPID_BUCKET, path='key')
        values = {
            'method': 'GET',
            'url': url,
            'bucket': RAPID_BUCKET,
            'skip_session_auth': True,
            'auth': CosS3Auth(client._conf, 'key'),
        }
        values.update(kwargs)
        return client.send_request(**values)

    def test_ip_url_keeps_logical_host_and_signed_host(self):
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        nodes = (('10.0.0.1', 80), ('10.0.0.2', 80))
        self._install_nodes(nodes)
        client = self._client(retry=0)
        records = []
        self._install_transport(client, [_FakeResponse(200)], records)

        result = self._send(client)

        self.assertEqual(result.status_code, 200)
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        self.assertEqual(records[0]['url'], 'http://10.0.0.1:80/key')
        logical_host = 'rapid-x--1250000000.cosrapid.ap-guangzhou.myqcloud.com'
        self.assertEqual(records[0]['headers']['Host'], logical_host)
        self.assertIn('q-header-list=host', records[0]['headers']['Authorization'])

    def test_rapid_control_connects_proxy_service_but_signs_bucket_host(self):
        client = self._client(retry=0)
        records = []
        self._install_transport(client, [_FakeResponse(200)], records)
        logical_url = client._conf.uri(bucket=RAPID_BUCKET)

        result = client.send_request(
            method='PUT', url=logical_url, bucket=RAPID_BUCKET,
            auth=CosS3Auth(client._conf), skip_session_auth=True,
            _rapid_control_request=True)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            records[0]['url'],
            'http://service.cosrapid.ap-guangzhou.myqcloud.com/')
        self.assertEqual(
            records[0]['headers']['Host'],
            'rapid-x--1250000000.cosrapid.ap-guangzhou.myqcloud.com')
        auth_fields = dict(
            item.split('=', 1)
            for item in records[0]['headers']['Authorization'].split('&'))
        self.assertIn('host', auth_fields['q-header-list'].split(';'))

    def test_rapid_control_marker_does_not_change_ordinary_bucket(self):
        conf = CosConfig(
            Region='ap-guangzhou', SecretId=BASE_AK, SecretKey=BASE_SK,
            Scheme='http', Endpoint='cos.ap-guangzhou.myqcloud.com')
        client = CosS3Client(conf, retry=0)
        client._session.trust_env = False
        records = []
        self._install_transport(client, [_FakeResponse(200)], records)
        url = conf.uri(bucket=ORDINARY_BUCKET)

        result = client.send_request(
            method='PUT', url=url, bucket=ORDINARY_BUCKET,
            auth=CosS3Auth(conf), skip_session_auth=True,
            _rapid_control_request=True)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(records[0]['url'], url)

    def test_rapid_control_rejects_bucket_host_mismatch_before_network(self):
        conf = CosConfig(
            Region='ap-guangzhou', SecretId=BASE_AK, SecretKey=BASE_SK,
            Scheme='http', EnableRapidDomain=True,
            Domain=(
                'rapid-a-x--1250000000.cosrapid.'
                'ap-guangzhou.myqcloud.com'))
        client = CosS3Client(conf, retry=0)
        calls = []
        client._http_once = lambda *_args, **_kwargs: calls.append(True)
        url = conf.uri(bucket='rapid-b-x--1250000000')

        with self.assertRaises(CosClientError):
            client.send_request(
                method='PUT', url=url,
                bucket='rapid-b-x--1250000000',
                auth=CosS3Auth(conf), skip_session_auth=True,
                _rapid_control_request=True)
        self.assertEqual(calls, [])

    def test_rapid_list_buckets_service_request_signs_service_host(self):
        client = self._client(retry=0)
        records = []
        self._install_transport(client, [_FakeResponse(200)], records)
        service_url = (
            'http://service.cosrapid.ap-guangzhou.myqcloud.com/')

        result = client.send_request(
            method='GET', url=service_url, bucket=None,
            auth=CosS3Auth(client._conf))

        self.assertEqual(result.status_code, 200)
        self.assertEqual(records[0]['url'], service_url)
        auth_fields = dict(
            item.split('=', 1)
            for item in records[0]['headers']['Authorization'].split('&'))
        self.assertIn('host', auth_fields['q-header-list'].split(';'))

    def test_ipv6_url_is_bracketed(self):
        self.assertEqual(
            CosS3Client._gateway_ip_url(
                'http://rapid-x--1250000000.cosrapid.ap-guangzhou.myqcloud.com:9990/a?x=1',
                ('2001:db8::1', 9990)),
            'http://[2001:db8::1]:9990/a?x=1')

    def test_explicit_port_is_rejected_and_retry_uses_full_jitter(self):
        client = self._client(
            retry=0,
            endpoint='cosrapid.ap-guangzhou.myqcloud.com:9990')
        url = client._conf.uri(bucket=RAPID_BUCKET, path='key')
        with self.assertRaises(CosClientError):
            client._gateway_lb_context(url, RAPID_BUCKET)

        bounds = []
        slept = []

        def uniform(low, high):
            bounds.append((low, high))
            return high / 2.0

        gateway_dns_lb.random.uniform = uniform
        cos_client_module.time.sleep = lambda delay: slept.append(delay)
        self.assertEqual([client._retry_delay(index) for index in range(5)],
                         [0.1, 0.2, 0.4, 0.8, 1.0])
        self.assertEqual(bounds,
                         [(0, 0.2), (0, 0.4), (0, 0.8), (0, 1.6), (0, 2.0)])
        self.assertEqual(slept, [0.1, 0.2, 0.4, 0.8, 1.0])

    def test_connection_timeout_truncation_and_500_switch_nodes(self):
        failures = [
            ConnectionError('refused'),
            Timeout('timed out'),
            ChunkedEncodingError('truncated'),
            _FakeResponse(500, b'<Error/>'),
            _FakeResponse(502, b'<Error/>'),
            _FakeResponse(503, b'<Error/>'),
            _FakeResponse(504, b'<Error/>'),
        ]
        for failure in failures:
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            self._install_nodes((('10.0.0.1', 80), ('10.0.0.2', 80)))
            client = self._client(retry=1)
            records = []
            delays = []
            self._no_sleep(client, delays)
            self._install_transport(
                client, [failure, _FakeResponse(200)], records)

            result = self._send(client)

            self.assertEqual(result.status_code, 200)
            self.assertEqual(
                [record['url'] for record in records],
                # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
                ['http://10.0.0.1:80/key', 'http://10.0.0.2:80/key'])
            self.assertNotIn('x-cos-sdk-retry', records[0]['headers'])
            self.assertEqual(records[1]['headers']['x-cos-sdk-retry'], 'true')
            self.assertEqual(delays, [0])
            if isinstance(failure, _FakeResponse):
                self.assertTrue(failure.closed)

    def test_create_session_uses_proxy_service_with_bucket_signature(self):
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        self._install_nodes((('10.0.0.1', 80),))
        client = self._client(retry=0)
        records = []
        body = (
            b'<CreateSessionResult><Credentials>'
            b'<AccessKeyId>session-ak</AccessKeyId>'
            b'<SecretAccessKey>session-sk</SecretAccessKey>'
            b'<SessionToken>session-token</SessionToken>'
            b'<Expiration>2099-01-01T00:00:00Z</Expiration>'
            b'</Credentials></CreateSessionResult>')
        self._install_transport(client, [_FakeResponse(200, body)], records)

        result = client.create_session(Bucket=RAPID_BUCKET)

        self.assertEqual(result['Credentials']['AccessKeyId'], 'session-ak')
        self.assertEqual(
            records[0]['url'],
            'http://service.cosrapid.ap-guangzhou.myqcloud.com/?session=')
        self.assertEqual(
            records[0]['headers']['Host'],
            'rapid-x--1250000000.cosrapid.ap-guangzhou.myqcloud.com')
        self.assertIn('q-ak=' + BASE_AK, records[0]['headers']['Authorization'])

    def test_rename_does_not_replay_ambiguous_failures(self):
        failures = [
            ConnectionError('response lost'),
            Timeout('response timed out'),
            ChunkedEncodingError('response truncated'),
            _FakeResponse(500, b'<Error><Code>InternalError</Code></Error>'),
        ]
        for failure in failures:
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            self._install_nodes((('10.0.0.1', 80), ('10.0.0.2', 80)))
            client = self._client(retry=3)
            records = []
            delays = []
            self._no_sleep(client, delays)
            self._install_transport(client, [failure], records)
            client._apply_session_credential = lambda *_args, **_kwargs: None

            if isinstance(failure, _FakeResponse):
                with self.assertRaises(CosServiceError):
                    client.rename_object(
                        Bucket=RAPID_BUCKET, Key='dst', RenameSource='src')
                self.assertFalse(failure.closed)
            else:
                with self.assertRaises(CosClientError):
                    client.rename_object(
                        Bucket=RAPID_BUCKET, Key='dst', RenameSource='src')
            self.assertEqual(len(records), 1)
            self.assertEqual(delays, [])

    def test_rename_still_retries_session_403_once_on_same_node(self):
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        self._install_nodes((('10.0.0.1', 80), ('10.0.0.2', 80)))
        client = self._client(retry=3)
        records = []
        first = _FakeResponse(403, b'<Error/>')
        self._install_transport(client, [first, _FakeResponse(200)], records)
        applied = []
        client._apply_session_credential = lambda bucket, kwargs, mode=None, force_refresh=False: applied.append(
            (bucket, force_refresh))
        client._session_provider.evict = lambda bucket: True

        client.rename_object(
            Bucket=RAPID_BUCKET, Key='dst', RenameSource='src')

        self.assertEqual(
            [record['url'] for record in records],
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            ['http://10.0.0.1:80/dst'] * 2)
        self.assertTrue(first.closed)
        self.assertEqual(applied, [(RAPID_BUCKET, False), (RAPID_BUCKET, True)])

    def test_ordinary_4xx_does_not_retry_or_fallback(self):
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        self._install_nodes((('10.0.0.1', 80), ('10.0.0.2', 80)))
        client = self._client(retry=3)
        records = []
        response = _FakeResponse(404, b'<Error><Code>NoSuchKey</Code></Error>')
        self._install_transport(client, [response], records)
        with self.assertRaises(CosServiceError):
            self._send(client)
        self.assertEqual(len(records), 1)
        self.assertFalse(response.closed)

    def test_retry_zero_still_uses_one_logical_host_fallback(self):
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        self._install_nodes((('10.0.0.1', 80),))
        client = self._client(retry=0)
        records = []
        delays = []
        self._no_sleep(client, delays)
        self._install_transport(
            client, [ConnectionError('down'), _FakeResponse(200),
                     _FakeResponse(200)], records)

        result = self._send(client)
        next_result = self._send(client)

        logical_url = client._conf.uri(bucket=RAPID_BUCKET, path='key')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(next_result.status_code, 200)
        self.assertEqual(
            [record['url'] for record in records],
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            ['http://10.0.0.1:80/key', logical_url,
             # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
             'http://10.0.0.1:80/key'])
        self.assertEqual(delays, [0])

    def test_ip_retry_budget_cycles_nodes_before_domain_fallback(self):
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        self._install_nodes((('10.0.0.1', 80), ('10.0.0.2', 80)))
        client = self._client(retry=3)
        records = []
        delays = []
        self._no_sleep(client, delays)
        self._install_transport(
            client,
            [ConnectionError('a1'), ConnectionError('b1'),
             ConnectionError('a2'), ConnectionError('b2'), _FakeResponse(200)],
            records)

        result = self._send(client)

        logical_url = client._conf.uri(bucket=RAPID_BUCKET, path='key')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            [record['url'] for record in records],
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            ['http://10.0.0.1:80/key', 'http://10.0.0.2:80/key',
             # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
             'http://10.0.0.1:80/key', 'http://10.0.0.2:80/key',
             logical_url])
        self.assertEqual(delays, [0, 1, 2, 3])

    def test_cold_dns_failure_uses_domain_retry_budget_without_extra_fallback(self):
        self._install_nodes(())
        client = self._client(retry=1)
        records = []
        delays = []
        self._no_sleep(client, delays)
        self._install_transport(
            client, [ConnectionError('down'), _FakeResponse(500, b'<Error/>')], records)
        with self.assertRaises(CosServiceError):
            self._send(client)
        logical_url = client._conf.uri(bucket=RAPID_BUCKET, path='key')
        self.assertEqual([record['url'] for record in records], [logical_url, logical_url])
        self.assertEqual(delays, [0])

    def test_seekable_body_is_rewound_before_node_retry(self):
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        self._install_nodes((('10.0.0.1', 80), ('10.0.0.2', 80)))
        client = self._client(retry=1)
        records = []
        self._no_sleep(client, [])
        self._install_transport(
            client, [ConnectionError('down'), _FakeResponse(200)], records)
        body = BytesIO(b'xxpayload')
        body.seek(2)

        result = self._send(client, method='PUT', data=body)

        self.assertEqual(result.status_code, 200)
        self.assertEqual([record['body'] for record in records], [b'payload', b'payload'])

    def test_generator_and_seek_failure_send_only_once(self):
        bodies = [
            (chunk for chunk in [b'payload']),
            _SeekFailureBody(),
        ]
        for body in bodies:
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            self._install_nodes((('10.0.0.1', 80), ('10.0.0.2', 80)))
            client = self._client(retry=1)
            records = []
            self._no_sleep(client, [])
            self._install_transport(client, [ConnectionError('down')], records)
            with self.assertRaises(CosClientError):
                self._send(client, method='PUT', data=body)
            self.assertEqual(len(records), 1)

    def test_ordinary_generator_transport_error_has_no_unbound_response(self):
        conf = CosConfig(
            Region='ap-guangzhou', SecretId=BASE_AK, SecretKey=BASE_SK,
            Scheme='http', Endpoint='cos.ap-guangzhou.tencentcos.com')
        client = CosS3Client(conf, retry=1)
        client._session.trust_env = False
        records = []
        self._install_transport(client, [ConnectionError('down')], records)
        body = (chunk for chunk in [b'payload'])
        url = conf.uri(bucket=ORDINARY_BUCKET, path='key')
        with self.assertRaises(CosClientError):
            client.send_request(method='PUT', url=url, bucket=ORDINARY_BUCKET,
                                data=body, auth=CosS3Auth(conf, 'key'))
        self.assertEqual(len(records), 1)

    def _ordinary_redirect_probe(self, allow_redirects_conf, **send_kwargs):
        conf = CosConfig(
            Region='ap-guangzhou', SecretId=BASE_AK, SecretKey=BASE_SK,
            Scheme='http', Endpoint='cos.ap-guangzhou.tencentcos.com',
            AllowRedirects=allow_redirects_conf)
        client = CosS3Client(conf, retry=1)
        client._session.trust_env = False
        records = []
        self._install_transport(client, [_FakeResponse(200)], records)
        url = conf.uri(bucket=ORDINARY_BUCKET, path='key')
        client.send_request(method='GET', url=url, bucket=ORDINARY_BUCKET,
                            auth=CosS3Auth(conf, 'key'), **send_kwargs)
        self.assertEqual(len(records), 1)
        return records[0]['allow_redirects']

    def test_ordinary_allow_redirects_keeps_upstream_config_priority(self):
        # 与 upstream/master 一致：配置非 None 时总覆盖单次 kwargs。
        self.assertIs(self._ordinary_redirect_probe(False, allow_redirects=True), False)
        self.assertIs(self._ordinary_redirect_probe(True, allow_redirects=False), True)
        self.assertIs(self._ordinary_redirect_probe(False), False)
        self.assertIs(self._ordinary_redirect_probe(True), True)
        # 配置 None 时保留调用方 kwargs，或不传（由 requests 自行决定）。
        self.assertIs(self._ordinary_redirect_probe(None, allow_redirects=True), True)
        self.assertIs(self._ordinary_redirect_probe(None, allow_redirects=False), False)
        self.assertEqual(self._ordinary_redirect_probe(None), 'unset')

    def test_create_session_never_follows_redirect_regardless_of_config(self):
        session_xml = (
            b'<CreateSessionResult><Credentials>'
            b'<AccessKeyId>SKIDSESSION</AccessKeyId>'
            b'<SecretAccessKey>session-secret</SecretAccessKey>'
            b'<SessionToken>session-token</SessionToken>'
            b'<Expiration>2099-01-01T00:00:00Z</Expiration>'
            b'</Credentials></CreateSessionResult>'
        )
        for allow_redirects_conf in (True, None):
            conf = CosConfig(
                Region='ap-guangzhou', SecretId=BASE_AK, SecretKey=BASE_SK,
                Scheme='http', Endpoint='cosrapid.ap-guangzhou.myqcloud.com',
                EnableSessionAuth=True, AllowRedirects=allow_redirects_conf)
            client = CosS3Client(conf, retry=1)
            client._session.trust_env = False
            records = []
            self._install_transport(client, [_FakeResponse(200, session_xml)], records)
            client.create_session(Bucket=RAPID_BUCKET)
            self.assertEqual(len(records), 1)
            self.assertIs(records[0]['allow_redirects'], False)

    def test_client_can_retry_preserves_legacy_body_contract(self):
        self.assertTrue(client_can_retry(None))
        self.assertFalse(client_can_retry(None, data=None))
        self.assertTrue(client_can_retry(None, data=b'payload'))
        self.assertTrue(client_can_retry(None, data=u'payload'))
        body = BytesIO(b'xxpayload')
        body.read()
        self.assertTrue(client_can_retry(2, data=body))
        self.assertEqual(body.read(), b'payload')
        self.assertFalse(client_can_retry(None, data=body))
        self.assertFalse(client_can_retry(0, data=_SeekFailureBody()))
        self.assertFalse(client_can_retry(None, data=iter([b'payload'])))

    def test_non_lb_retry_keeps_ordinary_and_rapid_body_semantics_separate(self):
        cos_client_module.time.sleep = lambda delay: None
        for bucket in (ORDINARY_BUCKET, RAPID_BUCKET):
            for transport_error in (True, False):
                client = self._client(retry=1)
                client._conf._enable_gateway_dns_lb = False
                url = client._conf.uri(bucket=bucket, path='key')
                records = []
                first = (ConnectionError('down') if transport_error else
                         _FakeResponse(500, b'<Error><Code>InternalError</Code></Error>'))
                self._install_transport(client, [first, _FakeResponse(200)], records)
                try:
                    # Explicit None was not replayable in the legacy helper;
                    # Rapid treats it as no body, even when DNS LB is disabled.
                    if bucket == ORDINARY_BUCKET:
                        error = CosClientError if transport_error else CosServiceError
                        with self.assertRaises(error):
                            self._send(client, bucket=bucket, url=url, data=None)
                        self.assertEqual(len(records), 1)
                    else:
                        self.assertEqual(self._send(client, bucket=bucket, url=url, data=None).status_code, 200)
                        self.assertEqual(len(records), 2)
                finally:
                    client._session.close()

    def test_non_rewindable_500_preserves_service_response(self):
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        self._install_nodes((('10.0.0.1', 80), ('10.0.0.2', 80)))
        client = self._client(retry=1)
        records = []
        response = _FakeResponse(500, b'<Error><Code>InternalError</Code></Error>')
        self._install_transport(client, [response], records)
        body = (chunk for chunk in [b'payload'])
        with self.assertRaises(CosServiceError):
            self._send(client, method='PUT', data=body)
        self.assertEqual(len(records), 1)
        self.assertFalse(response.closed)

    def test_session_403_resigns_once_on_same_node_without_delay(self):
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        self._install_nodes((('10.0.0.1', 80), ('10.0.0.2', 80)))
        client = self._client(retry=1)
        records = []
        delays = []
        self._no_sleep(client, delays)
        first = _FakeResponse(403, b'<Error/>')
        self._install_transport(client, [first, _FakeResponse(200)], records)
        applied = []
        client._apply_session_credential = lambda bucket, kwargs, mode=None, force_refresh=False: applied.append(
            (bucket, force_refresh))
        client._session_provider.evict = lambda bucket: True

        url = client._conf.uri(bucket=RAPID_BUCKET, path='key')
        result = client.send_request(
            method='GET', url=url, bucket=RAPID_BUCKET,
            auth=CosS3Auth(client._conf, 'key'),
            _rapid_data_request=True)

        self.assertEqual(result.status_code, 200)
        self.assertTrue(first.closed)
        self.assertEqual([record['url'] for record in records],
                         # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
                         ['http://10.0.0.1:80/key'] * 2)
        self.assertEqual(records[1]['headers']['x-cos-sdk-retry'], 'true')
        self.assertEqual(delays, [])
        self.assertEqual(applied, [(RAPID_BUCKET, False), (RAPID_BUCKET, True)])

    def test_second_session_403_is_not_retried(self):
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        self._install_nodes((('10.0.0.1', 80), ('10.0.0.2', 80)))
        client = self._client(retry=3)
        records = []
        delays = []
        self._no_sleep(client, delays)
        first = _FakeResponse(403, b'<Error/>')
        second = _FakeResponse(403, b'<Error/>')
        self._install_transport(client, [first, second], records)
        applied = []
        client._apply_session_credential = lambda bucket, kwargs, mode=None, force_refresh=False: applied.append(
            (bucket, force_refresh))
        client._session_provider.evict = lambda bucket: True

        url = client._conf.uri(bucket=RAPID_BUCKET, path='key')
        with self.assertRaises(CosServiceError):
            client.send_request(
                method='GET', url=url, bucket=RAPID_BUCKET,
                auth=CosS3Auth(client._conf, 'key'),
                _rapid_data_request=True)

        self.assertEqual(len(records), 2)
        self.assertEqual([record['url'] for record in records],
                         # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
                         ['http://10.0.0.1:80/key'] * 2)
        self.assertTrue(first.closed)
        self.assertFalse(second.closed)
        self.assertEqual(delays, [])
        self.assertEqual(applied, [(RAPID_BUCKET, False), (RAPID_BUCKET, True)])

    def test_failed_nodes_and_budget_are_request_local(self):
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        self._install_nodes((('10.0.0.1', 80), ('10.0.0.2', 80)))
        client = self._client(retry=1)
        records = []
        self._no_sleep(client, [])
        self._install_transport(
            client,
            [ConnectionError('down'), _FakeResponse(200), _FakeResponse(200)],
            records)

        self._send(client)
        self._send(client)

        self.assertEqual(
            [record['url'] for record in records],
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            ['http://10.0.0.1:80/key',
             # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
             'http://10.0.0.2:80/key',
             # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
             'http://10.0.0.1:80/key'])

    def _send_data_plane(self, client, **kwargs):
        """走真实数据面分支（use_session=True），凭证由调用方 stub。"""
        url = client._conf.uri(bucket=RAPID_BUCKET, path=kwargs.pop('path', 'key'))
        values = {
            'method': 'GET',
            'url': url,
            'bucket': RAPID_BUCKET,
            'auth': CosS3Auth(client._conf, 'key'),
            '_rapid_data_request': True,
        }
        values.update(kwargs)
        return client.send_request(**values)

    @staticmethod
    def _stub_session(client, applied, evicted=None):
        def apply(bucket, kwargs, mode=None, force_refresh=False):
            applied.append((bucket, force_refresh))

        def evict(bucket):
            if evicted is not None:
                evicted.append(bucket)
            return True

        client._apply_session_credential = apply
        client._session_provider.evict = evict

    def test_response_close_failure_does_not_block_session_or_5xx_retry(self):
        # 1. session 403：close 抛异常仍要重签并重试一次。
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        self._install_nodes((('10.0.0.1', 80), ('10.0.0.2', 80)))
        client = self._client(retry=1)
        records = []
        delays = []
        self._no_sleep(client, delays)
        forbidden = _CloseFailureResponse(403, b'<Error/>')
        self._install_transport(client, [forbidden, _FakeResponse(200)], records)
        applied = []
        evicted = []
        self._stub_session(client, applied, evicted)

        result = self._send_data_plane(client)

        self.assertEqual(result.status_code, 200)
        self.assertTrue(forbidden.closed)
        self.assertEqual([record['url'] for record in records],
                         # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
                         ['http://10.0.0.1:80/key'] * 2)
        self.assertEqual(records[1]['headers']['x-cos-sdk-retry'], 'true')
        self.assertEqual(applied, [(RAPID_BUCKET, False), (RAPID_BUCKET, True)])
        self.assertEqual(evicted, [RAPID_BUCKET])
        self.assertEqual(delays, [])

        # 2. HTTP 500：close 抛异常仍要换节点重试。
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        self._install_nodes((('10.0.0.1', 80), ('10.0.0.2', 80)))
        client = self._client(retry=1)
        records = []
        delays = []
        self._no_sleep(client, delays)
        failure = _CloseFailureResponse(500, b'<Error/>')
        self._install_transport(client, [failure, _FakeResponse(200)], records)

        result = self._send(client)

        self.assertEqual(result.status_code, 200)
        self.assertTrue(failure.closed)
        self.assertEqual([record['url'] for record in records],
                         # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
                         ['http://10.0.0.1:80/key', 'http://10.0.0.2:80/key'])
        self.assertEqual(delays, [0])

    def test_non_rewindable_session_403_does_not_resign_or_retry(self):
        bodies = [
            lambda: (chunk for chunk in [b'payload']),
            _SeekFailureBody,
        ]
        for make_body in bodies:
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            self._install_nodes((('10.0.0.1', 80), ('10.0.0.2', 80)))
            client = self._client(retry=1)
            records = []
            delays = []
            self._no_sleep(client, delays)
            forbidden = _FakeResponse(
                403, b'<Error><Code>AccessDenied</Code></Error>')
            self._install_transport(client, [forbidden], records)
            applied = []
            evicted = []
            self._stub_session(client, applied, evicted)

            with self.assertRaises(CosServiceError):
                self._send_data_plane(
                    client, method='PUT', data=make_body())

            # 不可回退 body 收到 403：既不重签也不重发，原响应交给调用方处理。
            self.assertEqual(len(records), 1)
            self.assertFalse(forbidden.closed)
            self.assertEqual(evicted, [])
            self.assertEqual(applied, [(RAPID_BUCKET, False)])
            self.assertEqual(delays, [])

    def test_unexpected_transport_exception_is_not_retried(self):
        for error in (ValueError('bad chunk'), RuntimeError('boom')):
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            self._install_nodes((('10.0.0.1', 80), ('10.0.0.2', 80)))
            client = self._client(retry=3)
            records = []
            delays = []
            self._no_sleep(client, delays)
            self._install_transport(client, [error], records)

            with self.assertRaises(CosClientError) as caught:
                self._send(client)

            self.assertIn(str(error), str(caught.exception))
            self.assertEqual([record['url'] for record in records],
                             # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
                             ['http://10.0.0.1:80/key'])
            self.assertEqual(delays, [])

    def test_http_5xx_exhausts_gateway_nodes_then_uses_domain_once(self):
        # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
        self._install_nodes((('10.0.0.1', 80), ('10.0.0.2', 80)))
        client = self._client(retry=1)
        records = []
        delays = []
        self._no_sleep(client, delays)
        failures = [_FakeResponse(500, b'<Error/>'),
                    _FakeResponse(503, b'<Error/>')]
        self._install_transport(
            client, failures + [_FakeResponse(200)], records)

        result = self._send(client)

        logical_url = client._conf.uri(bucket=RAPID_BUCKET, path='key')
        logical_host = 'rapid-x--1250000000.cosrapid.ap-guangzhou.myqcloud.com'
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            [record['url'] for record in records],
            # NOCA:InnerIPLeak(Mock test address),ip_check(Fixed address for unit tests)
            ['http://10.0.0.1:80/key', 'http://10.0.0.2:80/key', logical_url])
        # 每个 5xx 响应都要按次关闭，逻辑域名只兜底一次。
        self.assertEqual([failure.closed for failure in failures], [True, True])
        self.assertEqual(delays, [0, 1])
        self.assertEqual([record['headers']['Host'] for record in records],
                         [logical_host] * 3)
        for record in records:
            fields = dict(
                item.split('=', 1)
                for item in record['headers']['Authorization'].split('&'))
            self.assertEqual(fields['q-ak'], BASE_AK)
            self.assertIn('host', fields['q-header-list'].split(';'))


if __name__ == '__main__':
    unittest.main()
