#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
示例：使用角色授权方式初始化 CosS3Client。

SDK 内部会自动调用 STS 接口获取临时密钥（SecretId / SecretKey / Token），
并在临时密钥过期前自动刷新，调用方无需手动管理临时密钥。

运行前需设置以下环境变量：
    COS_SECRET_ID       调用方的永久 SecretId（用于调用 STS 接口）
    COS_SECRET_KEY      调用方的永久 SecretKey

安装依赖：
    pip install -U qcloud-python-sts cos-python-sdk-v5
"""

import os

from qcloud_cos import CosConfig, CosS3Client, RoleCredentialProvider

# ---------------------------------------------------------------------------
# 构建凭证提供者 —— SDK 会通过 STS AssumeRole 接口自动获取并刷新临时密钥
# ---------------------------------------------------------------------------
provider = RoleCredentialProvider(
    SecretId=os.getenv('COS_SECRET_ID'),
    SecretKey=os.getenv('COS_SECRET_KEY'),
    # RoleArn 可在 CAM 控制台 访问管理 -> 角色 中获取：https://console.cloud.tencent.com/cam/role
    RoleArn='qcs::cam::uin/100000000001:roleName/COS_Access_Role',
    DurationSeconds=1800,   # 临时密钥有效期（秒）
    Region='ap-guangzhou',  # 需与存储桶所在地域保持一致
)

# ---------------------------------------------------------------------------
# 初始化 CosConfig 和 CosS3Client —— 无需手动传入临时密钥
# ---------------------------------------------------------------------------
config = CosConfig(Region='ap-guangzhou', CredentialInstance=provider)
client = CosS3Client(config)

# ---------------------------------------------------------------------------
# 示例：下载存储桶中的对象
# ---------------------------------------------------------------------------
response = client.get_object(Bucket='my-bucket-1250000000', Key='example.txt')
with open('example.txt', 'wb') as f:
    f.write(response['Body'].get_raw_stream().read())
