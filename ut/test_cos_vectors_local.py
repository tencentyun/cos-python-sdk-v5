# -*- coding=utf-8
"""COS Vectors 与 Native API 本地单测。不依赖 COS 环境变量或真实网络，手动执行:

    python -m unittest ut.test_cos_vectors_local
"""

import hashlib
import hmac
import json
import threading
import time
import unittest

from requests.structures import CaseInsensitiveDict
from six.moves.urllib.parse import quote

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
except ImportError:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

from qcloud_cos import CosClientError, CosConfig, CosServiceError, CosVectorsClient
from qcloud_cos.cos_comm import to_bytes

SECRET_ID = 'AKIDvectorslocaltest'
SECRET_KEY = 'vectorslocaltestsecret'
REGION = 'ap-guangzhou'
BUCKET = 'examplebucket-1250000000'
SERVICE_HOST = 'vectors.ap-guangzhou.coslake.com'
BUCKET_HOST = BUCKET + '.' + SERVICE_HOST
JSON_HEADERS = [('Content-Type', 'application/json'), ('x-cos-request-id', 'req-local-1')]


class _FakeResponse(object):
    def __init__(self, status=200, headers=None, content=b''):
        self.status_code = status
        self.headers = CaseInsensitiveDict(headers or {})
        self.content = content

    def json(self):
        return json.loads(self.content.decode('utf-8'))


def _capture(client, response=None):
    """替换 send_request，记录请求参数并返回固定响应。"""
    calls = []

    def fake_send_request(**kwargs):
        calls.append(kwargs)
        if response is not None:
            return response
        return _FakeResponse(200, {'Content-Type': 'application/json', 'x-cos-request-id': 'req-1'}, b'{}')

    client.send_request = fake_send_request
    return calls


def _client(**conf_kwargs):
    conf_kwargs.setdefault('Region', REGION)
    conf = CosConfig(SecretId=SECRET_ID, SecretKey=SECRET_KEY, **conf_kwargs)
    return CosVectorsClient(conf, retry=2)


def _body(call):
    return json.loads(call['data'])


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(length) if length else b''
        headers = dict((k.lower(), v) for k, v in self.headers.items())
        self.server.records.append({'path': self.path, 'headers': headers, 'body': body})
        status, resp_headers, payload = self.server.next_response()
        self.send_response(status)
        for key, value in resp_headers:
            self.send_header(key, value)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        if payload:
            self.wfile.write(payload)

    def log_message(self, *args):
        pass


class _LoopbackServer(HTTPServer):
    def __init__(self):
        HTTPServer.__init__(self, ('127.0.0.1', 0), _Handler)
        self.records = []
        self.responses = []

    def next_response(self):
        if self.responses:
            return self.responses.pop(0)
        return 200, JSON_HEADERS, b''


def _verify_signature(record, secret_key):
    """按 proxy 验签取值方式重算: host 取实际 Host 头, path 取原始请求路径, 其余签名头取请求头。"""
    headers = record['headers']
    params = dict(kv.split('=', 1) for kv in headers['authorization'].split('&'))
    names = [name for name in params['q-header-list'].split(';') if name]
    if names != sorted(names):
        return False, names
    header_str = '&'.join('%s=%s' % (name, quote(to_bytes(headers.get(name, '')), '-_.~')) for name in names)
    format_str = 'post\n%s\n\n%s\n' % (record['path'].split('?')[0], header_str)
    sign_time = params['q-sign-time']
    string_to_sign = 'sha1\n%s\n%s\n' % (sign_time, hashlib.sha1(to_bytes(format_str)).hexdigest())
    sign_key = hmac.new(to_bytes(secret_key), to_bytes(sign_time), hashlib.sha1).hexdigest()
    expected = hmac.new(to_bytes(sign_key), to_bytes(string_to_sign), hashlib.sha1).hexdigest()
    return expected == params['q-signature'], names


