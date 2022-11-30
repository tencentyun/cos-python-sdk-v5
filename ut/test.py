# -*- coding=utf-8
import random
import sys
import time
import hashlib
import os
import requests
import json
import base64

from qcloud_cos import CosS3Client
from qcloud_cos import CosConfig
from qcloud_cos import CosServiceError
from qcloud_cos import get_date
from qcloud_cos.cos_encryption_client import CosEncryptionClient
from qcloud_cos.crypto import AESProvider
from qcloud_cos.crypto import RSAProvider
from qcloud_cos.cos_comm import CiDetectType, get_md5, to_bytes

SECRET_ID = os.environ["SECRET_ID"]
SECRET_KEY = os.environ["SECRET_KEY"]
TRAVIS_FLAG = os.environ["TRAVIS_FLAG"]
REGION = os.environ["REGION"]
APPID = '1251668577'
TEST_CI = os.environ["TEST_CI"]
USE_CREDENTIAL_INST = os.environ["USE_CREDENTIAL_INST"]
test_bucket = 'cos-python-v5-testbkt-' + str(sys.version_info[0]) + '-' + str(
    sys.version_info[1]) + '-' + REGION + '-' + APPID
copy_test_bucket = 'copy-' + test_bucket
test_object = "test.txt"
special_file_name = "中文" + "→↓←→↖↗↙↘! \"#$%&'()*+,-./0123456789:;<=>@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"

""" CredentialDemo """
class CredentialDemo:
    @property
    def secret_id(self):
        return SECRET_ID
    
    @property
    def secret_key(self):
        return SECRET_KEY
    
    @property
    def token(self):
        return ''

if USE_CREDENTIAL_INST == 'true':
    conf = CosConfig(
        Region=REGION,
        CredentialInstance=CredentialDemo()
    )
else:
    conf = CosConfig(
        Region=REGION,
        SecretId=SECRET_ID,
        SecretKey=SECRET_KEY,
    )

client = CosS3Client(conf, retry=3)
rsa_provider = RSAProvider()
client_for_rsa = CosEncryptionClient(conf, rsa_provider)
aes_provider = AESProvider()
client_for_aes = CosEncryptionClient(conf, aes_provider)

ci_bucket_name = 'ci-qta-gz-1251668577'
ci_region = 'ap-guangzhou'


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


def _upload_test_file(test_bucket, test_key):
    response = client.put_object(
        Bucket=test_bucket,
        Key=test_key,
        Body='test'
    )
    return None


def get_raw_md5(data):
    m2 = hashlib.md5(data)
    etag = '"' + str(m2.hexdigest()) + '"'
    return etag


def gen_file(path, size):
    _file = open(path, 'w')
    _file.seek(1024 * 1024 * size - 3)
    _file.write('cos')
    _file.close()


def print_error_msg(e):
    print(e.get_origin_msg())
    print(e.get_digest_msg())
    print(e.get_status_code())
    print(e.get_error_code())
    print(e.get_error_msg())
    print(e.get_resource_location())
    print(e.get_trace_id())
    print(e.get_request_id())


def percentage(consumed_bytes, total_bytes):
    """进度条回调函数，计算当前完成的百分比
    :param consumed_bytes: 已经上传/下载的数据量
    :param total_bytes: 总数据量
    """
    if total_bytes:
        rate = int(100 * (float(consumed_bytes) / float(total_bytes)))
        print('\r{0}% '.format(rate))
        sys.stdout.flush()


def setUp():
    print("start test...")
    print("start create bucket " + test_bucket)
    _create_test_bucket(test_bucket)
    _create_test_bucket(copy_test_bucket)
    _upload_test_file(copy_test_bucket, test_object)


def tearDown():
    print("function teardown")


def test_put_get_delete_object_10MB():
    """简单上传下载删除10MB小文件"""
    file_size = 10
    file_id = str(random.randint(0, 1000)) + str(random.randint(0, 1000))
    file_name = "tmp" + file_id + "_" + str(file_size) + "MB"
    gen_file(file_name, 1)
    with open(file_name, 'rb') as f:
        etag = get_raw_md5(f.read())
    try:
        # put object
        with open(file_name, 'rb') as fp:
            put_response = client.put_object(
                Bucket=test_bucket,
                Body=fp,
                Key=file_name,
                CacheControl='no-cache',
                ContentDisposition='download.txt'
            )
        assert etag == put_response['ETag']
        # head object
        head_response = client.head_object(
            Bucket=test_bucket,
            Key=file_name
        )
        assert etag == head_response['ETag']
        # get object
        get_response = client.get_object(
            Bucket=test_bucket,
            Key=file_name,
            ResponseCacheControl='private'
        )
        assert etag == get_response['ETag']
        assert 'private' == get_response['Cache-Control']
        download_fp = get_response['Body'].get_raw_stream()
        assert download_fp
        # delete object
        delete_response = client.delete_object(
            Bucket=test_bucket,
            Key=file_name
        )
    except CosServiceError as e:
        print_error_msg(e)
    if os.path.exists(file_name):
        os.remove(file_name)


def test_put_object_speacil_names():
    """特殊字符文件上传"""
    response = client.put_object(
        Bucket=test_bucket,
        Body='S' * 1024,
        Key=special_file_name,
        CacheControl='no-cache',
        ContentDisposition='download.txt'
    )
    assert response


def test_get_object_special_names():
    """特殊字符文件下载"""
    response = client.get_object(
        Bucket=test_bucket,
        Key=special_file_name
    )
    assert response


def test_delete_object_special_names():
    """特殊字符文件删除"""
    response = client.delete_object(
        Bucket=test_bucket,
        Key=special_file_name
    )


def test_put_object_non_exist_bucket():
    """文件上传至不存在bucket"""
    try:
        response = client.put_object(
            Bucket='test0xx-' + APPID,
            Body='T' * 10,
            Key=test_object,
            CacheControl='no-cache',
            ContentDisposition='download.txt'
        )
    except CosServiceError as e:
        print_error_msg(e)


def test_put_object_acl():
    """设置object acl"""
    response = client.put_object(
        Bucket=test_bucket,
        Key=test_object,
        Body='test acl'
    )
    response = client.put_object_acl(
        Bucket=test_bucket,
        Key=test_object,
        ACL='public-read'
    )


def test_get_object_acl():
    """获取object acl"""
    response = client.get_object_acl(
        Bucket=test_bucket,
        Key=test_object
    )
    assert response
    response = client.delete_object(
        Bucket=test_bucket,
        Key=test_object
    )


def test_copy_object_diff_bucket():
    """从另外的bucket拷贝object"""
    copy_source = {'Bucket': copy_test_bucket, 'Key': 'test.txt', 'Region': REGION}
    response = client.copy_object(
        Bucket=test_bucket,
        Key='test.txt',
        CopySource=copy_source
    )
    assert response


def test_create_abort_multipart_upload():
    """创建一个分块上传，然后终止它"""
    # create
    response = client.create_multipart_upload(
        Bucket=test_bucket,
        Key='multipartfile.txt',
    )
    assert response
    uploadid = response['UploadId']
    # abort
    response = client.abort_multipart_upload(
        Bucket=test_bucket,
        Key='multipartfile.txt',
        UploadId=uploadid
    )


def test_create_complete_multipart_upload():
    """创建一个分块上传，上传分块，列出分块，完成分块上传"""
    # create
    response = client.create_multipart_upload(
        Bucket=test_bucket,
        Key='multipartfile.txt',
    )
    uploadid = response['UploadId']
    # upload part
    response = client.upload_part(
        Bucket=test_bucket,
        Key='multipartfile.txt',
        UploadId=uploadid,
        PartNumber=1,
        Body='A' * 1024 * 1024 * 2
    )

    response = client.upload_part(
        Bucket=test_bucket,
        Key='multipartfile.txt',
        UploadId=uploadid,
        PartNumber=2,
        Body='B' * 1024 * 1024 * 2
    )
    # list parts
    response = client.list_parts(
        Bucket=test_bucket,
        Key='multipartfile.txt',
        UploadId=uploadid
    )
    lst = response['Part']
    # complete
    response = client.complete_multipart_upload(
        Bucket=test_bucket,
        Key='multipartfile.txt',
        UploadId=uploadid,
        MultipartUpload={'Part': lst}
    )


