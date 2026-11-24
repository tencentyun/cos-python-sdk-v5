# -*- coding=utf-8
import sys
import os
from pprint import pprint

from qcloud_cos import CosConfig
from qcloud_cos import CosVectorsClient
import logging

# 正常情况日志级别使用 INFO，需要定位时可以修改为 DEBUG，此时 SDK 会打印和服务端的通信信息
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# 1. 设置用户属性, 包括 secret_id, secret_key, region 等。Appid 已在 CosConfig 中移除，请在参数 Bucket 中带上 Appid。Bucket 由 BucketName-Appid 组成
secret_id = os.getenv("COS_VECTORS_SECRET_ID")     # 用户的 SecretId，建议使用子账号密钥，授权遵循最小权限指引，降低使用风险。子账号密钥获取可参见 https://cloud.tencent.com/document/product/598/37140
secret_key = os.getenv("COS_VECTORS_SECRET_KEY")   # 用户的 SecretKey，建议使用子账号密钥，授权遵循最小权限指引，降低使用风险。子账号密钥获取可参见 https://cloud.tencent.com/document/product/598/37140
region = 'ap-guangzhou'      # 替换为用户的 region，已创建桶归属的 region 可以在控制台查看，https://console.cloud.tencent.com/cos/bucket
                           # COS 支持的所有 region 列表参见 https://cloud.tencent.com/document/product/436/6224
token = None               # 如果使用永久密钥不需要填入 token，如果使用临时密钥需要填入，临时密钥生成和使用指引参见 https://cloud.tencent.com/document/product/436/14048
scheme = 'http'           # 指定使用 http/https 协议来访问 COS，默认为 https，可不填

# 2. Native API(namespace/文档接口)通过 Host 中的第一段定位存储桶, 要求桶为 ENHANCED 模式:
#    - 不配置 EndpointCosVectors 时按 Region 推导: <bucket>.vectors.<region>.coslake.com
config = CosConfig(
    Region=region,
    SecretId=secret_id,
    SecretKey=secret_key,
    Scheme=scheme,
    EndpointCosVectors="vectors.ap-guangzhou.coslake.com",
    Token=token
)
client = CosVectorsClient(config)

bucket = 'example-bucket-1250000000'
namespace = 'products'

print("[获取namespace]")
resp, data = client.get_namespace(
    Bucket=bucket,
    Namespace=namespace
)
# print(resp)
pprint(data)

print("[写入文档: 行式]")
# 每行都带主键, 设置 PrimaryKeySpecified=True 后失败时可以自动重试;
# 若由系统生成主键(行内没有主键)且未指定主键, 请保持默认 False, 避免重试写入重复数据
resp = client.upsert_documents(
    Bucket=bucket,
    Namespace=namespace,
    Rows=[
        {'id': 'p1', 'title': 'vector database', 'price': 12.5, 'tag': 'db', 'embedding': [1.0, 0.0, 0.0]},
        {'id': 'p2', 'title': 'object storage', 'price': 9.9, 'tag': 'storage', 'embedding': [0.0, 1.0, 0.0]},
        {'id': 'p3', 'title': 'vector search engine', 'price': 99.0, 'tag': 'db', 'embedding': [0.9, 0.1, 0.0]}
    ],
    PrimaryKeySpecified=True
)
print(resp)

print("[写入文档: 列式]")
resp = client.upsert_documents(
    Bucket=bucket,
    Namespace=namespace,
    Columns={
        'id': ['p4'],
        'title': ['hybrid search'],
        'price': [49.0],
        'tag': ['db'],
        'embedding': [[0.8, 0.2, 0.0]]
    },
    PrimaryKeySpecified=True
)
print(resp)

print("[部分更新文档]")
resp = client.patch_documents(
    Bucket=bucket,
    Namespace=namespace,
    Rows=[{'id': 'p2', 'price': 19.9}]
)
print(resp)

print("[向量检索]")
resp, data = client.query_documents(
    Bucket=bucket,
    Namespace=namespace,
    Query=['embedding', 'Ann', {'vector': [1.0, 0.0, 0.0], 'topk': 2}],
    Projection={'includes': ['title', 'price']}
)
# print(resp)
pprint(data)

print("[全文检索 + 过滤]")
resp, data = client.query_documents(
    Bucket=bucket,
    Namespace=namespace,
    Query=['title', 'BM25', 'vector'],
    Filter=['tag', 'Eq', 'db'],
    Limit=10
)
# print(resp)
pprint(data)

print("[多路召回, RRF 融合]")
resp, data = client.query_documents(
    Bucket=bucket,
    Namespace=namespace,
    Queries=[
        ['title', 'BM25', 'vector'],
        ['embedding', 'Ann', {'vector': [1.0, 0.0, 0.0], 'topk': 3}]
    ],
    Fusion={'kind': 'rrf'},
    Limit=3
)
# print(resp)
pprint(data)

print("[列出文档]")
resp, data = client.list_documents(
    Bucket=bucket,
    Namespace=namespace,
    Filter=['tag', 'Eq', 'db'],
    MaxResults=10
)
# print(resp)
pprint(data)

print("[删除文档]")
resp = client.delete_documents(
    Bucket=bucket,
    Namespace=namespace,
    Ids=['p1', 'p2', 'p3', 'p4']
)
print(resp)
