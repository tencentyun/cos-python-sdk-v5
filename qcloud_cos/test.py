# -*- coding=utf-8
from qcloud_cos import cos_client
import logging
import random
import sys
import os
import datetime
reload(sys)
sys.setdefaultencoding('utf-8')
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(asctime)s - %(message)s")
access_id = "AKID15IsskiBQKTZbAo6WhgcBqVls9SmuG00"
access_key = "ciivKvnnrMvSvQpMAWuIz12pThGGlWRW"
file_id = str(random.randint(0, 1000)) + str(random.randint(0, 1000))
file_list = []
test_num = 20


def gen_file(path, size):
    file = open(path, 'w')
    file.seek(1024*1024*size)
    file.write('\x00')
    file.close()


def setUp():
    print "config"
    conf = cos_client.CosConfig(
        appid="1252448703",
        region="cn-north",
        access_id=access_id,
        access_key=access_key,
    )
    client = cos_client.CosS3Client(conf)
    global obj_int
    obj_int = client.obj_int()
    
    conf = cos_client.CosConfig(
        appid="1252448703",
        region="cn-north",
        access_id=access_id,
        access_key=access_key,
    )
    client = cos_client.CosS3Client(conf)
    global buc_int
    buc_int = client.buc_int()

def tearDown():
    print "function teardown"


def Test():
    file_size = 3.1 + 0.1
    file_name = "tmp" + file_id + "_" + str(file_size) + "MB"
    headers = {
               'Content-Encoding':'url'}
    print "Test put " + file_name
    sys.stdout.flush()
    
    conf = cos_client.CosConfig(
        appid="1252448703",
        region="cn-north",
        access_id=access_id,
        access_key=access_key,
    )
    client = cos_client.CosS3Client(conf)
    obj_int = client.obj_int()
    rt = obj_int.put_object(
                         Bucket='lewzylu06',
                         Body='123'*1232, 
                         Key=file_name,
                         CacheControl='string',
                         ContentDisposition='string',
                         ContentEncoding='string',
                         ContentLanguage='string',
                         ContentType='string')
    assert rt.status_code==200
    
    print "Test get " + file_name
    rt = obj_int.get_object(Bucket='lewzylu06',
                            Key=file_name)
    assert rt.status_code==200
    
    print "Test delete " + file_name
    rt = obj_int.delete_object(
                                Bucket='lewzylu06',
                                Key=file_name,
                                )
    assert rt.status_code==204
    
    print "Test create bucket"
    rt = buc_int.create_bucket(
                                Bucket='lewzylu999'
                            )
    
    print "Test delete bucket"
    rt = buc_int.delete_bucket(
                                Bucket='lewzylu999',
                                MaxKeys = '1'
                                )
    assert rt.status_code==204
    rt = buc_int.list_objects(Bucket='lewzylu06')
    print rt.content
    print rt.status_code

if __name__ == "__main__":
    setUp()
    Test()
