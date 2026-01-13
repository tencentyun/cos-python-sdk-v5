# -*- coding=utf-8

from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
import sys
import os
import logging

# logging.basicConfig(level=logging.INFO, stream=sys.stdout)


def _recover_main(src_region, src_bucket, dst_region, dst_bucket, secret_id, secret_key, prefix):

    src_client = CosS3Client(CosConfig(Region=src_region, SecretId=secret_id, SecretKey=secret_key))
    dst_client = CosS3Client(CosConfig(Region=dst_region, SecretId=secret_id, SecretKey=secret_key))

    # 列举操作的分页参数
    key_marker = ''
    versionId_marker = ''

    recovered_keys = set() # 记录已经恢复的对象

    while True:
        response = src_client.list_objects_versions(
            Bucket=src_bucket,
            Prefix=prefix,
            KeyMarker=key_marker,
            VersionIdMarker=versionId_marker,
        )

        # 从 Version 取出用于恢复的对象版本
        if 'Version' in response:
            for version in response['Version']:
                key = version['Key']
                versionId = version['VersionId']
                if not key in recovered_keys:
                    print('recover from object: {src_bucket}/{key}(versionId={versionId})'.format(
                        src_bucket=src_bucket, key=key, versionId=versionId))
                    try:
                        dst_client.copy(
                            Bucket=dst_bucket,
                            Key=key,
                            CopySource={
                                'Bucket': src_bucket,
                                'Key': key,
                                'Region': src_region,
                                'VersionId': versionId,
                            }
                        )
                        recovered_keys.add(key)
                        print("success recover object: {src_bucket}/{key}(versionId={versionId}) => {dst_bucket}/{key}".format(
                            src_bucket=src_bucket, key=key, versionId=versionId, dst_bucket=dst_bucket))
                    except Exception as e:
                        print(e)
                        pass
        
        if response['IsTruncated'] == 'false':
            break

        key_marker = response['NextKeyMarker']
        versionId_marker = response['NextVersionIdMarker']
    


if __name__ == '__main__':
    # 使用场景:
    # src_bucket: 备份桶
    # dst_bucket: 目标桶
    # 目标桶(dst_bucket)里的对象被误删，遍历备份桶(src_bucket)的对象，选择非删除标记的当前版本对象，复制到目标桶(dst_bucket)从而完成恢复

    # 备份桶信息
    src_region = 'ap-guangzhou'
    src_bucket = 'bucket-backup-1250000000'

    # 目标桶信息
    dst_region = 'ap-guangzhou'
    dst_bucket = 'bucket-1250000000'

    # 从环境变量获取密钥
    secret_id = os.environ['COS_SECRET_ID']
    secret_key = os.environ['COS_SECRET_KEY']

    prefix = ''  # 设置要恢复的对象前缀，例如 'docs/'，默认空字符串表示恢复所有对象

    _recover_main(
        src_region=src_region,
        src_bucket=src_bucket,
        dst_region=dst_region,
        dst_bucket=dst_bucket,
        secret_id=secret_id,
        secret_key=secret_key,
        prefix=prefix
    )