def test_upload_part_copy():
    """创建一个分块上传，上传分块拷贝，列出分块，完成分块上传"""
    # create
    response = client.create_multipart_upload(
        Bucket=test_bucket,
        Key='multipartfile.txt',
    )
    uploadid = response['UploadId']
    # upload part
    response = client.upload_part(
        Bucket=test_bucket,
        Key='multipartfile.txt',
        UploadId=uploadid,
        PartNumber=1,
        Body='A' * 1024 * 1024 * 2
    )

    response = client.upload_part(
        Bucket=test_bucket,
        Key='multipartfile.txt',
        UploadId=uploadid,
        PartNumber=2,
        Body='B' * 1024 * 1024 * 2
    )

    # upload part copy
    copy_source = {'Bucket': copy_test_bucket, 'Key': 'test.txt', 'Region': REGION}
    response = client.upload_part_copy(
        Bucket=test_bucket,
        Key='multipartfile.txt',
        UploadId=uploadid,
        PartNumber=3,
        CopySource=copy_source
    )
    # list parts
    response = client.list_parts(
        Bucket=test_bucket,
        Key='multipartfile.txt',
        UploadId=uploadid
    )
    lst = response['Part']
    # complete
    response = client.complete_multipart_upload(
        Bucket=test_bucket,
        Key='multipartfile.txt',
        UploadId=uploadid,
        MultipartUpload={'Part': lst}
    )


def test_delete_multiple_objects():
    """批量删除文件"""
    file_id = str(random.randint(0, 1000)) + str(random.randint(0, 1000))
    file_name1 = "tmp" + file_id + "_delete1"
    file_name2 = "tmp" + file_id + "_delete2"
    response1 = client.put_object(
        Bucket=test_bucket,
        Key=file_name1,
        Body='A' * 1024 * 1024
    )
    assert response1
    response2 = client.put_object(
        Bucket=test_bucket,
        Key=file_name2,
        Body='B' * 1024 * 1024 * 2
    )
    assert response2
    objects = {
        "Quiet": "true",
        "Object": [
            {
                "Key": file_name1
            },
            {
                "Key": file_name2
            }
        ]
    }
    response = client.delete_objects(
        Bucket=test_bucket,
        Delete=objects
    )


def test_create_head_delete_bucket():
    """创建一个bucket,head它是否存在,最后删除一个空bucket"""
    bucket_id = str(random.randint(0, 1000)) + str(random.randint(0, 1000))
    bucket_name = 'buckettest' + bucket_id + '-' + APPID
    response = client.create_bucket(
        Bucket=bucket_name,
        ACL='public-read'
    )
    response = client.head_bucket(
        Bucket=bucket_name
    )
    response = client.delete_bucket(
        Bucket=bucket_name
    )

def test_create_head_delete_maz_bucket():
    """创建一个多AZ bucket,head它是否存在,最后删除一个空bucket"""
    bucket_id = str(random.randint(0, 1000)) + str(random.randint(0, 1000))
    bucket_name = 'buckettest-maz' + bucket_id + '-' + APPID
    response = client.create_bucket(
        Bucket=bucket_name,
        BucketAZConfig='MAZ',
        ACL='public-read'
    )
    response = client.head_bucket(
        Bucket=bucket_name
    )
    response = client.delete_bucket(
        Bucket=bucket_name
    )

def test_put_bucket_acl_illegal():
    """设置非法的ACL"""
    try:
        response = client.put_bucket_acl(
            Bucket=test_bucket,
            ACL='public-read-writ'
        )
    except CosServiceError as e:
        print_error_msg(e)


def test_get_bucket_acl_normal():
    """正常获取bucket ACL"""
    response = client.get_bucket_acl(
        Bucket=test_bucket
    )
    assert response


def test_list_objects():
    """列出bucket下的objects"""
    response = client.list_objects(
        Bucket=test_bucket,
        MaxKeys=100,
        Prefix='中文',
        Delimiter='/'
    )
    assert response


def test_list_objects_versions():
    """列出bucket下的带版本信息的objects"""
    response = client.list_objects_versions(
        Bucket=test_bucket,
        MaxKeys=50
    )
    assert response


def test_get_presigned_url():
    """生成预签名的url下载地址"""
    url = client.get_presigned_download_url(
        Bucket=test_bucket,
        Key='中文.txt'
    )
    assert url
    print(url)


def test_get_bucket_location():
    """获取bucket的地域信息"""
    response = client.get_bucket_location(
        Bucket=test_bucket
    )
    assert response['LocationConstraint'] == REGION


def test_get_service():
    return  # TODO: 测试账号的桶太多了导致列举超时，暂时屏蔽掉

    """列出账号下所有的bucket信息"""
    response = client.list_buckets()
    assert response


def test_put_get_delete_cors():
    """设置、获取、删除跨域配置"""
    cors_config = {
        'CORSRule': [
            {
                'ID': '1234',
                'AllowedOrigin': ['http://www.qq.com'],
                'AllowedMethod': ['GET', 'PUT'],
                'AllowedHeader': ['x-cos-meta-test'],
                'ExposeHeader': ['x-cos-meta-test1'],
                'MaxAgeSeconds': 500
            }
        ]
    }
    # put cors
    response = client.put_bucket_cors(
        Bucket=test_bucket,
        CORSConfiguration=cors_config
    )
    # wait for sync
    # get cors
    time.sleep(4)
    response = client.get_bucket_cors(
        Bucket=test_bucket
    )
    assert response
    # delete cors
    response = client.delete_bucket_cors(
        Bucket=test_bucket
    )


def test_put_get_delete_lifecycle():
    """设置、获取、删除生命周期配置"""
    lifecycle_config = {
        'Rule': [
            {
                'Status': 'Enabled',
                'Filter': {
                    # 作用于带标签键 datalevel 和值 backup 的标签的对象
                    'Tag': [
                        {
                            'Key': 'datalevel',
                            'Value': 'backup'
                        }
                    ]
                },
                'Transation': [
                    {
                        # 30天后转换为Standard_IA
                        'Days': 30,
                        'StorageClass': 'Standard_IA'
                    }
                ],
                'Expiration': {
                    # 3650天后过期删除
                    'Days': 3650
                }
            }
        ]
    }
    try:
        # put lifecycle
        response = client.put_bucket_lifecycle(
            Bucket=test_bucket,
            LifecycleConfiguration=lifecycle_config
        )
        # wait for sync
        # get lifecycle
        time.sleep(4)
        response = client.get_bucket_lifecycle(
            Bucket=test_bucket
        )
        assert response
        # delete lifecycle
        response = client.delete_bucket_lifecycle(
            Bucket=test_bucket
        )
    except CosServiceError as e:
        if e.get_status_code() < 500:
            raise e


def test_put_get_versioning():
    """设置、获取版本控制"""
    # put versioning
    response = client.put_bucket_versioning(
        Bucket=test_bucket,
        Status='Enabled'
    )
    # wait for sync
    # get versioning
    time.sleep(4)
    response = client.get_bucket_versioning(
        Bucket=test_bucket
    )
    assert response['Status'] == 'Enabled'


def test_put_get_delete_replication():
    """设置、获取、删除跨园区复制配置"""
    replic_dest_bucket = 'replicationsh-' + APPID
    _create_test_bucket(replic_dest_bucket, 'ap-shanghai')
    sh_conf = CosConfig(
        Region='ap-shanghai',
        Secret_id=SECRET_ID,
        Secret_key=SECRET_KEY
    )
    sh_client = CosS3Client(sh_conf)
    response = sh_client.put_bucket_versioning(
        Bucket=replic_dest_bucket,
        Status='Enabled'
    )
    replication_config = {
        'Role': 'qcs::cam::uin/2779643970:uin/2779643970',
        'Rule': [
            {
                'ID': '123',
                'Status': 'Enabled',
                'Prefix': '中文',
                'Destination': {
                    'Bucket': 'qcs::cos:ap-shanghai::' + replic_dest_bucket,
                    'StorageClass': 'Standard'
                }
            }
        ]
    }
    # source dest bucket must enable versioning
    # put replication
    response = client.put_bucket_replication(
        Bucket=test_bucket,
        ReplicationConfiguration=replication_config
    )
    # wait for sync
    # get replication
    time.sleep(4)
    response = client.get_bucket_replication(
        Bucket=test_bucket
    )
    assert response
    # delete replication
    response = client.delete_bucket_replication(
        Bucket=test_bucket
    )


def test_put_get_delete_website():
    """设置、获取、删除静态网站配置"""
    website_config = {
        'IndexDocument': {
            'Suffix': 'index.html'
        },
        'ErrorDocument': {
            'Key': 'error.html'
        },
        'RoutingRules': [
            {
                'Condition': {
                    'HttpErrorCodeReturnedEquals': '404',
                },
                'Redirect': {
                    'ReplaceKeyWith': '404.html',
                }
            },
            {
                'Condition': {
                    'KeyPrefixEquals': 'aaa/'
                },
                'Redirect': {
                    'ReplaceKeyPrefixWith': 'ccc/'
                }
            }
        ]
    }
    response = client.put_bucket_website(
        Bucket=test_bucket,
        WebsiteConfiguration=website_config
    )
    # wait for sync
    # get website
    time.sleep(4)
    response = client.get_bucket_website(
        Bucket=test_bucket
    )
    assert website_config == response
    # delete website
    response = client.delete_bucket_website(
        Bucket=test_bucket
    )


