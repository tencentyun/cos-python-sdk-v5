# -*- coding=utf-8
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
import sys
import os
import logging

# 正常情况日志级别使用 INFO，需要定位时可以修改为 DEBUG，此时 SDK 会打印和服务端的通信信息
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# 1. 设置用户属性, 包括 secret_id, secret_key, region等。Appid 已在 CosConfig 中移除，请在参数 Bucket 中带上 Appid。Bucket 由 BucketName-Appid 组成
secret_id = os.environ['COS_SECRET_ID']     # 用户的 SecretId，建议使用子账号密钥，授权遵循最小权限指引，降低使用风险。子账号密钥获取可参见 https://cloud.tencent.com/document/product/598/37140
secret_key = os.environ['COS_SECRET_KEY']   # 用户的 SecretKey，建议使用子账号密钥，授权遵循最小权限指引，降低使用风险。子账号密钥获取可参见 https://cloud.tencent.com/document/product/598/37140
region = 'ap-beijing'      # 替换为用户的 region，已创建桶归属的 region 可以在控制台查看，https://console.cloud.tencent.com/cos5/bucket
                           # COS 支持的所有 region 列表参见 https://cloud.tencent.com/document/product/436/6224
token = None               # 如果使用永久密钥不需要填入 token，如果使用临时密钥需要填入，临时密钥生成和使用指引参见 https://cloud.tencent.com/document/product/436/14048
scheme = 'https'           # 指定使用 http/https 协议来访问 COS，默认为 https，可不填

config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token, Scheme=scheme)
client = CosS3Client(config)

# 设置生命周期
response = client.put_bucket_lifecycle(
    Bucket='examplebucket-1250000000',
    LifecycleConfiguration={
        'Rule': [
            {
                'ID': 'string', # 设置规则的 ID，例如Rule-1
                'Filter': { 
                    'Prefix': '' # 配置前缀为空，桶内所有对象都会执行此规则
                },
                'Status': 'Enabled', # Enabled 表示启用规则
                'Expiration': {
                    'Days': 200 # 设置对象的当前版本200天后过期删除
                },
                'Transition': [
                    {
                        'Days': 100, # 设置对象的当前版本100天后沉降
                        'StorageClass': 'Standard_IA' # 沉降为低频存储
                    },
                ],
                'AbortIncompleteMultipartUpload': {
                    'DaysAfterInitiation': 7 # 设置7天后回收未合并的分块
                }
            }
        ]   
    }
)

# 查询生命周期
response = client.get_bucket_lifecycle(
    Bucket='examplebucket-1250000000',
)

# 删除生命周期
response = client.delete_bucket_lifecycle(
    Bucket='examplebucket-1250000000',
)

