# -*- coding=utf-8
import base64
import jwt
from urllib.parse import quote, quote_plus
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
from datetime import datetime, timedelta

import sys
import logging
import os

# 腾讯云COSV5Python SDK, 目前可以支持Python2.6与Python2.7以及Python3.x

# 媒体处理相关API请参考 https://cloud.tencent.com/document/product/460/84790

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# 设置用户属性, 包括secret_id, secret_key, region
# appid已在配置中移除,请在参数Bucket中带上appid。Bucket由bucketname-appid组成
# 这里秘钥是从环境变量取得，如自己测试可改成自己对应的秘钥
secret_id = os.environ["SECRETID"] # 替换为用户的 SecretId，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
secret_key = os.environ["SECRETKEY"] # 替换为用户的 SecretKey，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
region = 'ap-chongqing' # 替换为用户的 region，已创建桶归属的region可以在控制台查看，https://console.cloud.tencent.com/cos5/bucket
# COS支持的所有region列表参见https://www.qcloud.com/document/product/436/6224
token = None # 如果使用永久密钥不需要填入token，如果使用临时密钥需要填入，临时密钥生成和使用指引参见https://cloud.tencent.com/document/product/436/14048

config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token, Scheme='https') # 获取配置对象
client = CosS3Client(config)


bucket_name = 'demo-1250000000'
play_key = 'play_key'
object_name = 'test.m3u8'


def generate_token():
    now = datetime.now()
    expire_time = now + timedelta(minutes=30)
    path_encoded = quote(object_name)
    object = quote_plus(path_encoded)

    headers = {
        # 加密的算法，固定为 HS256
        "alg": "HS256",
        # 类型，固定为 JWT
        "typ": "JWT"
    }
    token_info = {
        # 固定为 CosCiToken， 必填参数
        'Type': 'CosCiToken',
        # app id，必填参数
        'AppId': '1250000000',
        # 播放文件所在的BucketId， 必填参数
        'BucketId': bucket_name,
        # 播放文件名
        'Object': object,
        # 固定为client，必填参数
        'Issuer': 'client',
        # token颁发时间戳，必填参数
        'IssuedTimeStamp': now.timestamp(),
        # token过期时间戳，非必填参数，默认1天过期
        'ExpireTimeStamp': expire_time.timestamp(),
        # token使用次数限制，非必填参数，默认限制100000次
        'UsageLimit': 20,
        # 是否加密解密密钥（播放时解密ts视频流的密钥），1表示对解密密钥加密，0表示不对解密密钥加密。
        'ProtectContentKey': 1,
    }
    if token_info['ProtectContentKey'] == 1:
        public_key = """-----BEGIN PUBLIC KEY-----
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxBgQCj9GNktf2yA0Mp8aCzxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx54Jl4NVNewBLPZq1WFxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxKpSCdl9hHxFZ732ixxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxx
-----END PUBLIC KEY-----"""
        base64_public_key = base64.urlsafe_b64encode(public_key.encode('utf-8')).decode('utf-8')
        token_info.update({
            # 保护模式，填写为 rsa1024 ，则表示使用 RSA 非对称加密的方式保护，公私钥对长度为 1024 bit
            'ProtectSchema': "rsa1024",
            # 公钥。1024 bit 的 RSA 公钥，需使用 Base64 进行编码
            'PublicKey': base64_public_key,
        })
    return jwt.encode(token_info, play_key, algorithm="HS256", headers=headers)


def get_url():
    url = client.get_presigned_download_url(
        Bucket=bucket_name,  # 存储桶名称
        Key="/" + object_name,
        Expired=3600,    # 预签名超时时间
    )
    if token is not None:
        url = url + "&x-cos-security-token=" + token
    url = url + "&tokenType=JwtToken&expires=3600&ci-process=pm3u8&token=" + generate_token()
    return url


if __name__ == '__main__':
    print(generate_token())
    print(get_url())