def test_list_multipart_uploads():
    """获取所有正在进行的分块上传"""
    response = client.list_multipart_uploads(
        Bucket=test_bucket,
        Prefix="multipart",
        MaxUploads=100
    )
    # abort make sure delete all uploads
    if 'Upload' in response.keys():
        for data in response['Upload']:
            response = client.abort_multipart_upload(
                Bucket=test_bucket,
                Key=data['Key'],
                UploadId=data['UploadId']
            )
    # create a new upload
    response = client.create_multipart_upload(
        Bucket=test_bucket,
        Key='multipartfile.txt',
    )
    assert response
    uploadid = response['UploadId']
    # list again
    response = client.list_multipart_uploads(
        Bucket=test_bucket,
        Prefix="multipart",
        MaxUploads=100
    )
    assert response['Upload'][0]['Key'] == "multipartfile.txt"
    assert response['Upload'][0]['UploadId'] == uploadid
    # abort again make sure delete all uploads
    for data in response['Upload']:
        response = client.abort_multipart_upload(
            Bucket=test_bucket,
            Key=data['Key'],
            UploadId=data['UploadId']
        )


def test_upload_file_from_buffer():
    import io
    data = io.BytesIO(6 * 1024 * 1024 * b'A')
    response = client.upload_file_from_buffer(
        Bucket=test_bucket,
        Key='test_upload_from_buffer',
        Body=data,
        MaxBufferSize=5,
        PartSize=1
    )


def test_upload_file_multithreading():
    """根据文件大小自动选择分块大小,多线程并发上传提高上传速度"""
    file_name = "thread_1GB"
    file_size = 128
    if TRAVIS_FLAG == 'true':
        file_size = 5  # set 5MB beacuse travis too slow
    gen_file(file_name, file_size)
    st = time.time()  # 记录开始时间
    response = client.upload_file(
        Bucket=test_bucket,
        Key=file_name,
        LocalFilePath=file_name,
        MAXThread=5,
        EnableMD5=True
    )
    ed = time.time()  # 记录结束时间
    if os.path.exists(file_name):
        os.remove(file_name)
    print(ed - st)


def test_upload_file_with_progress_callback():
    """带有进度条功能的并发上传"""
    file_name = "test_progress_callback"
    file_size = 128
    if TRAVIS_FLAG == 'true':
        file_size = 5  # set 5MB beacuse travis too slow
    gen_file(file_name, file_size)
    response = client.upload_file(
        Bucket=test_bucket,
        Key=file_name,
        LocalFilePath=file_name,
        MAXThread=5,
        EnableMD5=True,
        progress_callback=percentage
    )
    if os.path.exists(file_name):
        os.remove(file_name)


def test_copy_file_automatically():
    """根据拷贝源文件的大小自动选择拷贝策略，不同园区,小于5G直接copy_object，大于5G分块拷贝"""
    copy_source = {'Bucket': copy_test_bucket, 'Key': 'test.txt', 'Region': REGION}
    response = client.copy(
        Bucket=test_bucket,
        Key='copy.txt',
        CopySource=copy_source,
        MAXThread=10
    )


def test_upload_empty_file():
    """上传一个空文件,不能返回411错误"""
    file_name = "empty.txt"
    with open(file_name, 'wb') as f:
        pass
    with open(file_name, 'rb') as fp:
        response = client.put_object(
            Bucket=test_bucket,
            Body=fp,
            Key=file_name,
            CacheControl='no-cache',
            ContentDisposition='download.txt'
        )


def test_use_get_auth():
    """测试利用get_auth方法直接生产签名,然后访问COS"""
    auth = client.get_auth(
        Method='GET',
        Bucket=test_bucket,
        Key='test.txt',
        Params={'acl': '', 'unsed': '123'}
    )
    if conf._enable_old_domain:
        url = 'http://' + test_bucket + '.cos.' + REGION + '.myqcloud.com/test.txt?acl&unsed=123'
    else:
        url = 'http://' + test_bucket + '.cos.' + REGION + '.tencentcos.cn/test.txt?acl&unsed=123'
    response = requests.get(url, headers={'Authorization': auth})
    assert response.status_code == 200


def test_upload_with_server_side_encryption():
    """上传带上加密头部,下载时验证有该头部"""
    response = client.put_object(
        Bucket=test_bucket,
        Key=test_object,
        Body='123',
        ServerSideEncryption='AES256'
    )
    assert response['x-cos-server-side-encryption'] == 'AES256'

    response = client.get_object(
        Bucket=test_bucket,
        Key=test_object
    )
    assert response['x-cos-server-side-encryption'] == 'AES256'


def test_put_get_bucket_logging():
    """测试bucket的logging服务"""
    logging_bucket = 'logging-beijing-' + APPID
    _create_test_bucket(logging_bucket, 'ap-beijing')
    logging_config = {
        'LoggingEnabled': {
            'TargetBucket': logging_bucket,
            'TargetPrefix': 'test'
        }
    }
    beijing_conf = CosConfig(
        Region='ap-beijing',
        Secret_id=SECRET_ID,
        Secret_key=SECRET_KEY
    )
    logging_client = CosS3Client(beijing_conf)
    response = logging_client.put_bucket_logging(
        Bucket=logging_bucket,
        BucketLoggingStatus=logging_config
    )
    time.sleep(4)
    response = logging_client.get_bucket_logging(
        Bucket=logging_bucket
    )
    print(response)
    assert response['LoggingEnabled']['TargetBucket'] == logging_bucket
    assert response['LoggingEnabled']['TargetPrefix'] == 'test'


def test_put_object_enable_md5():
    """上传文件,SDK计算content-md5头部"""
    file_name = 'test_object_sdk_caculate_md5.file'
    gen_file(file_name, 1)
    with open(file_name, 'rb') as f:
        etag = get_raw_md5(f.read())
    with open(file_name, 'rb') as fp:
        # fp验证
        put_response = client.put_object(
            Bucket=test_bucket,
            Body=fp,
            Key=file_name,
            EnableMD5=True,
            CacheControl='no-cache',
            ContentDisposition='download.txt'
        )
        assert etag == put_response['ETag']
        put_response = client.put_object(
            Bucket=test_bucket,
            Body='TestMD5',
            Key=file_name,
            EnableMD5=True,
            CacheControl='no-cache',
            ContentDisposition='download.txt'
        )
        assert put_response
    if os.path.exists(file_name):
        os.remove(file_name)


def test_put_object_from_local_file():
    """通过本地文件路径来上传文件"""
    file_size = 1
    file_id = str(random.randint(0, 1000)) + str(random.randint(0, 1000))
    file_name = "tmp" + file_id + "_" + str(file_size) + "MB"
    gen_file(file_name, file_size)
    with open(file_name, 'rb') as f:
        etag = get_raw_md5(f.read())
    put_response = client.put_object_from_local_file(
        Bucket=test_bucket,
        LocalFilePath=file_name,
        Key=file_name
    )
    assert put_response['ETag'] == etag
    response = client.delete_object(
        Bucket=test_bucket,
        Key=file_name
    )
    if os.path.exists(file_name):
        os.remove(file_name)


def test_object_exists():
    """测试一个文件是否存在"""
    status = client.object_exists(
        Bucket=test_bucket,
        Key=test_object
    )
    assert status is True


def test_bucket_exists():
    """测试一个bucket是否存在"""
    status = client.bucket_exists(
        Bucket=test_bucket
    )
    assert status is True


def test_put_get_delete_bucket_policy():
    """设置获取删除bucket的policy配置"""
    resource = "qcs::cos:" + REGION + ":uid/" + APPID + ":" + test_bucket + "/*"
    resource_list = [resource]
    policy = {
        "Statement": [
            {
                "Principal": {
                    "qcs": [
                        "qcs::cam::anyone:anyone"
                    ]
                },
                "Action": [
                    "name/cos:GetObject",
                    "name/cos:HeadObject"
                ],
                "Effect": "allow",
                "Resource": resource_list
            }
        ],
        "Version": "2.0"
    }
    response = client.put_bucket_policy(
        Bucket=test_bucket,
        Policy=policy
    )
    response = client.get_bucket_policy(
        Bucket=test_bucket,
    )
    response = client.delete_bucket_policy(
        Bucket=test_bucket,
    )


def test_put_file_like_object():
    """利用BytesIo来模拟文件上传"""
    import io
    input = io.BytesIO(b"123456")
    rt = client.put_object(
        Bucket=test_bucket,
        Key='test_file_like_object',
        Body=input,
        EnableMD5=True
    )
    assert rt