class VectorsAddressTest(unittest.TestCase):
    """接入地址与 Host: Domain > EndpointCosVectors > Region, IP 只改变连接目标。"""

    def assert_target(self, call, url, host):
        self.assertEqual(url, call['url'])
        self.assertEqual(host, call['headers']['Host'])

    def test_region_only(self):
        client = _client()
        calls = _capture(client)
        client.get_vector_bucket(Bucket=BUCKET)
        client.get_namespace(Bucket=BUCKET, Namespace='products')
        self.assert_target(calls[0], 'https://' + SERVICE_HOST + '/GetVectorBucket', SERVICE_HOST)
        self.assert_target(calls[1], 'https://' + BUCKET_HOST + '/_native/products/_get_namespace', BUCKET_HOST)

    def test_endpoint_cosvectors(self):
        endpoint = 'vectors.test.example.com:8080'
        client = _client(EndpointCosVectors=endpoint, Scheme='http')
        calls = _capture(client)
        client.list_vector_buckets()
        client.list_namespaces(Bucket=BUCKET)
        self.assert_target(calls[0], 'http://' + endpoint + '/ListVectorBuckets', endpoint)
        self.assert_target(calls[1], 'http://' + BUCKET + '.' + endpoint + '/_native/_list_namespaces',
                           BUCKET + '.' + endpoint)

    def test_cos_endpoint_ignored(self):
        client = _client(Endpoint='cos.accelerate.myqcloud.com')
        calls = _capture(client)
        client.get_vector_bucket(Bucket=BUCKET)
        client.get_namespace(Bucket=BUCKET, Namespace='products')
        self.assertEqual(SERVICE_HOST, calls[0]['headers']['Host'])
        self.assertEqual(BUCKET_HOST, calls[1]['headers']['Host'])

    def test_domain_has_highest_priority(self):
        client = _client(Domain=BUCKET_HOST, EndpointCosVectors='vectors.other.example.com')
        calls = _capture(client)
        client.get_vector_bucket(Bucket=BUCKET)
        client.get_namespace(Bucket=BUCKET, Namespace='products')
        self.assert_target(calls[0], 'https://' + BUCKET_HOST + '/GetVectorBucket', BUCKET_HOST)
        self.assert_target(calls[1], 'https://' + BUCKET_HOST + '/_native/products/_get_namespace', BUCKET_HOST)

    def test_service_domain_rejected_for_native(self):
        client = _client(Domain=SERVICE_HOST)
        calls = _capture(client)
        client.get_vector_bucket(Bucket=BUCKET)
        self.assertEqual(SERVICE_HOST, calls[0]['headers']['Host'])
        with self.assertRaises(CosClientError):
            client.get_namespace(Bucket=BUCKET, Namespace='products')
        self.assertEqual(1, len(calls))

    def test_domain_bucket_mismatch(self):
        client = _client(Domain='otherbucket-1250000000.vectors.ap-guangzhou.coslake.com:8080')
        calls = _capture(client)
        with self.assertRaises(CosClientError):
            client.upsert_documents(Bucket=BUCKET, Namespace='products', Rows=[{'id': '1'}])
        client.upsert_documents(Bucket='otherbucket-1250000000', Namespace='products', Rows=[{'id': '1'}])
        self.assertEqual(1, len(calls))

    def test_appid_appended_to_bucket(self):
        client = _client(Appid='1250000000')
        calls = _capture(client)
        client.get_namespace(Bucket='examplebucket', Namespace='products')
        self.assertEqual(BUCKET_HOST, calls[0]['headers']['Host'])

    def test_ip_with_port(self):
        client = _client(IP='10.0.0.1', Port=8080, Scheme='http')
        calls = _capture(client)
        client.get_vector_bucket(Bucket=BUCKET)
        client.get_namespace(Bucket=BUCKET, Namespace='products')
        self.assert_target(calls[0], 'http://10.0.0.1:8080/GetVectorBucket', SERVICE_HOST)
        self.assert_target(calls[1], 'http://10.0.0.1:8080/_native/products/_get_namespace', BUCKET_HOST)

    def test_ip_without_port_uses_default_port(self):
        client = _client(IP='10.0.0.1', Scheme='http')
        calls = _capture(client)
        client.get_vector_bucket(Bucket=BUCKET)
        self.assert_target(calls[0], 'http://10.0.0.1/GetVectorBucket', SERVICE_HOST)

    def test_no_domain_source(self):
        client = _client(Region=None, Endpoint='cos.example.com', IP='10.0.0.1', Port=8080)
        calls = _capture(client)
        with self.assertRaises(CosClientError):
            client.get_vector_bucket(Bucket=BUCKET)
        with self.assertRaises(CosClientError):
            client.get_namespace(Bucket=BUCKET, Namespace='products')
        self.assertEqual(0, len(calls))

    def test_invalid_bucket(self):
        client = _client()
        calls = _capture(client)
        for bucket in ('evil.com#', 'a@b', '', None, 123):
            with self.assertRaises(CosClientError):
                client.get_namespace(Bucket=bucket, Namespace='products')
            with self.assertRaises(CosClientError):
                client.list_namespaces(Bucket=bucket)
        self.assertEqual(0, len(calls))

    def test_invalid_namespace(self):
        client = _client()
        calls = _capture(client)
        for namespace in ('a/b', '/', '.', '..', '', None, 123):
            with self.assertRaises(CosClientError):
                client.get_namespace(Bucket=BUCKET, Namespace=namespace)
        self.assertEqual(0, len(calls))

    def test_namespace_encoded_as_single_segment(self):
        client = _client()
        calls = _capture(client)
        client.get_namespace(Bucket=BUCKET, Namespace='a?b#c d')
        self.assertTrue(calls[0]['url'].endswith('/_native/a%3Fb%23c%20d/_get_namespace'))
        self.assertEqual(u'/_native/a%3Fb%23c%20d/_get_namespace', calls[0]['auth']._path)

    def test_cos_vectors_uri_compatible(self):
        conf = CosConfig(Region=REGION, SecretId=SECRET_ID, SecretKey=SECRET_KEY)
        self.assertEqual('https://' + SERVICE_HOST + '/GetVectorBucket', conf.cos_vectors_uri(path='/GetVectorBucket'))
        self.assertEqual('https://custom.example.com/GetVectorBucket',
                         conf.cos_vectors_uri(domain='custom.example.com', path='GetVectorBucket'))
        with self.assertRaises(CosClientError):
            conf.cos_vectors_uri(path='')


