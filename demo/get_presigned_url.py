# -*- coding=utf-8
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
import sys
import os
import logging
import requests
import time

# 正常情况日志级别使用 INFO，需要定位时可以修改为 DEBUG，此时 SDK 会打印和服务端的通信信息
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# 1. 设置用户属性, 包括 secret_id, secret_key, region 等。Appid 已在 CosConfig 中移除，请在参数 Bucket 中带上 Appid。Bucket 由 BucketName-Appid 组成
secret_id = os.environ['COS_SECRET_ID']     # 用户的 SecretId，建议使用子账号密钥，授权遵循最小权限指引，降低使用风险。子账号密钥获取可参见 https://cloud.tencent.com/document/product/598/37140
secret_key = os.environ['COS_SECRET_KEY']   # 用户的 SecretKey，建议使用子账号密钥，授权遵循最小权限指引，降低使用风险。子账号密钥获取可参见 https://cloud.tencent.com/document/product/598/37140
region = 'ap-beijing'      # 替换为用户的 region，已创建桶归属的 region 可以在控制台查看，https://console.cloud.tencent.com/cos5/bucket
                           # COS 支持的所有 region 列表参见https://cloud.tencent.com/document/product/436/6224
token = None               # 如果使用永久密钥不需要填入 token，如果使用临时密钥需要填入，临时密钥生成和使用指引参见 https://cloud.tencent.com/document/product/436/14048
scheme = 'https'           # 指定使用 http/https 协议来访问 COS，默认为 https，可不填

config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token, Scheme=scheme)
client = CosS3Client(config)

'''生成上传预签名 URL
'''

# 生成上传 URL，未限制请求头部和请求参数
url = client.get_presigned_url(
    Method='PUT',
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    Expired=120  # 120秒后过期，过期时间请根据自身场景定义
)
print(url)

# 生成上传 URL，同时限制存储类型和上传速度
url = client.get_presigned_url(
    Method='PUT',
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    Headers={
        'x-cos-storage-class':'STANDARD_IA', 
        'x-cos-traffic-limit':'819200' # 预签名 URL 本身是不包含请求头部的，但请求头部会算入签名，那么使用 URL 时就必须携带请求头部，并且请求头部的值必须是这里指定的值
    },
    Expired=300  # 300秒后过期，过期时间请根据自身场景定义
)
print(url)

# 生成上传 URL，只能上传指定的文件内容
url = client.get_presigned_url(
    Method='PUT',
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    Headers={'Content-MD5':'string'}, # 约定使用此 URL 上传对象的人必须携带 MD5 请求头部，并且请求头部的值必须是这里指定的值，这样就限定了文件的内容
    Expired=300  # 300秒后过期，过期时间请根据自身场景定义
)
print(url)

# 生成上传 URL，只能用于上传 ACL
url = client.get_presigned_url(
    Method='PUT',
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    Params={'acl':''}, # 指定了请求参数，则 URL 中会携带此请求参数，并且请求参数会算入签名，不允许使用者修改请求参数的值
    Expired=120  # 120秒后过期，过期时间请根据自身场景定义
)
print(url)

# 生成上传 URL，请求域名不算入签名，签名后使用者需要修改请求域名时使用
url = client.get_presigned_url(
    Method='PUT',
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    SignHost=False, # 请求域名不算入签名，允许使用者修改请求域名，有一定安全风险
    Expired=120  # 120秒后过期，过期时间请根据自身场景定义
)
print(url)

# 使用上传 URL
retry = 1 # 简单重试1次
for i in range(retry + 1):
    response = requests.put(url=url, data=b'123')
    if response.status_code == 400 or response.status_code >= 500: # 只对400和5xx错误码进行重试
        time.sleep(1) # 延迟 1s 后再重试
        continue
    # 请求结束, 打印结果并退出循环
    print(response)
    break


'''生成下载预签名 URL
'''

# 生成下载 URL，未限制请求头部和请求参数
url = client.get_presigned_url(
    Method='GET',
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    Expired=120  # 120秒后过期，过期时间请根据自身场景定义
)
print(url)

# 生成下载 URL，同时指定响应的 content-disposition 头部，让文件在浏览器另存为，而不是显示
url = client.get_presigned_url(
    Method='GET',
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    Params={
        'response-content-disposition':'attachment; filename=example.xlsx' # 下载时保存为指定的文件
        # 除了 response-content-disposition，还支持 response-cache-control、response-content-encoding、response-content-language、
        # response-content-type、response-expires 等请求参数，详见下载对象 API，https://cloud.tencent.com/document/product/436/7753
    }, 
    Expired=120  # 120秒后过期，过期时间请根据自身场景定义
)
print(url)

# 生成下载 URL，同时限制下载速度
url = client.get_presigned_url(
    Method='GET',
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    Headers={'x-cos-traffic-limit':'819200'}, # 预签名URL本身是不包含请求头部的，但请求头部会算入签名，那么使用 URL 时就必须携带请求头部，并且请求头部的值必须是这里指定的值
    Expired=300  # 300秒后过期，过期时间请根据自身场景定义
)
print(url)