def test_put_chunked_object():
    """支持网络流来支持chunk上传"""
    import requests
    input = requests.get(client.get_presigned_download_url(test_bucket, test_object))
    rt = client.put_object(
        Bucket=test_bucket,
        Key='test_chunked_object',
        Body=input
    )
    assert rt


def test_put_get_gzip_file():
    """上传文件时,带上ContentEncoding,下载时默认不解压"""
    rt = client.put_object(
        Bucket=test_bucket,
        Key='test_gzip_file',
        Body='123456',
        ContentEncoding='gzip',
    )
    rt = client.get_object(
        Bucket=test_bucket,
        Key='test_gzip_file'
    )
    rt['Body'].get_stream_to_file('test_gzip_file.local')


def test_put_get_delete_bucket_domain():
    """测试设置获取删除bucket自定义域名"""
    domain = 'tiedu-gz.coshelper.com'
    if TRAVIS_FLAG == 'true':
        domain = 'tiedu-ger.coshelper.com'
    domain_config = {
        'DomainRule': [
            {
                'Name': domain,
                'Type': 'REST',
                'Status': 'ENABLED',
            },
        ]
    }

    response = client.delete_bucket_domain(
        Bucket=test_bucket
    )

    time.sleep(2)
    response = client.put_bucket_domain(
        Bucket=test_bucket,
        DomainConfiguration=domain_config
    )
    # wait for sync
    # get domain
    time.sleep(4)
    response = client.get_bucket_domain(
        Bucket=test_bucket
    )
    assert domain_config["DomainRule"] == response["DomainRule"]
    # test domain request
    """
    domain_conf = CosConfig(
        SecretId=SECRET_ID,
        SecretKey=SECRET_KEY,
        Domain=domain,
        Scheme='http'
    )
    domain_client = CosS3Client(domain_conf)
    response = domain_client.head_bucket(
        Bucket=test_bucket
    )
    """
    # delete domain
    response = client.delete_bucket_domain(
        Bucket=test_bucket
    )

def test_put_get_delete_bucket_domain_certificate():
    """测试设置获取删除bucket自定义域名证书"""

    """
    存储桶 bj-1259654469 专门用于测试自定义域名证书
    """

    temp_bucket = 'bj-1259654469'
    temp_conf = CosConfig(
        Region='ap-beijing',
        SecretId=SECRET_ID,
        SecretKey=SECRET_KEY
    )
    temp_client = CosS3Client(
        conf=temp_conf,
        retry=3
    )

    domain = 'testcertificate.coshelper.com'
    domain_config = {
        'DomainRule': [
            {
                'Name': domain,
                'Type': 'REST',
                'Status': 'ENABLED',
            },
        ]
    }

    # put domain
    response = temp_client.put_bucket_domain(
        Bucket=temp_bucket,
        DomainConfiguration=domain_config
    ) 

    with open('./testcertificate.coshelper.com.key', 'rb') as f:
        key = f.read().decode('utf-8')
    with open('./testcertificate.coshelper.com.pem', 'rb') as f:
        cert = f.read().decode('utf-8')

    domain_cert_config = {
        'CertificateInfo': {
            'CertType': 'CustomCert',
            'CustomCert': {
                'Cert': cert,
                'PrivateKey': key,
            },
        },
        'DomainList': [
            {
                'DomainName': domain
            },
        ],
    }

    # put domain certificate
    response = temp_client.delete_bucket_domain_certificate(
        Bucket=temp_bucket,
        DomainName=domain
    )

    time.sleep(2)
    response = temp_client.put_bucket_domain_certificate(
        Bucket=temp_bucket,
        DomainCertificateConfiguration=domain_cert_config
    )
    # wait for sync
    # get domain certificate
    time.sleep(4)
    response = temp_client.get_bucket_domain_certificate(
        Bucket=temp_bucket,
        DomainName=domain
    )
    assert response["Status"] == "Enabled"

    # delete domain certificate
    response = temp_client.delete_bucket_domain_certificate(
        Bucket=temp_bucket,
        DomainName=domain
    )

    # delete domain
    response = temp_client.delete_bucket_domain(
        Bucket=temp_bucket,
    )

def test_put_get_delete_bucket_inventory():
    """测试设置获取删除bucket清单"""
    inventory_config = {
        'Destination': {
            'COSBucketDestination': {
                'AccountId': '2779643970',
                'Bucket': 'qcs::cos:' + REGION + '::' + test_bucket,
                'Format': 'CSV',
                'Prefix': 'list1',
                'Encryption': {
                    'SSECOS': {}
                }
            }
        },
        'IsEnabled': 'True',
        'Filter': {
            'Prefix': 'filterPrefix'
        },
        'IncludedObjectVersions': 'All',
        'OptionalFields': {
            'Field': [
                'Size',
                'LastModifiedDate',
                'ETag',
                'StorageClass',
                'IsMultipartUploaded',
                'ReplicationStatus'
            ]
        },
        'Schedule': {
            'Frequency': 'Daily'
        }
    }
    response = client.put_bucket_inventory(
        Bucket=test_bucket,
        Id='test',
        InventoryConfiguration=inventory_config
    )
    # wait for sync
    # get inventory
    time.sleep(4)
    response = client.get_bucket_inventory(
        Bucket=test_bucket,
        Id='test'
    )
    # delete inventory
    response = client.delete_bucket_inventory(
        Bucket=test_bucket,
        Id='test'
    )


def test_put_get_delete_bucket_tagging():
    """测试设置获取删除bucket标签"""
    tagging_config = {
        'TagSet': {
            'Tag': [
                {
                    'Key': 'key0',
                    'Value': 'value0'
                }
            ]
        }
    }
    response = client.put_bucket_tagging(
        Bucket=test_bucket,
        Tagging=tagging_config
    )
    # wait for sync
    # get tagging
    time.sleep(1)
    response = client.get_bucket_tagging(
        Bucket=test_bucket
    )
    assert tagging_config == response
    # delete tagging
    response = client.delete_bucket_tagging(
        Bucket=test_bucket
    )


def test_put_get_delete_object_tagging():
    """测试设置获取删除object标签"""
    tagging_config = {
        'TagSet': {
            'Tag': [
                {
                    'Key': 'key0',
                    'Value': 'value0'
                }
            ]
        }
    }
    response = client.put_object_tagging(
        Bucket=test_bucket,
        Key=test_object,
        Tagging=tagging_config
    )
    # wait for sync
    # get tagging
    time.sleep(1)
    response = client.get_object_tagging(
        Bucket=test_bucket,
        Key=test_object
    )
    assert tagging_config == response
    # delete tagging
    response = client.delete_object_tagging(
        Bucket=test_bucket,
        Key=test_object
    )


def _test_put_get_delete_bucket_origin():
    """测试设置获取删除bucket回源域名"""
    origin_config = {}
    response = client.put_bucket_origin(
        Bucket=test_bucket,
        OriginConfiguration=origin_config
    )
    # wait for sync
    # get origin
    time.sleep(4)
    response = client.get_bucket_origin(
        Bucket=test_bucket
    )
    # delete origin
    response = client.delete_bucket_origin(
        Bucket=test_bucket
    )


def test_put_get_delete_bucket_referer():
    """测试设置获取删除bucket防盗链规则"""
    referer_config = {
        'Status': 'Enabled',
        'RefererType': 'White-List',
        'EmptyReferConfiguration': 'Allow',
        'DomainList': {
            'Domain': [
                '*.qq.com',
                '*.qcloud.com'
            ]
        }
    }
    response = client.put_bucket_referer(
        Bucket=test_bucket,
        RefererConfiguration=referer_config
    )
    time.sleep(4)
    response = client.get_bucket_referer(
        Bucket=test_bucket,
    )
    response = client.delete_bucket_referer(
        Bucket=test_bucket,
    )
    time.sleep(4)
    response = client.get_bucket_referer(
        Bucket=test_bucket,
    )
    assert len(response) == 0


def test_put_get_traffic_limit():
    """测试上传下载接口的单链接限速"""
    traffic_test_key = 'traffic_test'
    response = client.put_object(
        Bucket=test_bucket,
        Key=traffic_test_key,
        Body='A' * 1024 * 1024,
        TrafficLimit='1048576'
    )
    # 限速的单位为bit/s 1048576bit/s代表1Mb/s
    response = client.get_object(
        Bucket=test_bucket,
        Key=traffic_test_key,
        TrafficLimit='1048576'
    )