class VectorsRequestBodyTest(unittest.TestCase):
    """请求体字段映射、序列化与返回值。"""

    def setUp(self):
        self.client = _client()
        self.calls = _capture(self.client)

    def test_create_namespace(self):
        schema = {'primary_key': 'id', 'fields': {'id': {'type': 'string'}}}
        resp = self.client.create_namespace(Bucket=BUCKET, Namespace='products', Schema=schema,
                                            Metadata={'owner': 'team'})
        self.assertIsInstance(resp, dict)
        self.assertTrue(self.calls[0]['url'].endswith('/_native/products/_create_namespace'))
        self.assertEqual({'schema': schema, 'metadata': {'owner': 'team'}}, _body(self.calls[0]))
        self.client.create_namespace(Bucket=BUCKET, Namespace='products', Schema=schema)
        self.assertEqual({'schema': schema}, _body(self.calls[1]))

    def test_no_parameter_actions_send_empty_object(self):
        self.client.get_namespace(Bucket=BUCKET, Namespace='products')
        resp = self.client.delete_namespace(Bucket=BUCKET, Namespace='products')
        self.client.list_namespaces(Bucket=BUCKET)
        self.client.list_documents(Bucket=BUCKET, Namespace='products')
        self.assertIsInstance(resp, dict)
        for call in self.calls:
            self.assertEqual('{}', call['data'])
            self.assertEqual('application/json', call['headers']['Content-Type'])
        self.assertTrue(self.calls[1]['url'].endswith('/_native/products/_delete_namespace'))

    def test_list_namespaces(self):
        resp, data = self.client.list_namespaces(Bucket=BUCKET, MaxResults=10, NextToken='t', Prefix='prod')
        self.assertTrue(self.calls[0]['url'].endswith('/_native/_list_namespaces'))
        self.assertEqual({'maxResults': 10, 'nextToken': 't', 'prefix': 'prod'}, _body(self.calls[0]))
        self.assertEqual({}, data)

    def test_modify_namespace(self):
        self.client.modify_namespace(Bucket=BUCKET, Namespace='products', AddColumns=[{'name': 'c', 'type': 'string'}])
        self.client.modify_namespace(Bucket=BUCKET, Namespace='products', DropColumns=['c'])
        self.assertTrue(self.calls[0]['url'].endswith('/_native/products/_modify_namespace'))
        self.assertEqual({'addColumns': [{'name': 'c', 'type': 'string'}]}, _body(self.calls[0]))
        self.assertEqual({'dropColumns': ['c']}, _body(self.calls[1]))

    def test_upsert_documents_retry_flag(self):
        rows = [{'id': '1', 'embedding': [0.1, 0.2]}]
        self.client.upsert_documents(Bucket=BUCKET, Namespace='products', Rows=rows)
        self.client.upsert_documents(Bucket=BUCKET, Namespace='products', Columns={'id': ['1']}, PrimaryKeySpecified=True)
        self.assertTrue(self.calls[0]['url'].endswith('/_native/products/_upsert'))
        self.assertEqual({'rows': rows}, _body(self.calls[0]))
        self.assertFalse(self.calls[0]['_retry_ambiguous'])
        self.assertEqual({'columns': {'id': ['1']}}, _body(self.calls[1]))
        self.assertTrue(self.calls[1]['_retry_ambiguous'])

    def test_patch_and_delete_documents(self):
        self.client.patch_documents(Bucket=BUCKET, Namespace='products', Rows=[{'id': '1', 'price': None}])
        self.client.delete_documents(Bucket=BUCKET, Namespace='products', Ids=['1', '2'])
        self.assertTrue(self.calls[0]['url'].endswith('/_native/products/_patch'))
        self.assertEqual({'rows': [{'id': '1', 'price': None}]}, _body(self.calls[0]))
        self.assertTrue(self.calls[0]['_retry_ambiguous'])
        self.assertTrue(self.calls[1]['url'].endswith('/_native/products/_delete'))
        self.assertEqual({'ids': ['1', '2']}, _body(self.calls[1]))
        self.assertTrue(self.calls[1]['_retry_ambiguous'])

    def test_query_documents(self):
        queries = [['title', 'BM25', 'db'], ['embedding', 'Ann', {'vector': [0.1, 0.2], 'topk': 5}]]
        self.client.query_documents(Bucket=BUCKET, Namespace='products', Queries=queries, Filter=['price', 'Lt', 100],
                                    Fusion={'kind': 'rrf'}, Limit=10, Offset=0, Projection={'includes': ['title']})
        self.client.query_documents(Bucket=BUCKET, Namespace='products', Query=['title', 'BM25', 'db'],
                                    Sort=[['price', 'asc']])
        self.assertTrue(self.calls[0]['url'].endswith('/_native/products/_query'))
        self.assertEqual({'queries': queries, 'filter': ['price', 'Lt', 100], 'fusion': {'kind': 'rrf'},
                          'limit': 10, 'offset': 0, 'projection': {'includes': ['title']}}, _body(self.calls[0]))
        self.assertEqual({'query': ['title', 'BM25', 'db'], 'sort': [['price', 'asc']]}, _body(self.calls[1]))

    def test_list_documents(self):
        self.client.list_documents(Bucket=BUCKET, Namespace='products', Filter=['s', 'Eq', 'x'], MaxResults=100,
                                   NextToken='t', Projection={'excludes': ['embedding']}, SegmentCount=4, SegmentIndex=0)
        self.assertTrue(self.calls[0]['url'].endswith('/_native/products/_list'))
        self.assertEqual({'filter': ['s', 'Eq', 'x'], 'maxResults': 100, 'nextToken': 't',
                          'projection': {'excludes': ['embedding']}, 'segmentCount': 4, 'segmentIndex': 0},
                         _body(self.calls[0]))

    def test_compact_separators(self):
        self.client.upsert_documents(Bucket=BUCKET, Namespace='products', Rows=[{'id': '1', 'v': [1, 2]}])
        self.client.put_vectors(Bucket=BUCKET, Index='idx', Vectors=[{'key': 'k', 'data': {'float32': [1, 2]}}])
        for call in self.calls:
            self.assertNotIn(', ', call['data'])
            self.assertNotIn(': ', call['data'])

    def test_invalid_json_raises_client_error(self):
        with self.assertRaises(CosClientError):
            self.client.upsert_documents(Bucket=BUCKET, Namespace='products', Rows=[{'id': '1', 'v': [float('nan')]}])
        with self.assertRaises(CosClientError):
            self.client.query_documents(Bucket=BUCKET, Namespace='products', Query=['v', 'Ann', {'vector': [float('inf')]}])
        with self.assertRaises(CosClientError):
            self.client.put_vectors(Bucket=BUCKET, Index='idx', Vectors=[{'key': 'k', 'data': {'float32': [float('nan')]}}])
        with self.assertRaises(CosClientError):
            self.client.put_vectors(Bucket=BUCKET, Index='idx', Vectors=[{'key': 'k', 'metadata': {'o': object()}}])
        with self.assertRaises(CosClientError):
            self.client.put_vector_bucket_policy(Bucket=BUCKET, Policy={'v': set([1])})
        self.assertEqual(0, len(self.calls))

    def test_bucket_mode_parameter(self):
        """create_vector_bucket 默认不发送 mode；显式传 Mode 时才发送。"""
        self.client.create_vector_bucket(Bucket=BUCKET)
        self.client.create_vector_bucket(Bucket=BUCKET, Mode='ENHANCED', SseType='AES256')
        self.client.create_vector_bucket(Bucket=BUCKET, Mode=None)
        self.client.list_vector_buckets()
        self.client.list_vector_buckets(Mode='ENHANCED')
        self.assertTrue(self.calls[0]['url'].endswith('/CreateVectorBucket'))
        self.assertEqual({'vectorBucketName': BUCKET}, _body(self.calls[0]))
        self.assertEqual({'vectorBucketName': BUCKET, 'mode': 'ENHANCED',
                          'encryptionConfiguration': {'sseType': 'AES256'}}, _body(self.calls[1]))
        self.assertEqual({'vectorBucketName': BUCKET}, _body(self.calls[2]))
        self.assertTrue(self.calls[3]['url'].endswith('/ListVectorBuckets'))
        self.assertEqual({}, _body(self.calls[3]))
        self.assertEqual({'mode': 'ENHANCED'}, _body(self.calls[4]))

    def test_existing_actions_unchanged(self):
        self.client.create_index(Bucket=BUCKET, Index='idx', DataType='float32', Dimension=3, DistanceMetric='cosine',
                                 NonFilterableMetadataKeys=['k'])
        self.client.list_vectors(Bucket=BUCKET, Index='idx', MaxResults=10, SegmentCount=2, SegmentIndex=1,
                                 Filter={'k': {'$eq': 'v'}})
        self.client.put_vector_bucket_policy(Bucket=BUCKET, Policy={'version': '2.0', 'statement': []})
        self.client.list_indexes(Bucket=BUCKET)
        self.assertTrue(self.calls[0]['url'].endswith('/CreateIndex'))
        self.assertEqual({'dataType': 'float32', 'dimension': 3, 'distanceMetric': 'cosine',
                          'metadataConfiguration': {'nonFilterableMetadataKeys': ['k']},
                          'indexName': 'idx', 'vectorBucketName': BUCKET}, _body(self.calls[0]))
        self.assertEqual({'indexName': 'idx', 'vectorBucketName': BUCKET, 'maxResults': 10, 'segmentCount': 2,
                          'segmentIndex': 1, 'filter': {'k': {'$eq': 'v'}}}, _body(self.calls[1]))
        self.assertEqual('{"version":"2.0","statement":[]}', _body(self.calls[2])['policy'])
        self.assertEqual({'vectorBucketName': BUCKET}, _body(self.calls[3]))
        for call in self.calls:
            self.assertTrue(call['_retry_ambiguous'])
            self.assertEqual(call['url'].split('/')[-1], call['auth']._path.lstrip('/'))

    def test_existing_return_types(self):
        self.assertIsInstance(self.client.delete_vector_bucket(Bucket=BUCKET), dict)
        self.assertIsInstance(self.client.delete_index(Bucket=BUCKET, Index='idx'), dict)
        self.assertIsInstance(self.client.delete_vectors(Bucket=BUCKET, Index='idx', Keys=['k']), dict)
        self.assertIsInstance(self.client.delete_vector_bucket_policy(Bucket=BUCKET), dict)
        self.assertIsInstance(self.client.put_vectors(Bucket=BUCKET, Index='idx', Vectors=[]), CaseInsensitiveDict)
        resp, data = self.client.get_vector_bucket(Bucket=BUCKET)
        self.assertIsInstance(resp, dict)
        self.assertEqual({}, data)


