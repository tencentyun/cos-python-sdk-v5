# -*- coding=utf-8
"""COS Vectors e2e 用例, 包含两组流程.

- CLASSIC 组: CLASSIC 桶 + index + vectors, 入口 run_classic_e2e
- ENHANCED 组: ENHANCED 桶 + namespace + documents, 入口 run_enhanced_e2e

两组共用同一套接入方式和同一个 client, 区别只在使用的桶:
- 只配 Region 即可, Host 由 SDK 推导: COS Vectors 协议接口用 vectors.<region>.coslake.com,
  Native 接口用 <bucket>.vectors.<region>.coslake.com, 因此不需要手工指定 Domain
- 用 IP 访问时只需配 IP/Port, Host 仍由 Region 或 EndpointCosVectors 推导(proxy 靠 Host 解析桶)
- EndpointCosVectors 是可选覆盖, 且 Host 中的 region 段必须与 proxy 所在地域一致,
  否则 proxy 返回 400 unexpected region in host

本文件不定义 test_* 函数或 TestCase 类, 由 ut/test.py 的薄壳函数调用,
避免 nose/pytest 与薄壳重复收集同一组用例.
"""
import os
import random
import time

from qcloud_cos import CosConfig
from qcloud_cos import CosVectorsClient
from qcloud_cos import CosServiceError

# 3.0 目前只在测试环境可用, 凭证与地域独立配置, 不复用 COS 主账号那一套
SECRET_ID = os.environ["COS_VECTORS_SECRET_ID"]
SECRET_KEY = os.environ["COS_VECTORS_SECRET_KEY"]
REGION = os.environ['COS_VECTORS_REGION']
APPID = os.environ['COS_VECTORS_APPID']

# 可选: 服务域名(不含 bucket), 不配置时按 Region 推导 vectors.<region>.coslake.com
COS_VECTORS_ENDPOINT = os.environ.get("COS_VECTORS_ENDPOINT") or None
# 可选: IP 直连, 仅用于本地调试; 只改变连接目标, Host 仍由 Endpoint/Region 推导
COS_VECTORS_IP = os.environ.get("COS_VECTORS_IP") or None
COS_VECTORS_PORT = int(os.environ["COS_VECTORS_PORT"]) if os.environ.get("COS_VECTORS_PORT") else None

BUCKET_PREFIX = "cos-python-sdk-test-vec"
INDEX_NAME = 'idx-float32-dim3'

# 轮询等待的默认超时与间隔, 两组共用
WAIT_TIMEOUT = 60
WAIT_INTERVAL = 2

client = CosVectorsClient(CosConfig(
    Scheme='http',
    Appid=APPID,
    Region=REGION,
    SecretId=SECRET_ID,
    SecretKey=SECRET_KEY,
    IP=COS_VECTORS_IP,
    Port=COS_VECTORS_PORT,
    EndpointCosVectors=COS_VECTORS_ENDPOINT,
), retry=3)


def _brief(value):
    """截断过长观测值, 便于放入断言报错信息"""
    text = repr(value)
    return text if len(text) <= 300 else text[:300] + '...'


def _wait_until(fetch, check, describe, timeout=WAIT_TIMEOUT, interval=WAIT_INTERVAL):
    """轮询至 check(fetch()) 为真, 返回最后一次结果.

    超时抛 AssertionError, 报错信息包含 describe 与最后一次观测值,
    便于区分"慢"与"错". 固定 sleep 会掩盖这类信息, 因此统一改为此函数.
    """
    deadline = time.time() + timeout
    result = fetch()
    while not check(result):
        if time.time() >= deadline:
            raise AssertionError('{describe} 等待超时({timeout}s), 最后观测: {value}'.format(
                describe=describe, timeout=timeout, value=_brief(result)))
        time.sleep(interval)
        result = fetch()
    return result


# ===================== CLASSIC 组: 桶 + index + vectors =====================

def create_vector_bucket(Bucket):
    """创建向量桶"""
    resp, data = client.create_vector_bucket(
        Bucket=Bucket,
        SseType='AES256'
    )
    return resp, data


def delete_vector_bucket(Bucket):
    """删除向量桶"""
    resp = client.delete_vector_bucket(
        Bucket=Bucket
    )
    return resp


def list_vector_buckets():
    """列出向量桶"""
    resp, data = client.list_vector_buckets(
        MaxResults=100,
        Prefix=BUCKET_PREFIX
    )
    return resp, data