def test_select_object():
    """测试SQL检索COS对象(只支持国内)"""
    select_obj = "select_test.json"
    json_body = {
        'name': 'cos',
        'age': '999'
    }
    conf = CosConfig(
        Region='ap-guangzhou',
        SecretId=SECRET_ID,
        SecretKey=SECRET_KEY,
    )
    test_bucket = 'test-select-' + APPID
    _create_test_bucket(test_bucket, 'ap-guangzhou')
    client = CosS3Client(conf)
    response = client.put_object(
        Bucket=test_bucket,
        Key=select_obj,
        Body=(json.dumps(json_body) + '\n') * 100
    )
    response = client.select_object_content(
        Bucket=test_bucket,
        Key=select_obj,
        Expression='Select * from COSObject',
        ExpressionType='SQL',
        InputSerialization={
            'CompressionType': 'NONE',
            'JSON': {
                'Type': 'LINES'
            }
        },
        OutputSerialization={
            'CSV': {
                'RecordDelimiter': '\n'
            }
        }
    )
    event_stream = response['Payload']
    for event in event_stream:
        print(event)


def _test_get_object_sensitive_content_recognition():
    """测试ci文件内容识别的接口"""
    print(CiDetectType)
    response = client.get_object_sensitive_content_recognition(
        Bucket=test_bucket,
        Key=test_object,
        Interval=3,
        MaxFrames=20,
        # BizType='xxxx',
        DetectType=(CiDetectType.PORN | CiDetectType.TERRORIST | CiDetectType.POLITICS | CiDetectType.ADS)
    )
    print(response)
    assert response


def test_download_file():
    """测试断点续传下载接口"""
    # 测试普通下载
    client.download_file(copy_test_bucket, test_object, 'test_download_file.local')
    if os.path.exists('test_download_file.local'):
        os.remove('test_download_file.local')

    # 测试限速下载
    client.download_file(copy_test_bucket, test_object, 'test_download_traffic_limit.local', TrafficLimit='819200')
    if os.path.exists('test_download_traffic_limit.local'):
        os.remove('test_download_traffic_limit.local')

    # 测试crc64校验开关
    client.download_file(copy_test_bucket, test_object, 'test_download_crc.local', EnableCRC=True)
    if os.path.exists('test_download_crc.local'):
        os.remove('test_download_crc.local')

    # 测试源文件的md5与下载下来后的文件md5
    file_size = 25  # MB
    file_id = str(random.randint(0, 1000)) + str(random.randint(0, 1000))
    file_name = "tmp" + file_id + "_" + str(file_size) + "MB"
    gen_file(file_name, file_size)

    source_file_md5 = None
    dest_file_md5 = None
    with open(file_name, 'rb') as f:
        source_file_md5 = get_raw_md5(f.read())

    client.put_object_from_local_file(
        Bucket=copy_test_bucket,
        LocalFilePath=file_name,
        Key=file_name
    )

    client.download_file(copy_test_bucket, file_name, 'test_download_md5.local')
    if os.path.exists('test_download_md5.local'):
        with open('test_download_md5.local', 'rb') as f:
            dest_file_md5 = get_raw_md5(f.read())
    assert source_file_md5 and dest_file_md5 and source_file_md5 == dest_file_md5

    # 释放资源
    client.delete_object(
        Bucket=copy_test_bucket,
        Key=file_name
    )
    if os.path.exists(file_name):
        os.remove(file_name)


def _test_put_get_bucket_intelligenttiering():
    """测试设置获取智能分层"""
    intelligent_tiering_conf = {
                'Status': 'Enabled',
                'Transition': {
                    'Days': '30',
                    'RequestFrequent': '1'
                }
            }
    response = client.put_bucket_intelligenttiering(
        Bucket=test_bucket,
        IntelligentTieringConfiguration=intelligent_tiering_conf
    )
    time.sleep(2)
    response = client.get_bucket_intelligenttiering(
        Bucket=test_bucket,
    )


def test_bucket_encryption():
    """测试存储桶默认加密配置"""
    # 测试设置存储桶的默认加密配置
    config_dict = {
        'Rule': [
            {
                'ApplySideEncryptionConfiguration': {
                    'SSEAlgorithm': 'AES256',
                }
            },
        ]
    }
    client.put_bucket_encryption(test_bucket, config_dict)

    # 测试获取存储桶默认加密配置
    ret = client.get_bucket_encryption(test_bucket)
    sse_algorithm = ret['Rule'][0]['ApplyServerSideEncryptionByDefault']['SSEAlgorithm']
    assert (sse_algorithm == 'AES256')

    # 删除存储桶默认加密配置
    client.delete_bucket_encryption(test_bucket)


def test_aes_client():
    """测试aes加密客户端的上传下载操作"""
    content = '123456' * 1024 + '1'
    client_for_aes.delete_object(test_bucket, 'test_for_aes')
    client_for_aes.put_object(test_bucket, content, 'test_for_aes')
    # 测试整个文件的md5
    response = client_for_aes.get_object(test_bucket, 'test_for_aes')
    response['Body'].get_stream_to_file('test_for_aes_local')
    local_file_md5 = None
    content_md5 = None
    with open('test_for_aes_local', 'rb') as f:
        local_file_md5 = get_raw_md5(f.read())
    content_md5 = get_raw_md5(content.encode("utf-8"))
    assert local_file_md5 and content_md5 and local_file_md5 == content_md5
    if os.path.exists('test_for_aes_local'):
        os.remove('test_for_aes_local')

    # 测试读取部分数据的md5
    response = client_for_aes.get_object(test_bucket, 'test_for_aes', Range='bytes=5-3000')
    response['Body'].get_stream_to_file('test_for_aes_local')
    with open('test_for_aes_local', 'rb') as f:
        local_file_md5 = get_raw_md5(f.read())
    content_md5 = get_raw_md5(content[5:3001].encode("utf-8"))
    assert local_file_md5 and content_md5 and local_file_md5 == content_md5
    if os.path.exists('test_for_aes_local'):
        os.remove('test_for_aes_local')

    client_for_aes.delete_object(test_bucket, 'test_for_aes')

    content = '1' * 1024 * 1024
    # 测试分片上传
    client_for_rsa.delete_object(test_bucket, 'test_multi_upload')
    response = client_for_aes.create_multipart_upload(test_bucket, 'test_multi_upload')
    uploadid = response['UploadId']
    client_for_aes.upload_part(test_bucket, 'test_multi_upload', content, 1, uploadid)
    client_for_aes.upload_part(test_bucket, 'test_multi_upload', content, 2, uploadid)
    response = client_for_aes.list_parts(test_bucket, 'test_multi_upload', uploadid)
    client_for_aes.complete_multipart_upload(test_bucket, 'test_multi_upload', uploadid, {'Part': response['Part']})
    response = client_for_aes.get_object(test_bucket, 'test_multi_upload')
    response['Body'].get_stream_to_file('test_multi_upload_local')
    with open('test_multi_upload_local', 'rb') as f:
        local_file_md5 = get_raw_md5(f.read())
    content_md5 = get_raw_md5((content + content).encode("utf-8"))
    assert local_file_md5 and content_md5 and local_file_md5 == content_md5
    if os.path.exists('test_multi_upload_local'):
        os.remove('test_multi_upload_local')

    client_for_rsa.delete_object(test_bucket, 'test_multi_upload')


def test_rsa_client():
    """测试rsa加密客户端的上传下载操作"""
    content = '123456' * 1024 + '1'
    client_for_rsa.delete_object(test_bucket, 'test_for_rsa')
    client_for_rsa.put_object(test_bucket, content, 'test_for_rsa')
    # 测试整个文件的md5
    response = client_for_rsa.get_object(test_bucket, 'test_for_rsa')
    response['Body'].get_stream_to_file('test_for_rsa_local')
    local_file_md5 = None
    content_md5 = None
    with open('test_for_rsa_local', 'rb') as f:
        local_file_md5 = get_raw_md5(f.read())
    content_md5 = get_raw_md5(content.encode("utf-8"))
    assert local_file_md5 and content_md5 and local_file_md5 == content_md5
    if os.path.exists('test_for_rsa_local'):
        os.remove('test_for_rsa_local')

    # 测试读取部分数据的md5
    response = client_for_rsa.get_object(test_bucket, 'test_for_rsa', Range='bytes=5-3000')
    response['Body'].get_stream_to_file('test_for_rsa_local')
    with open('test_for_rsa_local', 'rb') as f:
        local_file_md5 = get_raw_md5(f.read())
    content_md5 = get_raw_md5(content[5:3001].encode("utf-8"))
    assert local_file_md5 and content_md5 and local_file_md5 == content_md5
    if os.path.exists('test_for_rsa_local'):
        os.remove('test_for_rsa_local')

    client_for_rsa.delete_object(test_bucket, 'test_for_rsa')

    content = '1' * 1024 * 1024
    # 测试分片上传
    client_for_rsa.delete_object(test_bucket, 'test_multi_upload')
    response = client_for_rsa.create_multipart_upload(test_bucket, 'test_multi_upload')
    uploadid = response['UploadId']
    client_for_rsa.upload_part(test_bucket, 'test_multi_upload', content, 1, uploadid)
    client_for_rsa.upload_part(test_bucket, 'test_multi_upload', content, 2, uploadid)
    response = client_for_rsa.list_parts(test_bucket, 'test_multi_upload', uploadid)
    client_for_rsa.complete_multipart_upload(test_bucket, 'test_multi_upload', uploadid, {'Part': response['Part']})
    response = client_for_rsa.get_object(test_bucket, 'test_multi_upload')
    response['Body'].get_stream_to_file('test_multi_upload_local')
    with open('test_multi_upload_local', 'rb') as f:
        local_file_md5 = get_raw_md5(f.read())
    content_md5 = get_raw_md5((content + content).encode("utf-8"))
    assert local_file_md5 and content_md5 and local_file_md5 == content_md5
    if os.path.exists('test_multi_upload_local'):
        os.remove('test_multi_upload_local')

    client_for_rsa.delete_object(test_bucket, 'test_multi_upload')


