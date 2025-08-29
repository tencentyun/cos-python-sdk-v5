# -*- coding=utf-8

from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
import sys
import os
import logging

# logging.basicConfig(level=logging.INFO, stream=sys.stdout)


def _recover_main(src_region, src_secret_id, src_secret_key, src_bucket, prefix):

    src_client = CosS3Client(CosConfig(Region=src_region, SecretId=src_secret_id, SecretKey=src_secret_key))

    key_marker = ''
    versionId_marker = ''
    while True:
        response = src_client.list_objects_versions(
            Bucket=src_bucket,
            Prefix=prefix,
            KeyMarker=key_marker,
            VersionIdMarker=versionId_marker,
        )
        delete_marker_keys = list()
        recovered_keys = list()
        # 从 DeleteMarker 取出被删除的对象
        if 'DeleteMarker' in response:
            for version in response['DeleteMarker']:
                if version['IsLatest'] == 'true':
                    delete_marker_keys.append(version['Key'])
        
        if len(delete_marker_keys) == 0:
            print('no delete markers found, no data to recover, continue listing')

        # 从 Version 取最新的版本号
        if 'Version' in response:
            for version in response['Version']:
                key = version['Key']
                versionId = version['VersionId']
                if key in delete_marker_keys and not key in recovered_keys:
                    print('recover from key:{key}, versionId:{versionId}'.format(key=key, versionId=versionId))
                    try:
                        src_client.copy(
                            Bucket=src_bucket,
                            Key=key,
                            CopySource={
                                'Bucket': src_bucket,
                                'Key': key,
                                'Region': src_region,
                                'VersionId': versionId,
                            }
                        )
                        recovered_keys.append(key)
                        print("success recover object: {key}(versionId={versionId}) => {key}".format(
                            src_bucket=src_bucket, key=key, versionId=versionId))
                    except Exception as e:
                        print(e)
                        pass

        if response['IsTruncated'] == 'false':
            break

        key_marker = response['NextKeyMarker']
        versionId_marker = response['NextVersionIdMarker']


if __name__ == '__main__':
    # 使用场景:
    # 根据源桶src_bucket的删除标记从历史版本里把文件恢复出来

    # 源桶信息
    src_region = 'ap-guangzhou'  # 源地域
    src_secret_id = ''  # 源桶SecretID
    src_secret_key = ''  # 源桶SecretKey
    src_bucket = 'bucket-1200000000'  # 源桶名

    prefix = ''  # 设置要恢复的对象前缀

    _recover_main(src_region, src_secret_id, src_secret_key, src_bucket, prefix)