def get_vector_bucket(Bucket):
    """获取向量桶"""
    resp, data = client.get_vector_bucket(
        Bucket=Bucket
    )
    return resp, data


def _index_qcs(bucket):
    """index 级 QCS: qcs::cosvector:<region>:uid/<appid>:bucket/<bucket>/index/<index>"""
    return u"qcs::cosvector:{region}:uid/{appid}:bucket/{bucket}/index/{index}".format(
        region=REGION, appid=APPID, bucket=bucket, index=INDEX_NAME)


def _namespace_qcs(bucket, namespace):
    """namespace 级 QCS: qcs::cosvector:<region>:uid/<appid>:bucket/<bucket>/namespace/<ns>"""
    return u"qcs::cosvector:{region}:uid/{appid}:bucket/{bucket}/namespace/{namespace}".format(
        region=REGION, appid=APPID, bucket=bucket, namespace=namespace)


def _put_policy(bucket, resource, actions):
    """写入向量桶策略; 策略写接口按桶计配额, 429 时退避重试"""
    policy = {
        "Version": "2.0",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "qcs": [
                        "qcs::cam::anonymous:anonymous"
                    ]
                },
                "Action": actions,
                "Resource": [resource]
            }
        ]
    }
    for attempt in range(3):
        try:
            return client.put_vector_bucket_policy(Bucket=bucket, Policy=policy)
        except CosServiceError as e:
            if e.get_status_code() == 429 and attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            raise


def _policy_roundtrip(bucket, resource, segment, actions):
    """写入策略 -> 回读断言 QCS 段 -> 删除策略.

    CAM 只校验 QCS 的前缀结构, 写错 /index/ 或 /namespace/ 段同样能存进去,
    因此必须回读策略文本断言段名, 否则用例会假通过.
    """
    _put_policy(bucket, resource, actions)

    def fetch():
        return client.get_vector_bucket_policy(Bucket=bucket)[1]

    data = _wait_until(fetch, lambda result: segment in (result.get('policy') or ''),
                       '策略回读包含 {segment} 段'.format(segment=segment))
    policy = data['policy']
    assert segment in policy, policy
    assert resource in policy, policy
    assert bucket in policy, policy
    unexpected = '/namespace/' if segment == '/index/' else '/index/'
    assert unexpected not in policy, policy

    client.delete_vector_bucket_policy(Bucket=bucket)


def create_index(Bucket):
    """创建索引"""
    resp, data = client.create_index(
        Bucket=Bucket,
        Index=INDEX_NAME,
        DataType="float32",
        Dimension=3,
        DistanceMetric='euclidean',
        NonFilterableMetadataKeys=['nfkey1', 'nfkey2']
    )
    return resp, data


def delete_index(Bucket):
    """删除索引"""
    resp = client.delete_index(
        Bucket=Bucket,
        Index=INDEX_NAME
    )
    return resp


def list_indexes(Bucket):
    """列出索引"""
    resp, data = client.list_indexes(
        MaxResults=100,
        Bucket=Bucket
    )
    return resp, data


def get_index(Bucket):
    """获取索引"""
    resp, data = client.get_index(
        Bucket=Bucket,
        Index=INDEX_NAME
    )
    return resp, data


def put_vectors(Bucket):
    """插入向量"""
    resp = client.put_vectors(
        Bucket=Bucket,
        Index=INDEX_NAME,
        Vectors=[
            {
                'key': 'vector1',
                'data': {
                    'float32': [0.1, 0.2, 0.3],
                },
                'metadata': {
                    'key1': 'value1',
                    'key2': 'value2',
                    'nfkey1': 'nfvalue1'
                }
            },
            {
                'key': 'vector2',
                'data': {
                    'float32': [0.4, 0.5, 0.6]
                },
                'metadata': {
                    'key1': 'value11',
                    'key2': 'value22',
                    'nfkey2': 'nfvalue22'
                }
            },
            {
                'key': 'vector3',
                'data': {
                    'float32': [0.7, 0.8, 0.9]
                },
                'metadata': {
                    'key1': 'value111',
                    'key2': 'value222',
                    'nfkey1': 'nfvalue111',
                    'nfkey2': 'nfvalue222'
                }
            }
        ]
    )
    return resp


def get_vectors(Bucket, keys):
    """获取向量"""
    resp, data = client.get_vectors(
        Bucket=Bucket,
        Index=INDEX_NAME,
        Keys=keys,
        ReturnData=True,
        ReturnMetaData=True
    )
    return resp, data