def test_live_channel():
    if TEST_CI != 'true':
        return
    """测试rtmp推流功能"""
    livechannel_config = {
        'Description': 'cos python sdk test',
        'Switch': 'Enabled',
        'Target': {
            'Type': 'HLS',
            'FragDuration': '3',
            'FragCount': '5',
        }
    }
    channel_name = 'cos-python-sdk-uttest-ch1'

    try:
        response = client.put_live_channel(
            Bucket=test_bucket,
            ChannelName=channel_name,
            LiveChannelConfiguration=livechannel_config)
        assert (response)
    except Exception as e:
        if e.get_error_code() != 'ChannelStillLive':
            return

    print("get live channel info...")
    response = client.get_live_channel_info(
        Bucket=test_bucket,
        ChannelName=channel_name)
    print(response)
    assert (response['Switch'] == 'Enabled')
    assert (response['Description'] == 'cos python sdk test')
    assert (response['Target']['Type'] == 'HLS')
    assert (response['Target']['FragDuration'] == '3')
    assert (response['Target']['FragCount'] == '5')
    assert (response['Target']['PlaylistName'] == 'playlist.m3u8')

    print("put live channel switch...")
    client.put_live_channel_switch(
        Bucket=test_bucket,
        ChannelName=channel_name,
        Switch='disabled')
    response = client.get_live_channel_info(
        Bucket=test_bucket,
        ChannelName=channel_name)
    assert (response['Switch'] == 'Disabled')
    client.put_live_channel_switch(
        Bucket=test_bucket,
        ChannelName=channel_name,
        Switch='enabled')
    response = client.get_live_channel_info(
        Bucket=test_bucket,
        ChannelName=channel_name)
    assert (response['Switch'] == 'Enabled')

    print("get live channel history...")
    response = client.get_live_channel_history(
        Bucket=test_bucket,
        ChannelName=channel_name)
    print(response)

    print("get live channel status...")
    response = client.get_live_channel_status(
        Bucket=test_bucket,
        ChannelName=channel_name)
    print(response)
    assert (response['Status'] == 'Idle' or response['Status'] == 'Live')

    print("list channel...")
    create_chan_num = 20
    for i in range(1, create_chan_num):
        ch_name = 'test-list-channel-' + str(i)
        client.put_live_channel(
            Bucket=test_bucket,
            ChannelName=ch_name,
            LiveChannelConfiguration=livechannel_config)
    response = client.list_live_channel(Bucket=test_bucket, MaxKeys=10)
    print(response)
    assert (response['MaxKeys'] == '10')
    assert (response['IsTruncated'] == 'true')
    response = client.list_live_channel(Bucket=test_bucket, MaxKeys=5, Marker=response['NextMarker'])
    print(response)
    assert (response['MaxKeys'] == '5')
    assert (response['IsTruncated'] == 'true')

    for i in range(1, create_chan_num):
        ch_name = 'test-list-channel-' + str(i)
        client.delete_live_channel(Bucket=test_bucket, ChannelName=ch_name)

    print("post vod playlist")
    '''playlist不以.m3u8结尾'''
    try:
        client.post_vod_playlist(
            Bucket=test_bucket,
            ChannelName=channel_name,
            PlaylistName='test',
            StartTime=int(time.time()) - 10000,
            EndTime=int(time.time()))
    except Exception as e:
        pass

    '''starttime大于endtimne'''
    try:
        client.post_vod_playlist(
            Bucket=test_bucket,
            ChannelName=channel_name,
            PlaylistName='test.m3u8',
            StartTime=10,
            EndTime=9)
    except Exception as e:
        pass

    client.post_vod_playlist(
        Bucket=test_bucket,
        ChannelName=channel_name,
        PlaylistName='test.m3u8',
        StartTime=int(time.time()) - 10000,
        EndTime=int(time.time()))
    response = client.head_object(
        Bucket=test_bucket,
        Key=channel_name + '/test.m3u8')
    assert (response)

    print("delete live channel...")
    response = client.delete_live_channel(Bucket=test_bucket, ChannelName=channel_name)
    assert (response)


def test_get_object_url():
    """测试获取对象访问URL"""
    response = client.get_object_url(
        Bucket=test_bucket,
        Key='test.txt'
    )
    print(response)


def _test_qrcode():
    """二维码图片上传时识别"""
    file_name = 'test_object_sdk_qrcode.file'
    with open(file_name, 'rb') as fp:
        # fp验证
        opts = '{"is_pic_info":1,"rules":[{"fileid":"format.jpg","rule":"QRcode/cover/1"}]}'
        response, data = client.ci_put_object_from_local_file_and_get_qrcode(
            Bucket=test_bucket,
            LocalFilePath=file_name,
            Key=file_name,
            EnableMD5=False,
            PicOperations=opts
        )
        print(response, data)

    """二维码图片下载时识别"""
    response, data = client.ci_get_object_qrcode(
        Bucket=test_bucket,
        Key=file_name,
        Cover=0
    )
    print(response, data)


def test_ci_put_image_style():
    if TEST_CI != 'true':
        return

    """增加图片样式接口"""
    body = {
        'StyleName': 'style_name',
        'StyleBody': 'imageMogr2/thumbnail/!50px',
    }
    response = client.ci_put_image_style(
        Bucket=test_bucket,
        Request=body,
    )
    print(response)


def test_ci_get_image_style():
    if TEST_CI != 'true':
        return

    """获取图片样式接口"""
    body = {
        'StyleName': 'style_name',
    }
    response, data = client.ci_get_image_style(
        Bucket=test_bucket,
        Request=body,
    )
    print(response['x-cos-request-id'])
    print(data)


def test_ci_get_image_info():
    if TEST_CI != 'true':
        return

    """ci获取图片基本信息接口"""
    response, data = client.ci_get_image_info(
        Bucket=test_bucket,
        Key='format.png',
    )
    print(response['x-cos-request-id'])
    print(data)


def test_ci_get_image_exif_info():
    if TEST_CI != 'true':
        return

    """获取图片exif信息接口"""
    response, data = client.ci_get_image_exif_info(
        Bucket=test_bucket,
        Key='format.png',
    )
    print(response['x-cos-request-id'])
    print(data)


def test_ci_get_image_ave_info():
    if TEST_CI != 'true':
        return

    """获取图片主色调接口"""
    response, data = client.ci_get_image_info(
        Bucket=test_bucket,
        Key='format.png',
    )
    print(response['x-cos-request-id'])
    print(data)


def test_ci_image_assess_quality():
    if TEST_CI != 'true':
        return

    """图片质量评估接口"""
    response = client.ci_image_assess_quality(
        Bucket=test_bucket,
        Key='format.png',
    )
    print(response)


def test_ci_qrcode_generate():
    if TEST_CI != 'true':
        return

    """二维码生成接口"""
    response = client.ci_qrcode_generate(
        Bucket=test_bucket,
        QrcodeContent='https://www.example.com',
        Width=200
    )
    qrCodeImage = base64.b64decode(response['ResultImage'])
    with open('/result.png', 'wb') as f:
        f.write(qrCodeImage)
    print(response)


def test_ci_ocr_process():
    if TEST_CI != 'true':
        return

    """通用文字识别"""
    response = client.ci_ocr_process(
        Bucket=test_bucket,
        Key='ocr.jpeg',
    )
    print(response)


def test_ci_get_media_queue():
    if TEST_CI != 'true':
        return

    # 查询媒体队列信息
    response = client.ci_get_media_queue(
                    Bucket=ci_bucket_name,
                    State="Active",
                )
    print(response)
    assert (response['QueueList'])


