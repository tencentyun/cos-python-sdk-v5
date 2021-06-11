# -*- coding=utf-8
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
from qcloud_cos import CosServiceError
from qcloud_cos import CosClientError
from qcloud_cos.cos_threadpool import SimpleThreadPool

import sys
import os
import logging

# 腾讯云COSV5Python SDK, 目前可以支持Python2.6与Python2.7以及Python3.x

# pip安装指南:pip install -U cos-python-sdk-v5

# cos最新可用地域,参照https://www.qcloud.com/document/product/436/6224

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# 设置用户属性, 包括secret_id, secret_key, region
# appid已在配置中移除,请在参数Bucket中带上appid。Bucket由bucketname-appid组成
secret_id = ''     # 替换为用户的secret_id
secret_key = ''     # 替换为用户的secret_key
region = 'ap-guangzhou'    # 替换为用户的region
token = None               # 使用临时密钥需要传入Token，默认为空,可不填
config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
client = CosS3Client(config)

bucket='examplebucket-1250000000'

# 删除目录
# 对象存储中，目录是特殊的路径以‘/’结尾的object。调用Delete Object接口即可
try:
    to_delete_dir='path/to/delete/dir/'
    response = client.delete_object(
        Bucket=bucket,
        Key=to_delete_dir,
    )
    print(response)
except CosServiceError as e:
    print(e.get_status_code())

uploadDir = '/root/logs'

g = os.walk(uploadDir)
# 创建上传的线程池
pool = SimpleThreadPool()
for path, dir_list, file_list in g:
    for file_name in file_list:
        srcKey = os.path.join(path, file_name)
        cosObjectKey = srcKey.strip('/')
        # 判断COS上文件是否存在
        exists = False
        try:
            response = client.head_object(Bucket=bucket, Key=cosObjectKey)
            exists = True
        except CosServiceError as e:
            if e.get_status_code() == 404:
                exists = False
            else:
                print("Error happened, reupload it.")
        if not exists:
            print("File %s not exists in cos, upload it", srcKey)
            pool.add_task(client.upload_file, bucket, cosObjectKey, srcKey)


pool.wait_completion()
result = pool.get_result()
if not result['success_all']:
    print("Not all files upload sucessed. you should retry")


# 删除指定前缀 (prefix)的文件
is_over = False
marker = ''
prefix = 'root/logs'
while not is_over:
    try:
        response = client.list_objects(Bucket=bucket, Prefix=prefix, Marker=marker)
        if response['Contents']:
            for content in response['Contents']:
                print("delete object: ", content['Key'])
                client.delete_object(Bucket=bucket, Key=content['Key'])

            if response['IsTruncated'] == 'false':
                is_over = True
                marker = response['Marker']

    except CosServiceError as e:
        print(e.get_origin_msg())
        print(e.get_digest_msg())
        print(e.get_status_code())
        print(e.get_error_code())
        print(e.get_error_msg())
        print(e.get_resource_location())
        print(e.get_trace_id())
        print(e.get_request_id())
        break


# 移动对象
srcKey = 'demo.py'  # 原始的对象路径
destKey = 'dest_object_key'   # 目的对象路径

try:
    response = client.copy_object(
        Bucket=bucket,
        Key=destKey,
        CopySource={
            'Bucket':bucket,
            'Key':srcKey,
            'Region':'ap-guangzhou',
        })
    client.delete_object(Bucket=bucket, Key=srcKey)
except CosException as e:
     print(e.get_error_msg())