def list_vectors(Bucket):
    """列出向量"""
    resp, data = client.list_vectors(
        Bucket=Bucket,
        Index=INDEX_NAME,
        MaxResults=100,
        ReturnData=True,
        ReturnMetaData=True
    )
    return resp, data


def delete_vectors(Bucket, keys):
    """删除向量"""
    resp = client.delete_vectors(
        Bucket=Bucket,
        Index=INDEX_NAME,
        Keys=keys
    )
    return resp


def query_vectors(Bucket, query_vector, filter=None):
    """查询向量"""
    resp, data = client.query_vectors(
        Bucket=Bucket,
        Index=INDEX_NAME,
        QueryVector={"float32": query_vector},
        TopK=1,
        Filter=filter,
        ReturnDistance=True,
        ReturnMetaData=True
    )
    return resp, data


def _vector_keys(data):
    """取出向量列表的 key, 供轮询判定使用"""
    if not isinstance(data, dict):
        return []
    return [vector.get('key') for vector in data.get('vectors') or []]


def _classic_cleanup(bucket):
    """尽力清理策略、索引与桶, 不抛异常, 避免掩盖原始断言失败"""
    try:
        client.delete_vector_bucket_policy(Bucket=bucket)
    except (CosServiceError, AssertionError):
        pass
    try:
        delete_index(bucket)
    except (CosServiceError, AssertionError):
        pass
    try:
        delete_vector_bucket(bucket)
    except (CosServiceError, AssertionError):
        pass


def run_classic_e2e():
    """CLASSIC 桶 + index + vectors 全流程"""
    random_suffix = ''.join(random.choice('0123456789abcdefghijklmnopqrstuvwxyz') for _ in range(8))
    vector_bucket_name = u"{prefix}-{suffix}-{appid}".format(
        prefix=BUCKET_PREFIX, suffix=random_suffix, appid=APPID)

    # 创建测试向量桶
    resp, data = create_vector_bucket(vector_bucket_name)
    assert isinstance(data, dict)
    assert 'vectorBucketQcs' in data

    try:
        # 列出现有向量桶
        resp, data = list_vector_buckets()
        assert isinstance(data, dict)
        assert 'vectorBuckets' in data
        assert isinstance(data['vectorBuckets'], list)

        # 获取向量桶
        resp, data = get_vector_bucket(vector_bucket_name)
        assert isinstance(data, dict)
        assert 'vectorBucket' in data
        assert isinstance(data['vectorBucket'], dict)
        assert data['vectorBucket']['vectorBucketName'] == vector_bucket_name

        # 策略: CLASSIC 桶的资源粒度是 index 级, QCS 段为 /index/<index>
        _policy_roundtrip(vector_bucket_name, _index_qcs(vector_bucket_name), '/index/',
                          ['name/cos:GetVectorIndex', 'name/cos:ListVectors'])

        # 创建索引
        resp, data = create_index(vector_bucket_name)
        assert isinstance(data, dict)
        assert 'indexQcs' in data

        # 列出索引
        resp, data = list_indexes(vector_bucket_name)
        assert isinstance(data, dict)
        assert 'indexes' in data
        assert isinstance(data['indexes'], list)
        assert len(data['indexes']) == 1

        # 获取索引
        resp, data = get_index(vector_bucket_name)
        assert isinstance(data, dict)
        assert 'index' in data
        assert isinstance(data['index'], dict)
        assert data['index']['indexName'] == INDEX_NAME
        assert data['index']['vectorBucketName'] == vector_bucket_name

        # 插入向量, 轮询到全部可见
        resp = put_vectors(vector_bucket_name)
        data = _wait_until(
            lambda: get_vectors(vector_bucket_name, ['vector1', 'vector2'])[1],
            lambda result: len(_vector_keys(result)) == 2,
            '写入后 get_vectors 可见 2 条')
        assert isinstance(data, dict)
        assert 'vectors' in data
        assert len(data['vectors']) == 2

        data = _wait_until(
            lambda: list_vectors(vector_bucket_name)[1],
            lambda result: len(_vector_keys(result)) == 3,
            '写入后 list_vectors 可见 3 条')
        assert isinstance(data, dict)
        assert 'vectors' in data
        assert len(data['vectors']) == 3

        # 查询向量
        resp, data = query_vectors(vector_bucket_name, [0.1, 0.2, 0.3])
        assert isinstance(data, dict)
        assert 'vectors' in data
        assert isinstance(data['vectors'], list)
        assert len(data['vectors']) == 1
        assert data['vectors'][0]['key'] == 'vector1'   # vector1距离最近

        # 删除向量再查询, 轮询到 vector2 成为最近的向量
        resp = delete_vectors(vector_bucket_name, ['vector1'])
        data = _wait_until(
            lambda: query_vectors(vector_bucket_name, [0.1, 0.2, 0.3])[1],
            lambda result: _vector_keys(result) == ['vector2'],
            '删除 vector1 后查询 top1 为 vector2')
        assert isinstance(data, dict)
        assert 'vectors' in data
        assert len(data['vectors']) == 1
        assert data['vectors'][0]['key'] == 'vector2'

        # 过滤查询: vector2被过滤掉
        resp, data = query_vectors(vector_bucket_name, [0.1, 0.2, 0.3], filter={'key1': {'$eq': 'value111'}})
        assert isinstance(data, dict)
        assert 'vectors' in data
        assert isinstance(data['vectors'], list)
        assert len(data['vectors']) == 1
        assert data['vectors'][0]['key'] == 'vector3'

        # 删除剩余向量, 轮询到列表为空
        resp = delete_vectors(vector_bucket_name, ['vector2', 'vector3'])
        data = _wait_until(
            lambda: list_vectors(vector_bucket_name)[1],
            lambda result: len(_vector_keys(result)) == 0,
            '删除全部向量后 list_vectors 为空')
        assert isinstance(data, dict)
        assert 'vectors' in data
        assert len(data['vectors']) == 0

        # 删除索引
        resp = delete_index(vector_bucket_name)
        resp, data = list_indexes(vector_bucket_name)
        assert isinstance(data, dict)
        assert 'indexes' in data
        assert isinstance(data['indexes'], list)
        assert len(data['indexes']) == 0

        # 再次尝试获取索引, 索引已不存在
        try:
            resp, data = get_index(vector_bucket_name)
        except CosServiceError as e:
            assert e.get_error_code() == "NotFoundException"

        # 删除向量桶
        try:
            time.sleep(1)
            resp = delete_vector_bucket(vector_bucket_name)
        except CosServiceError as e:
            assert e.get_error_code() == "ConflictException"
            print(e)
        resp, data = list_vector_buckets()
        assert isinstance(data, dict)
        assert 'vectorBuckets' in data
        assert isinstance(data['vectorBuckets'], list)
    finally:
        _classic_cleanup(vector_bucket_name)


