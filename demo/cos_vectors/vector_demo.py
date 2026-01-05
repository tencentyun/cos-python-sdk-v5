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

config = CosConfig(
    Region=region, 
    SecretId=secret_id, 
    SecretKey=secret_key,
    Scheme=scheme,
    Domain="vectors.ap-guangzhou.internal.tencentcos.com",
    Token=token
)
client = CosVectorsClient(config)

print("[获取向量索引]")
resp, data = client.get_index(
    Bucket='example-bucket-1250000000',
    Index='idx-dim3'
)
# print(resp)
pprint(data)

print("[插入向量]")
resp = client.put_vectors(
    Bucket='example-bucket-1250000000',
    Index='idx-dim3',
    Vectors=[
        {
            'key': 'vector1',
            'data': {"float32":[0.1, 0.2, 0.3]},
            'metadata': {
                'key1': 'value1',
                'key2': 'value2'
            }
        },
        {
            'key': 'vector2',
            'data': {"float32":[0.4, 0.5, 0.6]},
            'metadata': {
                'key1': 'value1',
                'key2': 'value2'
            }
        }
    ]
)
print(resp)

print("[获取向量]")
resp, data = client.get_vectors(
    Bucket='example-bucket-1250000000',
    Index='idx-dim3',
    Keys=['vector1', 'vector2'],
    ReturnData=True,
    ReturnMetaData=True
)
# print(resp)
pprint(data)

print("[查询向量]")
resp, data = client.query_vectors(
    Bucket='example-bucket-1250000000',
    Index='idx-dim3',
    QueryVector={"float32":[0.1, 0.2, 0.3]},
    TopK=10
)
# print(resp)
pprint(data)

print("[删除向量]")
resp = client.delete_vectors(
    Bucket='example-bucket-1250000000',
    Index='idx-dim3',
    Keys=['vector1', 'vector2']
)
print(resp)

print("[列出向量]")
resp, data = client.list_vectors(
    Bucket='example-bucket-1250000000',
    Index='idx-dim3',
    MaxResults=10
)
# print(resp)
pprint(data)