class VectorsResponseTest(unittest.TestCase):

    def test_empty_json_body(self):
        client = _client()
        _capture(client, _FakeResponse(200, {'Content-Type': 'application/json'}, b''))
        resp, data = client.get_namespace(Bucket=BUCKET, Namespace='products')
        self.assertEqual(b'', data)
        self.assertIsInstance(client.create_namespace(Bucket=BUCKET, Namespace='products', Schema={}), dict)

    def test_json_body(self):
        client = _client()
        _capture(client, _FakeResponse(200, {'Content-Type': 'application/json; charset=utf-8'},
                                       b'{"result":{"rowsUpserted":2}}'))
        resp, data = client.upsert_documents(Bucket=BUCKET, Namespace='products', Rows=[])
        self.assertEqual({'result': {'rowsUpserted': 2}}, data)

    def test_trace_id_header_passthrough(self):
        """响应头中的 X-Cos-Trace-Id 原样透传。"""
        client = _client()
        _capture(client, _FakeResponse(200, {'Content-Type': 'application/json',
                                             'X-Cos-Trace-Id': 'trace-1', 'x-cos-request-id': 'req-1'}, b'{}'))
        resp, _ = client.get_namespace(Bucket=BUCKET, Namespace='products')
        self.assertEqual('trace-1', resp['X-Cos-Trace-Id'])
        self.assertEqual('req-1', resp['x-cos-request-id'])

    def test_non_json_body(self):
        client = _client()
        _capture(client, _FakeResponse(200, {'Content-Type': 'text/plain'}, b'raw'))
        resp, data = client.list_documents(Bucket=BUCKET, Namespace='products')
        self.assertEqual(b'raw', data)


