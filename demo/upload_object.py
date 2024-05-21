# -*- coding=utf-8
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
from qcloud_cos.cos_threadpool import SimpleThreadPool
from qcloud_cos.cos_exception import CosClientError, CosServiceError

import sys
import os
import logging

# 正常情况日志级别使用 INFO，需要定位时可以修改为 DEBUG，此时 SDK 会打印和服务端的通信信息
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# 1. 设置用户属性, 包括 secret_id, secret_key, region 等。Appid 已在 CosConfig 中移除，请在参数 Bucket 中带上 Appid。Bucket 由 BucketName-Appid 组成
secret_id = os.environ['COS_SECRET_ID']     # 用户的 SecretId，建议使用子账号密钥，授权遵循最小权限指引，降低使用风险。子账号密钥获取可参见 https://cloud.tencent.com/document/product/598/37140
secret_key = os.environ['COS_SECRET_KEY']   # 用户的 SecretKey，建议使用子账号密钥，授权遵循最小权限指引，降低使用风险。子账号密钥获取可参见 https://cloud.tencent.com/document/product/598/37140
region = 'ap-beijing'      # 替换为用户的 region，已创建桶归属的 region 可以在控制台查看，https://console.cloud.tencent.com/cos5/bucket
                           # COS 支持的所有 region 列表参见 https://cloud.tencent.com/document/product/436/6224
token = None               # 如果使用永久密钥不需要填入 token，如果使用临时密钥需要填入，临时密钥生成和使用指引参见 https://cloud.tencent.com/document/product/436/14048
scheme = 'https'           # 指定使用 http/https 协议来访问 COS，默认为 https，可不填

config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token, Scheme=scheme)
client = CosS3Client(config)

'''上传对象（断点续传）
'''

# 使用高级接口上传一次，不重试，此时没有使用断点续传的功能
response = client.upload_file(
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    LocalFilePath='local.txt',
    EnableMD5=False,
    progress_callback=None
)

# 使用高级接口断点续传，失败重试时不会上传已成功的分块(这里重试10次)
for i in range(0, 10):
    try:
        response = client.upload_file(
        Bucket='examplebucket-1250000000',
        Key='exampleobject',
        LocalFilePath='local.txt')
        break
    except CosClientError or CosServiceError as e:
        print(e)


'''批量上传（本地文件夹上传）
'''

uploadDir = '/root/logs'
bucket = 'examplebucket-125000000'
g = os.walk(uploadDir)
# 创建上传的线程池
pool = SimpleThreadPool()
for path, dir_list, file_list in g:
    for file_name in file_list:
        srcKey = os.path.join(path, file_name)
        cosObjectKey = srcKey.strip('/')
        # 判断 COS 上文件是否存在
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
    print("Not all files upload successed. you should retry")


'''简单文件上传
'''

# 文件流 简单上传
file_name = 'test.txt'
with open('test.txt', 'rb') as fp:
    response = client.put_object(
        Bucket='examplebucket-1250000000',  # Bucket 由 BucketName-APPID 组成
        Body=fp,
        Key=file_name,
        StorageClass='STANDARD',
        ContentType='text/html; charset=utf-8'
    )
    print(response['ETag'])

# 字节流 简单上传
response = client.put_object(
    Bucket='examplebucket-1250000000',
    Body=b'abcdefg',
    Key=file_name
)
print(response['ETag'])

# 本地路径 简单上传
response = client.put_object_from_local_file(
    Bucket='examplebucket-1250000000',
    LocalFilePath='local.txt',
    Key=file_name
)
print(response['ETag'])

# 设置 HTTP 头部 简单上传
response = client.put_object(
    Bucket='examplebucket-1250000000',
    Body=b'test',
    Key=file_name,
    ContentType='text/html; charset=utf-8'
)
print(response['ETag'])

# 设置自定义头部 简单上传
response = client.put_object(
    Bucket='examplebucket-1250000000',
    Body=b'test',
    Key=file_name,
    Metadata={
        'x-cos-meta-key1': 'value1',
        'x-cos-meta-key2': 'value2'
    }
)
print(response['ETag'])

# 上传时限速
with open('test.bin', 'rb') as fp:
    response = client.put_object(
        Bucket='examplebucket-1250000000',  
        Key='exampleobject',
        Body=fp,
        TrafficLimit='819200'
    )
    print(response['ETag'])

'''查询分块上传
'''

response = client.list_multipart_uploads(
    Bucket='examplebucket-1250000000',
    Prefix='dir'
)

'''初始化分块上传
'''

response = client.create_multipart_upload(
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    StorageClass='STANDARD'
)

'''上传分块
'''

# 注意，上传分块的块数最多10000块
response = client.upload_part(
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    Body=b'b'*1024*1024,
    PartNumber=1,
    UploadId='exampleUploadId'
)

'''复制分块
'''

response = client.upload_part_copy(
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    PartNumber=1,
    UploadId='exampleUploadId',
    CopySource={
        'Bucket': 'sourcebucket-1250000000', 
        'Key': 'exampleobject', 
        'Region': 'ap-guangzhou'
    }
)

'''查询已上传分块
'''

response = client.list_parts(
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    UploadId='exampleUploadId'
)

'''完成分块上传
'''

response = client.complete_multipart_upload(
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    UploadId='exampleUploadId',
    MultipartUpload={
        'Part': [
            {
                'ETag': 'string',
                'PartNumber': 1
            },
            {
                'ETag': 'string',
                'PartNumber': 2
            },
        ]
    },
)

'''终止分块上传
'''

response = client.abort_multipart_upload(
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    UploadId='exampleUploadId'
)
