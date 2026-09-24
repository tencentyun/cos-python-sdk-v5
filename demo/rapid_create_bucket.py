# -*- coding=utf-8
"""Create a Rapid bucket and read its current provisioning status.

Set COS_SECRET_ID, COS_SECRET_KEY, COS_REGION, COS_BUCKET, COS_VPC_ID,
COS_CIDR_BLOCK, COS_SUBNET_ID and COS_ZONE; COS_SECURITY_TOKEN is optional.
Success accepts the creation request. Object operations require Available.
"""
from __future__ import print_function

import os

from qcloud_cos import CosConfig, CosS3Client


def main():
    client = CosS3Client(CosConfig(
        Region=os.environ['COS_REGION'],
        SecretId=os.environ['COS_SECRET_ID'],
        SecretKey=os.environ['COS_SECRET_KEY'],
        Token=os.environ.get('COS_SECURITY_TOKEN'),
        Scheme='http', EnableRapidDomain=True))
    try:
        bucket = os.environ['COS_BUCKET']
        client.create_bucket(
            Bucket=bucket,
            VpcId=os.environ['COS_VPC_ID'],
            CidrBlock=os.environ['COS_CIDR_BLOCK'],
            SubnetId=os.environ['COS_SUBNET_ID'],
            Zone=os.environ['COS_ZONE'])
        result = client.head_bucket(Bucket=bucket)
        print('Creation request accepted; bucket status: %s' %
              result.get('x-cos-bucket-status', 'Unknown'))
        # Poll HeadBucket with a bounded timeout in your application. Only start
        # object operations after the server reports Available.
    finally:
        client._session.close()


if __name__ == '__main__':
    main()