def test_ci_get_media_pic_queue():
    if TEST_CI != 'true':
        return

    # 查询图片处理队列信息
    response = client.ci_get_media_pic_queue(
        Bucket=ci_bucket_name,
        State="Active",
    )
    print(response)
    assert (response['QueueList'])


def test_ci_create_media_transcode_watermark_jobs():
    if TEST_CI != 'true':
        return

    # 创建转码任务
    response = client.ci_get_media_queue(
                    Bucket=ci_bucket_name,
                    State="Active",
    )
    QueueId = response['QueueList'][0]['QueueId']

    body = {
        'Input': {
            'Object': 'workflow/input/video/test1.mp4'
        },
        'QueueId': QueueId,
        'Tag': 'Transcode',
        'Operation': {
            'Output': {
                'Bucket': ci_bucket_name,
                'Region': ci_region,
                'Object': '117374C_output.mp4'
            },
            'TemplateId': 't02db40900dc1c43ad9bdbd8acec6075c5',
            # "WatermarkTemplateId": ["", ""],
            'Watermark': [
                {
                    'Type': 'Text',
                    'Pos': 'TopRight',
                    'LocMode': 'Absolute',
                    'Dx': '64',
                    'Dy': '64',
                    'StartTime': '0',
                    'EndTime': '1000.5',
                    'Text': {
                        'Text': '水印内容',
                        'FontSize': '90',
                        'FontType': 'simfang.ttf',
                        'FontColor': '0xFFEEFF',
                        'Transparency': '100',
                    },
                },
                {
                    'Type': 'Image',
                    'Pos': 'TopLeft',
                    'LocMode': 'Absolute',
                    'Dx': '100',
                    'Dy': '100',
                    'StartTime': '0',
                    'EndTime': '1000.5',
                    'Image': {
                        'Url': 'http://'+ci_bucket_name+".cos."+ci_region+".tencentcos.cn/1215shuiyin.jpg",
                        'Mode': 'Fixed',
                        'Width': '128',
                        'Height': '128',
                        'Transparency': '100',
                    },
                }
            ]
        }
    }
    # dict中数组类型的标签，都需要特殊处理
    lst = [
        '<Watermark>',
        '<WatermarkTemplateId>',
        '</WatermarkTemplateId>',
        '</Watermark>'
    ]
    response = client.ci_create_media_jobs(
                    Bucket=ci_bucket_name,
                    Jobs=body,
                    Lst=lst,
                    ContentType='application/xml'
                )
    print(response)
    assert (response['JobsDetail'])


def test_ci_create_media_transcode_jobs():
    if TEST_CI != 'true':
        return

    # 创建转码任务
    response = client.ci_get_media_queue(
                    Bucket=ci_bucket_name,
                    State="Active",
    )
    QueueId = response['QueueList'][0]['QueueId']
    body = {
        'Input': {
            'Object': 'workflow/input/video/test1.mp4'
        },
        'QueueId': QueueId,
        'Tag': 'Transcode',
        'Operation': {
            'Output': {
                'Bucket': ci_bucket_name,
                'Region': ci_region,
                'Object': '117374C_output.mp4'
            },
            'TemplateId': 't02db40900dc1c43ad9bdbd8acec6075c5'
        }
    }
    response = client.ci_create_media_jobs(
                    Bucket=ci_bucket_name,
                    Jobs=body,
                    Lst={},
                    ContentType='application/xml'
                )
    print(response)
    assert (response['JobsDetail'])


def test_ci_create_media_pic_jobs():
    if TEST_CI != 'true':
        return

    response = client.ci_get_media_pic_queue(
        Bucket=ci_bucket_name,
        State="Active",
    )
    QueueId = response['QueueList'][0]['QueueId']
    # 创建图片处理任务
    body = {
        'Input': {
            'Object': '1.png'
        },
        'QueueId': QueueId,
        'Tag': 'PicProcess',
        'Operation': {
            "PicProcess": {
                "IsPicInfo": "true",
                "ProcessRule": "imageMogr2/rotate/90",
            },
            'Output': {
                'Bucket': ci_bucket_name,
                'Region': ci_region,
                'Object': 'pic-process-result.png'
            },
        }
    }
    response = client.ci_create_media_pic_jobs(
        Bucket=ci_bucket_name,
        Jobs=body,
        Lst={},
        ContentType='application/xml'
    )
    print(response)
    assert (response['JobsDetail'])


def test_ci_list_media_pic_jobs():
    if TEST_CI != 'true':
        return

    # 图片处理任务列表
    response = client.ci_get_media_pic_queue(
        Bucket=ci_bucket_name,
        State="Active",
    )
    QueueId = response['QueueList'][0]['QueueId']

    response = client.ci_list_media_pic_jobs(
        Bucket=ci_bucket_name,
        QueueId=QueueId,
        Tag='PicProcess',
        ContentType='application/xml',
        States='Success'
    )
    print(response)
    assert (response['JobsDetail'])


def test_ci_list_media_transcode_jobs():
    if TEST_CI != 'true':
        return

    # 转码任务
    response = client.ci_get_media_queue(
                    Bucket=ci_bucket_name,
                    State="Active",
    )
    QueueId = response['QueueList'][0]['QueueId']
    response = client.ci_list_media_jobs(
                    Bucket=ci_bucket_name,
                    QueueId=QueueId,
                    Tag='Transcode',
                    Size=2,
                    ContentType='application/xml'
                )
    print(response)
    assert (response['JobsDetail'])


def test_get_media_info():
    if TEST_CI != 'true':
        return
    # 获取媒体信息
    response = client.get_media_info(
        Bucket=ci_bucket_name,
        Key='workflow/input/video/test1.mp4'
    )
    print(response)
    assert (response)


def test_get_snapshot():
    if TEST_CI != 'true':
        return
    # 产生同步截图
    response = client.get_snapshot(
        Bucket=ci_bucket_name,
        Key='workflow/input/video/test1.mp4',
        Time='1.5',
        Width='480',
        Format='png'
    )
    print(response)
    assert (response)


def test_get_pm3u8():
    if TEST_CI != 'true':
        return
    # 获取私有 M3U8 ts 资源的下载授权
    response = client.get_pm3u8(
        Bucket=ci_bucket_name,
        Key='/data/media/m3u8_no_end.m3u8',
        Expires='3600'
    )
    print(response)
    assert (response)


def test_ci_get_media_bucket():
    if TEST_CI != 'true':
        return
    # 获取私有 M3U8 ts 资源的下载授权
    response = client.ci_get_media_bucket(
        Regions=ci_region,
        BucketNames=ci_bucket_name,
        BucketName=ci_bucket_name,
        PageNumber='1',
        PageSize='2'
    )
    print(response)
    assert (response)


def test_ci_create_doc_transcode_jobs():
    if TEST_CI != 'true':
        return
    response = client.ci_get_doc_queue(
                    Bucket=ci_bucket_name
                )
    print(response)
    assert (response['QueueList'][0]['QueueId'])
    queueId = response['QueueList'][0]['QueueId']
    response = client.ci_create_doc_job(
                    Bucket=ci_bucket_name,
                    QueueId=queueId,
                    InputObject='normal.pptx',
                    OutputBucket=ci_bucket_name,
                    OutputRegion='ap-guangzhou',
                    OutputObject='/test_doc/normal/abc_${Number}.jpg',
                    # DocPassword='123',
                    Quality=109,
                    PageRanges='1,3',
                )
    print(response)
    assert (response['JobsDetail']['JobId'])

    # 测试转码查询任务
    JobID = response['JobsDetail']['JobId']
    response = client.ci_get_doc_job(
                    Bucket=ci_bucket_name,
                    JobID=JobID,
                )
    print(response)
    assert (response['JobsDetail'])


def test_ci_list_doc_transcode_jobs():
    if TEST_CI != 'true':
        return
    # 查询任务列表
    response = client.ci_get_doc_queue(
                    Bucket=ci_bucket_name
                )
    print(response)
    assert (response['QueueList'][0]['QueueId'])
    queueId = response['QueueList'][0]['QueueId']
    response = client.ci_list_doc_jobs(
                    Bucket=ci_bucket_name,
                    QueueId=queueId,
                    Size=10,
                )
    print(response)
    assert (response['JobsDetail'])


def test_ci_live_video_auditing():
    if TEST_CI != 'true':
        return
    # 提交视频流审核任务
    response = client.ci_auditing_live_video_submit(
                    Bucket=ci_bucket_name,
                    Url='rtmp://example.com/live/123',
                    Callback='http://callback.com/',
                    DataId='testdataid-111111',
                    UserInfo={
                        'TokenId': 'token',
                        'Nickname': 'test',
                        'DeviceId': 'DeviceId-test',
                        'AppId': 'AppId-test',
                        'Room': 'Room-test',
                        'IP': 'IP-test',
                        'Type': 'Type-test',
                    },
                    BizType="44f32597a627d013962c54d459a9ab6e",
                )
    assert (response['JobsDetail']['JobId'])
    jobId = response['JobsDetail']['JobId']
    time.sleep(5)
    response = client.ci_auditing_live_video_cancle(
                    Bucket=ci_bucket_name,
                    JobID=jobId,
                )
    print(response)
    assert (response['JobsDetail'])


