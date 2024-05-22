# -*- coding=utf-8
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
from qcloud_cos.cos_threadpool import SimpleThreadPool
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

# 删除单个对象
response = client.delete_object(
    Bucket='examplebucket-1250000000',
    Key='exampleobject'
)
print(response)

# 删除目录
to_delete_dir='path/to/delete/dir/'
response = client.delete_object(
    Bucket='examplebucket-1250000000',
    Key=to_delete_dir
)
print(response)

# 前缀批量删除
# 删除指定前缀 (prefix)的文件
bucket = 'examplebucket-1250000000'
marker = ''
prefix = 'root/logs'
while True:
    response = client.list_objects(Bucket=bucket, Prefix=prefix, Marker=marker)
    if 'Contents' in response:
        for content in response['Contents']:
            print("delete object: ", content['Key'])
            client.delete_object(Bucket=bucket, Key=content['Key'])


    if response['IsTruncated'] == 'false':
        break


    marker = response['NextMarker']

# 删除多个对象
response = client.delete_objects(
    Bucket='examplebucket-1250000000',
    Delete={
        'Object': [
            {
                'Key': 'exampleobject1'
            },
            {
                'Key': 'exampleobject2'
            }
        ]
    }
)

# 批量删除对象（删除目录）

bucket = 'examplebucket-1250000000'
folder = 'folder/' # 要删除的目录，'/'结尾表示目录

def delete_cos_dir():
    pool = SimpleThreadPool()
    marker = ""
    while True:
        file_infos = []

        # 列举一页100个对象
        response = client.list_objects(Bucket=bucket, Prefix=folder, Marker=marker, MaxKeys=100)

        if "Contents" in response:
            contents = response.get("Contents")
            file_infos.extend(contents)
            pool.add_task(delete_files, file_infos)

        # 列举完成，退出
        if response['IsTruncated'] == 'false':
            break

        # 列举下一页
        marker = response["NextMarker"]

    pool.wait_completion()
    return None   


def delete_files(file_infos):
    # 构造批量删除请求
    delete_list = []
    for file in file_infos:
        delete_list.append({"Key": file['Key']})

    response = client.delete_objects(Bucket=bucket, Delete={"Object": delete_list})
    print(response)

delete_cos_dir()