# 生成下载 URL，只能用于下载 ACL
url = client.get_presigned_url(
    Method='GET',
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    Params={'acl':''}, # 指定了请求参数，则 URL 中会携带此请求参数，并且请求参数会算入签名，不允许使用者修改请求参数的值
    Expired=120  # 120秒后过期，过期时间请根据自身场景定义
)
print(url)

# 生成下载 URL，请求域名不算入签名，签名后使用者需要修改请求域名时使用
url = client.get_presigned_url(
    Method='GET',
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    SignHost=False, # 请求域名不算入签名，允许使用者修改请求域名，有一定安全风险
    Expired=120  # 120秒后过期，过期时间请根据自身场景定义
)
print(url)

# 使用下载URL
retry = 1 # 简单重试1次
for i in range(retry + 1):
    response = requests.get(url)
    if response.status_code == 400 or response.status_code >= 500: # 只对400和5xx错误码进行重试
        time.sleep(1) # 延迟 1s 后再重试
        continue
    # 请求结束, 打印结果并退出循环
    print(response)
    break


'''使用临时密钥生成下载预签名 URL
'''

# 生成下载 URL
url = client.get_presigned_url(
    Method='GET',
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    Headers={'x-cos-traffic-limit':'819200'}, # 预签名 URL 本身是不包含请求头部的，但请求头部会算入签名，那么使用 URL 时就必须携带请求头部，并且请求头部的值必须是这里指定的值
    Params={
        'x-cos-security-token': 'string' # 使用临时密钥需要填入 Token 到请求参数
    },
    Expired=120,  # 120秒后过期，过期时间请根据自身场景定义
    SignHost=False # 请求域名不算入签名，签名后使用者需要修改请求域名时使用，有一定安全风险
)
print(url)

# 使用下载 URL
retry = 1 # 简单重试1次
for i in range(retry + 1):
    response = requests.get(url)
    if response.status_code == 400 or response.status_code >= 500: # 只对400和5xx错误码进行重试
        time.sleep(1) # 延迟 1s 后再重试
        continue
    # 请求结束, 打印结果并退出循环
    print(response)
    break


'''生成下载对象的预签名 URL
'''

# 生成下载 URL，未限制请求头部和请求参数
url = client.get_presigned_download_url(
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    Expired=120  # 120秒后过期，过期时间请根据自身场景定义
)
print(url)

# 生成下载 URL，同时指定响应的 content-disposition 头部，让文件在浏览器另存为，而不是显示
url = client.get_presigned_download_url(
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    Params={
        'response-content-disposition':'attachment; filename=example.xlsx' # 下载时保存为指定的文件
        # 除了 response-content-disposition，还支持 response-cache-control、response-content-encoding、response-content-language、
        # response-content-type、response-expires 等请求参数，详见下载对象 API，https://cloud.tencent.com/document/product/436/7753
    }, 
    Expired=120  # 120秒后过期，过期时间请根据自身场景定义
)
print(url)

# 生成下载 URL，同时限制下载速度
url = client.get_presigned_download_url(
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    Headers={'x-cos-traffic-limit':'819200'}, # 预签名 URL 本身是不包含请求头部的，但请求头部会算入签名，那么使用 URL 时就必须携带请求头部，并且请求头部的值必须是这里指定的值
    Expired=300  # 300秒后过期，过期时间请根据自身场景定义
)
print(url)

# 生成下载 URL，只能用于下载 ACL
url = client.get_presigned_download_url(
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    Params={'acl':''}, # 指定了请求参数，则 URL 中会携带此请求参数，并且请求参数会算入签名，不允许使用者修改请求参数的值
    Expired=120  # 120秒后过期，过期时间请根据自身场景定义
)
print(url)

# 生成下载 URL，请求域名不算入签名，签名后使用者需要修改请求域名时使用
url = client.get_presigned_download_url(
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    SignHost=False, # 请求域名不算入签名，允许使用者修改请求域名，有一定安全风险
    Expired=120  # 120秒后过期，过期时间请根据自身场景定义
)
print(url)

# 生成下载 URL，使用临时密钥签名
url = client.get_presigned_download_url(
    Bucket='examplebucket-1250000000',
    Key='exampleobject',
    Params={
        'x-cos-security-token': 'string'  # 使用永久密钥不需要填入 token，如果使用临时密钥需要填入
    }
)
print(url)

# 使用下载 URL
retry = 1 # 简单重试1次
for i in range(retry + 1):
    response = requests.get(url)
    if response.status_code == 400 or response.status_code >= 500: # 只对400和5xx错误码进行重试
        time.sleep(1) # 延迟 1s 后再重试
        continue
    # 请求结束, 打印结果并退出循环
    print(response)
    break