def test_sse_c_file():
    """测试SSE-C的各种接口"""
    bucket = test_bucket
    ssec_key = base64.standard_b64encode(to_bytes('01234567890123456789012345678901'))
    ssec_key_md5 = get_md5('01234567890123456789012345678901')
    file_name = 'sdk-sse-c'

    # 测试普通上传
    response = client.put_object(Bucket=bucket, Key=file_name, Body="00000",
                                 SSECustomerAlgorithm='AES256', SSECustomerKey=ssec_key, SSECustomerKeyMD5=ssec_key_md5)
    print(response)
    assert(response['x-cos-server-side-encryption-customer-algorithm'] == 'AES256')

    # 测试普通下载
    response = client.get_object(Bucket=bucket, Key=file_name,
                                 SSECustomerAlgorithm='AES256', SSECustomerKey=ssec_key, SSECustomerKeyMD5=ssec_key_md5)
    print(response)
    assert(response['x-cos-server-side-encryption-customer-algorithm'] == 'AES256')

    # 测试小文件高级下载
    response = client.download_file(Bucket=bucket, Key=file_name, DestFilePath='sdk-sse-c.local',
                                    SSECustomerAlgorithm='AES256', SSECustomerKey=ssec_key, SSECustomerKeyMD5=ssec_key_md5)
    print(response)
    if not os.path.exists('sdk-sse-c.local'):
        assert False
    else:
        os.remove('sdk-sse-c.local')

    # 测试普通拷贝
    # 故意构造源和目标的密钥不同
    dest_ssec_key = base64.standard_b64encode(to_bytes('01234567890123456789012345678902'))
    dest_ssec_key_md5 = get_md5('01234567890123456789012345678902')
    copy_source = {'Bucket': bucket, 'Key': file_name, 'Region': REGION}
    response = client.copy_object(
        Bucket=bucket, Key='sdk-sse-c-copy', CopySource=copy_source,
        SSECustomerAlgorithm='AES256', SSECustomerKey=dest_ssec_key, SSECustomerKeyMD5=dest_ssec_key_md5,
        CopySourceSSECustomerAlgorithm='AES256', CopySourceSSECustomerKey=ssec_key, CopySourceSSECustomerKeyMD5=ssec_key_md5
    )
    assert(response['x-cos-server-side-encryption-customer-algorithm'] == 'AES256')

    # 测试高级拷贝
    response = client.copy(Bucket=bucket, Key='sdk-sse-c-copy', CopySource=copy_source, MAXThread=2,
                           SSECustomerAlgorithm='AES256', SSECustomerKey=dest_ssec_key, SSECustomerKeyMD5=dest_ssec_key_md5,
                           CopySourceSSECustomerAlgorithm='AES256', CopySourceSSECustomerKey=ssec_key, CopySourceSSECustomerKeyMD5=ssec_key_md5)
    assert(response['x-cos-server-side-encryption-customer-algorithm'] == 'AES256')

    # 测试取回
    response = client.put_object(Bucket=bucket, Key=file_name, Body="00000",
                                 SSECustomerAlgorithm='AES256', SSECustomerKey=ssec_key, SSECustomerKeyMD5=ssec_key_md5, StorageClass='ARCHIVE')
    response = client.restore_object(Bucket=bucket, Key=file_name, RestoreRequest={
        'Days': 1,
        'CASJobParameters': {
            'Tier': 'Expedited'
        }
    }, SSECustomerAlgorithm='AES256', SSECustomerKey=ssec_key, SSECustomerKeyMD5=ssec_key_md5)

    # 测试大文件高级上传，走多段
    gen_file('sdk-sse-c-big.local', 21)

    file_name = 'sdk-sse-c-big'
    response = client.upload_file(Bucket=bucket, Key=file_name, LocalFilePath="sdk-sse-c-big.local",
                                  SSECustomerAlgorithm='AES256', SSECustomerKey=ssec_key, SSECustomerKeyMD5=ssec_key_md5)
    print(response)
    assert(response['x-cos-server-side-encryption-customer-algorithm'] == 'AES256')
    os.remove('sdk-sse-c-big.local')

    # 测试大文件高级下载，走多段
    response = client.download_file(Bucket=bucket, Key=file_name, DestFilePath='sdk-sse-c-1.local',
                                    SSECustomerAlgorithm='AES256', SSECustomerKey=ssec_key, SSECustomerKeyMD5=ssec_key_md5, EnableCRC=True)
    print(response)
    if not os.path.exists('sdk-sse-c-1.local'):
        assert False
    else:
        os.remove('sdk-sse-c-1.local')

    # 测试大文件高级拷贝，走拷贝段
    copy_source = {'Bucket': bucket, 'Key': file_name, 'Region': REGION}
    conf.set_copy_part_threshold_size(20 * 1024 * 1024)
    response = client.copy(Bucket=bucket, Key='sdk-sse-c-big-copy', CopySource=copy_source, MAXThread=2,
                           SSECustomerAlgorithm='AES256', SSECustomerKey=dest_ssec_key, SSECustomerKeyMD5=dest_ssec_key_md5, StorageClass='STANDARD_IA',
                           CopySourceSSECustomerAlgorithm='AES256', CopySourceSSECustomerKey=ssec_key, CopySourceSSECustomerKeyMD5=ssec_key_md5)
    assert(response['x-cos-server-side-encryption-customer-algorithm'] == 'AES256')


if __name__ == "__main__":
    setUp()
    """
    test_put_get_delete_object_10MB()
    test_put_object_speacil_names()
    test_get_object_special_names()
    test_delete_object_special_names()
    test_put_object_non_exist_bucket()
    test_put_object_acl()
    test_get_object_acl()
    test_copy_object_diff_bucket()
    test_create_abort_multipart_upload()
    test_create_complete_multipart_upload()
    test_upload_part_copy()
    test_delete_multiple_objects()
    test_create_head_delete_bucket()
    test_create_head_delete_maz_bucket()
    test_put_bucket_acl_illegal()
    test_get_bucket_acl_normal()
    test_list_objects()
    test_list_objects_versions()
    test_get_presigned_url()
    test_get_bucket_location()
    test_get_service()
    test_put_get_delete_cors()
    test_put_get_delete_lifecycle()
    test_put_get_versioning()
    test_put_get_delete_replication()
    test_put_get_delete_website()
    test_list_multipart_uploads()
    test_upload_file_from_buffer()
    test_upload_file_multithreading()
    test_upload_file_with_progress_callback()
    test_copy_file_automatically()
    test_upload_empty_file()
    test_use_get_auth()
    test_upload_with_server_side_encryption()
    test_put_get_bucket_logging()
    test_put_object_enable_md5()
    test_put_object_from_local_file()
    test_object_exists()
    test_bucket_exists()
    test_put_get_delete_bucket_policy()
    test_put_file_like_object()
    test_put_chunked_object()
    test_put_get_gzip_file()
    test_put_get_delete_bucket_domain()
    test_put_get_delete_bucket_domain_certificate()
    test_put_get_delete_bucket_inventory()
    test_put_get_delete_bucket_tagging()
    test_put_get_delete_object_tagging()
    test_put_get_delete_bucket_referer()
    test_put_get_traffic_limit()
    test_select_object()
    test_download_file()
    test_bucket_encryption()
    test_aes_client()
    test_rsa_client()
    test_live_channel()
    test_get_object_url()
    test_ci_put_image_style()
    test_ci_get_image_style()
    test_ci_get_image_info()
    test_ci_get_image_exif_info()
    test_ci_get_image_ave_info()
    test_ci_image_assess_quality()
    test_ci_qrcode_generate()
    test_ci_ocr_process()
    test_ci_get_media_queue()
    test_ci_get_media_pic_queue()
    test_ci_create_media_transcode_watermark_jobs()
    test_ci_create_media_transcode_jobs()
    test_ci_create_media_pic_jobs()
    test_ci_list_media_pic_jobs()
    test_ci_list_media_transcode_jobs()
    test_get_media_info()
    test_get_snapshot()
    test_get_pm3u8()
    test_ci_get_media_bucket()
    test_ci_create_doc_transcode_jobs()
    test_ci_list_doc_transcode_jobs()
    test_ci_live_video_auditing()
    test_sse_c_file()
    """
    tearDown()
