# -*- coding: utf-8 -*-
"""HTTP Rapid Gateway DNS LB 本机双节点、刷新和 fork 验证。"""

import json
import os
import select
import signal
import socket
import threading
import time
import unittest

try:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
    from SocketServer import ThreadingMixIn
except ImportError:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from socketserver import ThreadingMixIn

from qcloud_cos import CosConfig, CosS3Auth, CosS3Client
from qcloud_cos import gateway_dns_lb


RAPID_BUCKET_A = 'rapid-a-x--1250000000'
RAPID_BUCKET_B = 'rapid-b-x--1250000000'
BASE_AK = 'AKIDBASE'
BASE_SK = 'base-secret'
PROXY_ENV = ('http_proxy', 'HTTP_PROXY', 'all_proxy', 'ALL_PROXY')


class _GatewayState(object):
    def __init__(self, name):
        self.name = name
        self.status = 200
        self.records = []
        self.lock = threading.Lock()

    def record(self, handler):
        with self.lock:
            self.records.append({
                'host': handler.headers.get('Host'),
                'path': handler.path,
                'client_port': handler.client_address[1],
                'status': self.status,
            })
            return self.status


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class _GatewayHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, _format, *_args):
        return

    def _handle(self):
        length = int(self.headers.get('Content-Length') or 0)
        if length:
            self.rfile.read(length)
        status = self.server.state.record(self)
        body = self.server.state.name.encode('ascii')
        self.send_response(status)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    do_GET = _handle
    do_PUT = _handle
    do_POST = _handle
    do_DELETE = _handle
    do_HEAD = _handle


class _GatewayServer(object):
    def __init__(self, host, port, name):
        self.httpd = _ThreadingHTTPServer((host, port), _GatewayHandler)
        self.httpd.state = _GatewayState(name)
        self.host, self.port = self.httpd.server_address[:2]
        self.thread = threading.Thread(target=self.httpd.serve_forever)
        self.thread.daemon = True
        self.thread.start()

    @property
    def state(self):
        return self.httpd.state

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(3)


