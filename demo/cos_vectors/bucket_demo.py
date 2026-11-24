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
    Domain="vectors.ap-guangzhou.coslake.com",
    Token=token
)
client = CosVectorsClient(config)

print("[列出向量桶: 全部类型]")
# 不填 Mode 时不过滤, 返回 CLASSIC 与 ENHANCED 两种桶
resp, data = client.list_vector_buckets()
# print(resp)
pprint(data)

print("[列出向量桶: 只列 CLASSIC]")
resp, data = client.list_vector_buckets(
    Mode='CLASSIC',
    MaxResults=10
)
# print(resp)
pprint(data)

print("[列出向量桶: 只列 ENHANCED]")
# ENHANCED 桶支持 Native API(namespace/文档接口)
resp, data = client.list_vector_buckets(
    Mode='ENHANCED',
    MaxResults=10
)
# print(resp)
pprint(data)

print("[创建向量桶: CLASSIC, 用于向量索引]")
# 不填 Mode 时不发送 mode 字段, 由服务端按默认策略创建(当前默认 CLASSIC), 可配合 index_demo.py / vector_demo.py 使用
resp, data = client.create_vector_bucket(
    Bucket='example-bucket-1250000000'
)
# print(resp)
pprint(data)

print("[获取向量桶: CLASSIC]")
resp, data = client.get_vector_bucket(
    Bucket='example-bucket-1250000000'
)
# print(resp)
# 响应中的 mode 为桶类型
pprint(data)

print("[创建向量桶: ENHANCED, 用于 namespace]")
# ENHANCED 桶支持 Native API, 可配合 namespace_demo.py / document_demo.py 使用
# 桶类型创建后不可修改, 需要重建
resp, data = client.create_vector_bucket(
    Bucket='example-bucket-enhanced-1250000000',
    Mode='ENHANCED'
)
# print(resp)
pprint(data)

print("[获取向量桶: ENHANCED]")
resp, data = client.get_vector_bucket(
    Bucket='example-bucket-enhanced-1250000000'
)
# print(resp)
pprint(data)

print("[删除向量桶: CLASSIC]")
resp = client.delete_vector_bucket(
    Bucket='example-bucket-1250000000'
)
print(resp)

print("[删除向量桶: ENHANCED]")
# 桶内还有 namespace 时需要先删除 namespace, 参见 namespace_demo.py
resp = client.delete_vector_bucket(
    Bucket='example-bucket-enhanced-1250000000'
)
print(resp)
