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
file_id = str(random.randint(0, 1000)) + str(random.randint(0, 1000))
file_list = []
test_num = 20


def gen_file(path, size):
    file = open(path, 'w')
    file.seek(1024*1024*size)
    file.write('\x00')
    file.close()


def setUp():
    print "start test"

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
        access_id=ACCESS_ID,
        access_key=ACCESS_KEY,
    )
    client = cos_client.CosS3Client(conf)
    rt = client.put_object(
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
    rt = client.get_object(Bucket='lewzylu06',
                            Key=file_name)
    assert rt.status_code==200
    
    print "Test delete " + file_name
    rt = client.delete_object(
                                Bucket='lewzylu06',
                                Key=file_name,
                                )
    assert rt.status_code==204
    
    
    
    conf = cos_client.CosConfig(
        appid="1252448703",
        region="cn-north",
        access_id=ACCESS_ID,
        access_key=ACCESS_KEY,
    )
    client = cos_client.CosS3Client(conf)
    print "Test create bucket"
    rt = client.create_bucket(
                                Bucket='lewzylu999'
                            )
    
    print "Test delete bucket"
    rt = client.delete_bucket(
                                Bucket='lewzylu999',
                                MaxKeys = '1'
                                )
    assert rt.status_code==204
    rt = client.list_objects(Bucket='lewzylu06')
    print rt.content
    print rt.status_code

if __name__ == "__main__":
    setUp()
    Test()

