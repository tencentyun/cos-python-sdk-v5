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

print("[列出namespace]")
resp, data = client.list_namespaces(
    Bucket=bucket,
    MaxResults=10
)
# print(resp)
pprint(data)

print("[创建namespace]")
# primary_key 为用户自定义主键; 不指定时由系统生成 _id
resp = client.create_namespace(
    Bucket=bucket,
    Namespace=namespace,
    Schema={
        'primary_key': 'id',
        'fields': {
            'id': {'type': 'string'},
            'title': {'type': 'text', 'full_text_search': {'enabled': True}},
            'price': {'type': 'float64', 'filterable': True},
            'tag': {'type': 'string'},
            'embedding': {'type': 'vector', 'dimension': 3, 'data_type': 'float32', 'distance_metric': 'cosine'}
        }
    },
    Metadata={'owner': 'search-team'}
)
print(resp)

print("[获取namespace]")
resp, data = client.get_namespace(
    Bucket=bucket,
    Namespace=namespace
)
# print(resp)
pprint(data)

print("[修改namespace: 新增字段]")
resp, data = client.modify_namespace(
    Bucket=bucket,
    Namespace=namespace,
    AddColumns=[{'name': 'category', 'type': 'string'}]
)
# print(resp)
pprint(data)

print("[修改namespace: 删除字段]")
resp, data = client.modify_namespace(
    Bucket=bucket,
    Namespace=namespace,
    DropColumns=['category']
)
# print(resp)
pprint(data)

print("[删除namespace]")
resp = client.delete_namespace(
    Bucket=bucket,
    Namespace=namespace
)
print(resp)
