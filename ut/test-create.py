# -*- coding=utf-8
import random
import sys
import time
import hashlib
import os
import requests
import json
from qcloud_cos import CosS3Client
from qcloud_cos import CosConfig
from qcloud_cos import CosServiceError
from qcloud_cos import get_date
from qcloud_cos.cos_comm import CiDetectType

SECRET_ID = os.environ["SECRET_ID"]
SECRET_KEY = os.environ["SECRET_KEY"]
TRAVIS_FLAG = os.environ["TRAVIS_FLAG"]
REGION = os.environ["REGION"]
APPID = '1259698704'
test_bucket = 'debangpoc' + '-' + APPID
conf = CosConfig(
    Region=REGION,
    SecretId=SECRET_ID,
    SecretKey=SECRET_KEY,
)
client = CosS3Client(conf, retry=3)


def setUp():
    print ("start test...")
    print ("start create bucket " + test_bucket)
    _create_test_bucket(test_bucket)


def _create_test_bucket(test_bucket, create_region=None):
    try:
        if create_region is None:
            response = client.create_bucket(
                Bucket=test_bucket,
            )
        else:
            bucket_conf = CosConfig(
                Region=create_region,
                Secret_id=SECRET_ID,
                Secret_key=SECRET_KEY
            )
            bucket_client = CosS3Client(bucket_conf)
            response = bucket_client.create_bucket(
                Bucket=test_bucket,
            )
    except Exception as e:
        if e.get_error_code() == 'BucketAlreadyOwnedByYou':
            print('BucketAlreadyOwnedByYou')
        else:
            raise e
    return None

def test_live_channel():
    print ("create live channel...")
    livechannel_config = {
        'Description': 'cos python sdk test',
        'Switch': 'Enabled',
        'Target': {
            'Type': 'HLS',
            'FragDuration': '3',
            'FragCount': '5',
        }
    }

    for i in range(1, 5):
        channel_name = 'test-ch-' + str(i)
        try:
            response = client.put_live_channel(
                Bucket = test_bucket,
                ChannelName = channel_name,
                LiveChannelConfiguration = livechannel_config,
                Expire = 100000)
            assert(response)
            print(response)
        except Exception as e:
            if e.get_error_code() != 'ChannelStillLive':
                return

if __name__ == "__main__":
    setUp()
    test_live_channel()