class VectorsLoopbackTest(unittest.TestCase):
    """IP 直连本地服务, 校验实际 Host、路径与签名。"""

    @classmethod
    def setUpClass(cls):
        cls.server = _LoopbackServer()
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.daemon = True
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        del self.server.records[:]
        del self.server.responses[:]
        self._sleep = time.sleep
        time.sleep = lambda seconds: None

    def tearDown(self):
        time.sleep = self._sleep

    def client(self, **conf_kwargs):
        return _client(IP='127.0.0.1', Port=self.port, Scheme='http', **conf_kwargs)

    def assert_signed(self, record, host, path):
        self.assertEqual(host, record['headers']['host'])
        self.assertEqual(path, record['path'])
        valid, names = _verify_signature(record, SECRET_KEY)
        self.assertTrue(valid)
        self.assertIn('host', names)
        return names

    def test_native_region_only(self):
        self.client().get_namespace(Bucket=BUCKET, Namespace='products')
        self.assert_signed(self.server.records[0], BUCKET_HOST, '/_native/products/_get_namespace')

    def test_native_endpoint_with_token(self):
        endpoint = 'vectors.test.example.com:8080'
        self.client(EndpointCosVectors=endpoint, Token='tmp-token').list_namespaces(Bucket=BUCKET, MaxResults=1)
        record = self.server.records[0]
        names = self.assert_signed(record, BUCKET + '.' + endpoint, '/_native/_list_namespaces')
        self.assertIn('x-cos-security-token', names)
        self.assertEqual('tmp-token', record['headers']['x-cos-security-token'])
        self.assertEqual({'maxResults': 1}, json.loads(record['body'].decode('utf-8')))

    def test_native_bucket_domain(self):
        self.client(Domain=BUCKET_HOST).delete_namespace(Bucket=BUCKET, Namespace='products')
        self.assert_signed(self.server.records[0], BUCKET_HOST, '/_native/products/_delete_namespace')

    def test_existing_action_without_domain(self):
        self.server.responses.append((200, JSON_HEADERS, b'{"vectorBucket":{}}'))
        resp, data = self.client().get_vector_bucket(Bucket=BUCKET)
        self.assertEqual({'vectorBucket': {}}, data)
        self.assert_signed(self.server.records[0], SERVICE_HOST, '/GetVectorBucket')

    def test_empty_success_body(self):
        resp = self.client().create_namespace(Bucket=BUCKET, Namespace='products', Schema={'fields': {}})
        self.assertEqual('req-local-1', resp.get('x-cos-request-id'))

    def test_upsert_not_retried_by_default(self):
        self.server.responses.extend([(503, JSON_HEADERS, b'{}')] * 3)
        with self.assertRaises(CosServiceError):
            self.client().upsert_documents(Bucket=BUCKET, Namespace='products', Rows=[{'v': 1}])
        self.assertEqual(1, len(self.server.records))

    def test_upsert_retried_when_primary_key_specified(self):
        self.server.responses.extend([(503, JSON_HEADERS, b'{}')] * 3)
        with self.assertRaises(CosServiceError):
            self.client().upsert_documents(Bucket=BUCKET, Namespace='products', Rows=[{'id': '1'}],
                                           PrimaryKeySpecified=True)
        self.assertEqual(3, len(self.server.records))

    def test_other_actions_retried(self):
        self.server.responses.extend([(503, JSON_HEADERS, b'{}'), (200, JSON_HEADERS, b'{"result":{}}')])
        resp, data = self.client().patch_documents(Bucket=BUCKET, Namespace='products', Rows=[{'id': '1', 'v': 1}])
        self.assertEqual({'result': {}}, data)
        self.assertEqual(2, len(self.server.records))

    def test_native_error_response(self):
        payload = b'{"errorCode":"ValidationException","message":"bad schema"}'
        self.server.responses.append((400, JSON_HEADERS, payload))
        with self.assertRaises(CosServiceError) as ctx:
            self.client().create_namespace(Bucket=BUCKET, Namespace='products', Schema={})
        error = ctx.exception
        self.assertEqual(400, error.get_status_code())
        self.assertEqual('bad schema', error.get_error_msg())
        self.assertEqual('req-local-1', error.get_request_id())
        self.assertEqual(1, len(self.server.records))


if __name__ == '__main__':
    unittest.main()