# ===================== ENHANCED 组: 桶 + namespace + documents =====================

def _native_list_all_ids(bucket, namespace, **kwargs):
    """分页枚举namespace内全部文档主键"""
    ids = []
    next_token = None
    while True:
        resp, data = client.list_documents(
            Bucket=bucket, Namespace=namespace, MaxResults=2, NextToken=next_token, **kwargs)
        assert isinstance(data, dict)
        assert isinstance(data['documents'], list)
        assert len(data['documents']) <= 2
        ids.extend(doc['_id'] for doc in data['documents'])
        next_token = data.get('nextToken')
        if not next_token:
            return ids


def _native_hit_ids(data):
    assert isinstance(data, dict)
    assert isinstance(data['hits'], list)
    return [hit['_id'] for hit in data['hits']]


def _native_expect_status(status, func, **kwargs):
    try:
        func(**kwargs)
    except CosServiceError as e:
        assert e.get_status_code() == status, e
        assert e.get_error_msg()
        return e
    raise AssertionError('expect CosServiceError with status {status}'.format(status=status))


def _native_user_key_cases(bucket, namespace):
    """用户主键namespace: 生命周期、写入、检索与枚举"""
    schema = {
        'primary_key': 'id',
        'fields': {
            'id': {'type': 'string'},
            'title': {'type': 'text', 'full_text_search': {'enabled': True}},
            'price': {'type': 'float64'},
            'tag': {'type': 'string'},
            'embedding': {'type': 'vector', 'dimension': 3, 'data_type': 'float32', 'distance_metric': 'cosine'},
        }
    }
    resp = client.create_namespace(Bucket=bucket, Namespace=namespace, Schema=schema,
                                   Metadata={'owner': 'cos-python-sdk'})
    assert isinstance(resp, dict)
    _native_expect_status(409, client.create_namespace, Bucket=bucket, Namespace=namespace, Schema=schema)

    resp, data = client.get_namespace(Bucket=bucket, Namespace=namespace)
    assert data['namespace']['bucketName'] == bucket
    assert data['namespace']['namespaceName'] == namespace
    assert data['namespace']['schema']['primary_key'] == 'id'
    assert data['namespace']['metadata'] == {'owner': 'cos-python-sdk'}

    resp, data = client.list_namespaces(Bucket=bucket, Prefix=namespace)
    assert namespace in [item['namespaceName'] for item in data['namespaces']]

    resp, data = client.modify_namespace(Bucket=bucket, Namespace=namespace,
                                         AddColumns=[{'name': 'category', 'type': 'string'}])
    assert 'category' in data['namespace']['schema']['fields']
    resp, data = client.modify_namespace(Bucket=bucket, Namespace=namespace, DropColumns=['category'])
    assert 'category' not in data['namespace']['schema']['fields']

    # 行式与列式写入, 每行都携带主键, 允许重试
    resp = client.upsert_documents(
        Bucket=bucket, Namespace=namespace, PrimaryKeySpecified=True,
        Rows=[
            {'id': 'p1', 'title': 'vector database', 'price': 12.5, 'tag': 'db', 'embedding': [1.0, 0.0, 0.0]},
            {'id': 'p2', 'title': 'object storage', 'price': 9.9, 'tag': 'storage', 'embedding': [0.0, 1.0, 0.0]},
        ])
    assert isinstance(resp, dict)
    resp = client.upsert_documents(
        Bucket=bucket, Namespace=namespace, PrimaryKeySpecified=True,
        Columns={'id': ['p3'], 'title': ['vector search engine'], 'price': [99.0], 'tag': ['db'],
                 'embedding': [[0.9, 0.1, 0.0]]})
    assert isinstance(resp, dict)
    resp = client.patch_documents(Bucket=bucket, Namespace=namespace, Rows=[{'id': 'p2', 'price': 19.9}])
    assert isinstance(resp, dict)

    ids = _wait_until(lambda: _native_list_all_ids(bucket, namespace),
                      lambda result: sorted(result) == ['p1', 'p2', 'p3'],
                      '写入后列出文档为 p1/p2/p3')
    assert sorted(ids) == ['p1', 'p2', 'p3']

    def query(check, describe, **kwargs):
        # 写入后检索可见性可能有延迟, 轮询至check通过
        def fetch():
            return client.query_documents(Bucket=bucket, Namespace=namespace, **kwargs)[1]
        return _wait_until(fetch, check, describe)

    # 向量召回
    data = query(lambda d: _native_hit_ids(d)[:1] == ['p1'], '向量召回的 top1 为 p1',
                 Query=['embedding', 'Ann', {'vector': [1.0, 0.0, 0.0], 'topk': 2}], Limit=2)
    assert _native_hit_ids(data)[0] == 'p1'
    assert '_distance' in data['hits'][0]

    # BM25 召回 + 投影
    data = query(lambda d: set(_native_hit_ids(d)) == set(['p1', 'p3']), 'BM25 召回 p1/p3',
                 Query=['title', 'BM25', 'vector'], Projection={'includes': ['title']})
    assert set(_native_hit_ids(data)) == set(['p1', 'p3'])
    for hit in data['hits']:
        assert '_score' in hit
        assert set(hit.get('_source', {}).keys()) <= set(['title'])

    # 过滤: patch 后 p2 价格为 19.9
    data = query(lambda d: _native_hit_ids(d) == ['p2'], '过滤后仅命中 p2',
                 Query=['embedding', 'Ann', {'vector': [1.0, 0.0, 0.0], 'topk': 3}],
                 Filter=['And', [['tag', 'Eq', 'storage'], ['price', 'Gt', 15]]])
    assert _native_hit_ids(data) == ['p2']

    # 多路召回 RRF 融合
    queries = [['title', 'BM25', 'vector'], ['embedding', 'Ann', {'vector': [1.0, 0.0, 0.0], 'topk': 3}]]
    data = query(lambda d: 'p1' in _native_hit_ids(d), 'RRF 融合结果包含 p1',
                 Queries=queries, Fusion={'kind': 'rrf', 'rrf_k': 60}, Limit=3)
    assert 'p1' in _native_hit_ids(data)

    # 多路并行召回(无融合)
    resp, data = client.query_documents(Bucket=bucket, Namespace=namespace, Queries=queries)
    assert len(data['multiHits']) == 2

    # 过滤枚举与分段枚举
    resp, data = client.list_documents(Bucket=bucket, Namespace=namespace, Filter=['tag', 'Eq', 'db'],
                                       Projection={'includes': ['tag']})
    assert sorted(doc['_id'] for doc in data['documents']) == ['p1', 'p3']
    segment_ids = []
    for index in range(2):
        segment_ids.extend(_native_list_all_ids(bucket, namespace, SegmentCount=2, SegmentIndex=index))
    assert sorted(segment_ids) == ['p1', 'p2', 'p3']

    # 服务端参数校验错误
    _native_expect_status(400, client.query_documents, Bucket=bucket, Namespace=namespace,
                          Query=['embedding', 'Ann', {'vector': [1.0, 0.0], 'topk': 1}])

    # 按主键删除
    resp = client.delete_documents(Bucket=bucket, Namespace=namespace, Ids=['p1'])
    assert isinstance(resp, dict)
    ids = _wait_until(lambda: _native_list_all_ids(bucket, namespace),
                      lambda result: sorted(result) == ['p2', 'p3'],
                      '删除 p1 后列出文档为 p2/p3')
    assert sorted(ids) == ['p2', 'p3']