class TestGatewayLbIntegration(unittest.TestCase):
    _SESSION_ATTR = '_CosS3Client__built_in_sessions'
    _PID_ATTR = '_CosS3Client__built_in_pid'
    _LOCKS_ATTR = '_CosS3Client__built_in_locks'

    def setUp(self):
        self.proxy_env = dict((name, os.environ.get(name)) for name in PROXY_ENV)
        for name in PROXY_ENV:
            os.environ.pop(name, None)
        self.original_session = getattr(CosS3Client, self._SESSION_ATTR)
        self.original_pid = getattr(CosS3Client, self._PID_ATTR)
        self.original_locks = getattr(CosS3Client, self._LOCKS_ATTR)
        setattr(CosS3Client, self._SESSION_ATTR, None)
        setattr(CosS3Client, self._PID_ATTR, 0)
        setattr(CosS3Client, self._LOCKS_ATTR, {})
        self.original_ensure = gateway_dns_lb.ensure_snapshot
        self.original_pick = gateway_dns_lb.pick_node
        self.servers = []

    def tearDown(self):
        current_session = getattr(CosS3Client, self._SESSION_ATTR)
        if current_session is not None and current_session is not self.original_session:
            current_session.close()
        setattr(CosS3Client, self._SESSION_ATTR, self.original_session)
        setattr(CosS3Client, self._PID_ATTR, self.original_pid)
        setattr(CosS3Client, self._LOCKS_ATTR, self.original_locks)
        gateway_dns_lb.ensure_snapshot = self.original_ensure
        gateway_dns_lb.pick_node = self.original_pick
        for server in reversed(self.servers):
            server.close()
        for name, value in self.proxy_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def _start_gateways(self):
        first = _GatewayServer('127.0.0.1', 0, 'A')
        self.servers.append(first)
        # NOCA:InnerIPLeak(Loopback address for local HTTP fixtures)
        second = _GatewayServer('127.0.0.2', first.port, 'B')
        self.servers.append(second)
        return first, second

    def _client(self, _port, retry=1,
                endpoint_host='cosrapid.ap-guangzhou.myqcloud.com'):
        conf = CosConfig(
            Region='ap-guangzhou',
            SecretId=BASE_AK,
            SecretKey=BASE_SK,
            Scheme='http',
            Endpoint=endpoint_host,
            EnableSessionAuth=True,
            EnableGatewayDnsLb=True,
            GatewayDnsRefreshInterval=1,
            Timeout=3)
        client = CosS3Client(conf, retry=retry)
        client._session.trust_env = False
        client._retry_delay = lambda _index: 0.0
        return client

    @staticmethod
    def _first_available(nodes, excluded=None):
        excluded = excluded or set()
        for node in nodes:
            if node not in excluded:
                return node
        return None

    def _send(self, client, bucket):
        url = client._conf.uri(bucket=bucket, path='key')
        return client.send_request(
            method='GET', url=url, bucket=bucket, skip_session_auth=True,
            auth=CosS3Auth(client._conf, 'key'))

    def test_shared_standard_pool_keeps_hosts_separate(self):
        first, _second = self._start_gateways()
        nodes = (('127.0.0.1', first.port),)
        gateway_dns_lb.ensure_snapshot = lambda host, port, interval: nodes
        gateway_dns_lb.pick_node = self._first_available
        first_client = self._client(first.port, retry=0)
        second_client = self._client(first.port, retry=0)
        self.assertIs(first_client._session, second_client._session)

        self._send(first_client, RAPID_BUCKET_A)
        self._send(second_client, RAPID_BUCKET_B)

        with first.state.lock:
            records = list(first.state.records)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]['client_port'], records[1]['client_port'])
        self.assertEqual(
            [record['host'] for record in records],
            ['rapid-a-x--1250000000.cosrapid.ap-guangzhou.myqcloud.com',
             'rapid-b-x--1250000000.cosrapid.ap-guangzhou.myqcloud.com'])

    def test_single_node_failure_and_same_client_recovery(self):
        first, second = self._start_gateways()
        # NOCA:InnerIPLeak(Loopback address for local HTTP fixtures)
        nodes = (('127.0.0.1', first.port), ('127.0.0.2', first.port))
        gateway_dns_lb.ensure_snapshot = lambda host, port, interval: nodes
        gateway_dns_lb.pick_node = self._first_available
        client = self._client(first.port, retry=1)
        first.state.status = 500

        failed_over = self._send(client, RAPID_BUCKET_A)
        self.assertEqual(failed_over.content, b'B')

        first.state.status = 200
        recovered = self._send(client, RAPID_BUCKET_A)
        self.assertEqual(recovered.content, b'A')
        with first.state.lock:
            first_records = list(first.state.records)
        with second.state.lock:
            second_records = list(second.state.records)
        self.assertEqual([record['status'] for record in first_records], [500, 200])
        self.assertEqual([record['status'] for record in second_records], [200])

    @unittest.skipUnless(hasattr(os, 'fork'), 'requires os.fork')
    def test_z_dns_refresh_and_fork_rebuild_state_and_socket(self):
        first, second = self._start_gateways()
        original_getaddrinfo = socket.getaddrinfo
        selected_ip = ['127.0.0.1']
        failed_refresh = threading.Event()

        def resolve(host, port, family=0, socktype=0, proto=0, flags=0):
            if host.endswith('.cosrapid.ap-guangzhou.myqcloud.com'):
                if selected_ip[0] is None:
                    failed_refresh.set()
                    raise socket.gaierror('injected DNS failure')
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, '',
                         (selected_ip[0], first.port))]
            return original_getaddrinfo(host, port, family, socktype, proto, flags)

        gateway_dns_lb._condition = threading.Condition()
        gateway_dns_lb._states = {}
        gateway_dns_lb._pid = os.getpid()
        gateway_dns_lb._thread = None
        socket.getaddrinfo = resolve
        try:
            client = self._client(first.port, retry=0)
            parent_session = client._session
            first_response = self._send(client, RAPID_BUCKET_A)
            self.assertEqual(first_response.content, b'A')
            key = (
                'rapid-a-x--1250000000.cosrapid.ap-guangzhou.myqcloud.com',
                80)
            refresh_thread = gateway_dns_lb._thread

            selected_ip[0] = None
            self._force_failed_refresh(key, failed_refresh)
            with gateway_dns_lb._condition:
                self.assertEqual(
                    gateway_dns_lb._states[key]['nodes'],
                    (('127.0.0.1', first.port),))
            self.assertIs(gateway_dns_lb._thread, refresh_thread)

            # NOCA:InnerIPLeak(Loopback address for local HTTP fixtures)
            selected_ip[0] = '127.0.0.2'
            # NOCA:InnerIPLeak(Loopback address for local HTTP fixtures)
            self._force_refresh(key, (('127.0.0.2', first.port),))
            self.assertIs(gateway_dns_lb._thread, refresh_thread)
            refreshed = self._send(client, RAPID_BUCKET_A)
            self.assertEqual(refreshed.content, b'B')

            selected_ip[0] = '127.0.0.1'
            self._force_refresh(key, (('127.0.0.1', first.port),))
            recovered = self._send(client, RAPID_BUCKET_A)
            self.assertEqual(recovered.content, b'A')

            parent_condition = gateway_dns_lb._condition
            parent_condition.acquire()
            read_fd, write_fd = os.pipe()
            child_pid = os.fork()
            if child_pid == 0:
                try:
                    os.close(read_fd)
                    # NOCA:InnerIPLeak(Loopback address for local HTTP fixtures)
                    selected_ip[0] = '127.0.0.2'
                    child_response = self._send(client, RAPID_BUCKET_A)
                    result = {
                        'content': child_response.content.decode('ascii'),
                        'dns_pid': gateway_dns_lb._pid,
                        'nodes': gateway_dns_lb._states[key]['nodes'],
                        'new_condition': gateway_dns_lb._condition is not parent_condition,
                        'new_session': client._session is not parent_session,
                    }
                    os.write(write_fd, json.dumps(result).encode('utf-8'))
                finally:
                    os.close(write_fd)
                    os._exit(0)

            os.close(write_fd)
            try:
                readable, _, _ = select.select([read_fd], [], [], 5)
                self.assertTrue(readable, 'child blocked on an inherited DNS/session lock')
                result = json.loads(os.read(read_fd, 8192).decode('utf-8'))
                self.assertEqual(result['content'], 'B')
                self.assertEqual(result['dns_pid'], child_pid)
                # NOCA:InnerIPLeak(Loopback address for local HTTP fixtures)
                self.assertEqual(result['nodes'], [['127.0.0.2', first.port]])
                self.assertTrue(result['new_condition'])
                self.assertTrue(result['new_session'])
                _, status = os.waitpid(child_pid, 0)
                self.assertTrue(os.WIFEXITED(status))
                self.assertEqual(os.WEXITSTATUS(status), 0)
            finally:
                os.close(read_fd)
                parent_condition.release()
                try:
                    waited_pid, _ = os.waitpid(child_pid, os.WNOHANG)
                except OSError:
                    waited_pid = child_pid
                if waited_pid == 0:
                    os.kill(child_pid, signal.SIGKILL)
                    os.waitpid(child_pid, 0)

            with second.state.lock:
                second_records = list(second.state.records)
            self.assertGreaterEqual(len(second_records), 2)
        finally:
            socket.getaddrinfo = original_getaddrinfo
            with gateway_dns_lb._condition:
                gateway_dns_lb._states.clear()
                gateway_dns_lb._condition.notify_all()

    def _force_refresh(self, key, expected_nodes):
        deadline = time.time() + 5
        with gateway_dns_lb._condition:
            state = gateway_dns_lb._states[key]
            state['next_refresh'] = gateway_dns_lb._monotonic()
            gateway_dns_lb._condition.notify_all()
            while state['nodes'] != expected_nodes or state['resolving']:
                remaining = deadline - time.time()
                if remaining <= 0:
                    self.fail('DNS refresh did not publish %r' % (expected_nodes,))
                gateway_dns_lb._condition.wait(remaining)

    def _force_failed_refresh(self, key, failed_refresh):
        deadline = time.time() + 5
        with gateway_dns_lb._condition:
            state = gateway_dns_lb._states[key]
            state['next_refresh'] = gateway_dns_lb._monotonic()
            gateway_dns_lb._condition.notify_all()
        failed_refresh.wait(5)
        self.assertTrue(failed_refresh.is_set() if hasattr(failed_refresh, 'is_set')
                        else failed_refresh.isSet())
        with gateway_dns_lb._condition:
            while state['resolving']:
                remaining = deadline - time.time()
                if remaining <= 0:
                    self.fail('failed DNS refresh did not finish')
                gateway_dns_lb._condition.wait(remaining)


if __name__ == '__main__':
    unittest.main()