def _native_auto_key_cases(bucket, namespace):
    """系统自动主键namespace: 不携带_id的写入默认不重试"""
    schema = {
        'fields': {
            'title': {'type': 'text'},
            'embedding': {'type': 'vector', 'dimension': 3, 'distance_metric': 'l2'},
        }
    }
    client.create_namespace(Bucket=bucket, Namespace=namespace, Schema=schema)
    resp = client.upsert_documents(
        Bucket=bucket, Namespace=namespace, Rows=[{'title': 'auto key', 'embedding': [0.1, 0.2, 0.3]}])
    assert isinstance(resp, dict)
    resp = client.upsert_documents(
        Bucket=bucket, Namespace=namespace, PrimaryKeySpecified=True,
        Rows=[{'_id': 'auto-1', 'title': 'explicit key', 'embedding': [0.3, 0.2, 0.1]}])
    assert isinstance(resp, dict)

    ids = _wait_until(lambda: _native_list_all_ids(bucket, namespace),
                      lambda result: len(result) == 2,
                      '自动主键 namespace 写入后文档数为 2')
    assert len(ids) == 2
    assert 'auto-1' in ids
    assert all(ids)


def run_enhanced_e2e():
    """ENHANCED 桶 + namespace + documents 全流程, IP 直连"""
    random_suffix = ''.join(random.choice('0123456789abcdefghijklmnopqrstuvwxyz') for _ in range(8))
    bucket = u"cos-python-sdk-test-native-{suffix}-{appid}".format(suffix=random_suffix, appid=APPID)
    user_namespace = u"ns-user-{suffix}".format(suffix=random_suffix)
    auto_namespace = u"ns-auto-{suffix}".format(suffix=random_suffix)

    # 通过COS Vectors协议建桶, 同时验证IP直连时现有接口的Host
    # Native API(namespace/文档接口)只能在 ENHANCED 桶上使用
    resp, data = client.create_vector_bucket(Bucket=bucket, Mode='ENHANCED')
    assert 'vectorBucketQcs' in data
    try:
        resp, data = client.get_vector_bucket(Bucket=bucket)
        assert data['vectorBucket']['vectorBucketName'] == bucket
        assert data['vectorBucket']['mode'] == 'ENHANCED'

        _native_user_key_cases(bucket, user_namespace)
        _native_auto_key_cases(bucket, auto_namespace)

        # 策略: ENHANCED 桶的资源粒度是 namespace 级, QCS 段为 /namespace/<namespace>
        _policy_roundtrip(bucket, _namespace_qcs(bucket, user_namespace), '/namespace/',
                          ['name/cos:GetNamespace', 'name/cos:QueryDocuments'])

        resp, data = client.list_namespaces(Bucket=bucket, MaxResults=1)
        assert len(data['namespaces']) == 1
        assert 'nextToken' in data

        for namespace in (user_namespace, auto_namespace):
            resp = client.delete_namespace(Bucket=bucket, Namespace=namespace)
            assert isinstance(resp, dict)
            _native_expect_status(404, client.get_namespace, Bucket=bucket, Namespace=namespace)
    finally:
        try:
            client.delete_vector_bucket_policy(Bucket=bucket)
        except CosServiceError:
            pass
        for namespace in (user_namespace, auto_namespace):
            try:
                client.delete_namespace(Bucket=bucket, Namespace=namespace)
            except CosServiceError:
                pass
        time.sleep(1)
        try:
            client.delete_vector_bucket(Bucket=bucket)
        except CosServiceError:
            pass
