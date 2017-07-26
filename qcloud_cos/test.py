# -*- coding=utf-8
import cos_client
import logging
import random
import sys
import os

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(asctime)s - %(message)s")
file_id = str(random.randint(0, 1000)) + str(random.randint(0, 1000))
file_list = []
test_num = 20
ACCESS_ID = os.environ["ACCESS_ID"]
ACCESS_KEY = os.environ["ACCESS_KEY"]


def gen_file(path, size):
    _file = open(path, 'w')
    _file.seek(1024*1024*size)
    _file.write('\x00')
    _file.close()


def setUp():
    print "start test"


def tearDown():
    print "function teardown"


def Test():
    file_size = 3.1 + 0.1
    file_name = "tmp" + file_id + "_" + str(file_size) + "MB"
    headers = {'Content-Encoding': 'url'}
    print "Test put " + file_name
    sys.stdout.flush()
    conf = cos_client.CosConfig(
        Appid="1252448703",
        Region="cn-north",
        Access_id=ACCESS_ID,
        Access_key=ACCESS_KEY,
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
                         ContentType='string'
                         )
    assert rt.status_code == 200

    print "Test get " + file_name
    rt = client.get_object(Bucket='lewzylu06',
                           Key=file_name
                           )
    assert rt.status_code == 200

    print "Test delete " + file_name
    rt = client.delete_object(Bucket='lewzylu06',
                              Key=file_name,
                              )
    assert rt.status_code == 204

    conf = cos_client.CosConfig(
        Appid="1252448703",
        Region="cn-north",
        Access_id=ACCESS_ID,
        Access_key=ACCESS_KEY,
    )
    client = cos_client.CosS3Client(conf)
    print "Test create bucket"
    rt = client.create_bucket(Bucket='lewzylu999'
                              )
    assert rt.status_code == 200
    print "Test delete bucket"
    rt = client.delete_bucket(Bucket='lewzylu999'
                              )
    assert rt.status_code == 204

    print "Test list objects"
    rt = client.list_objects(
                            Bucket='lewzylu06',
                            Delimiter='string',
                            EncodingType='url',
                            Marker='string',
                            MaxKeys=123,
                            Prefix='string',
                            MaxKeys='1',
                            )
    print rt.status_code
    assert rt.status_code == 200


if __name__ == "__main__":
    setUp()
    Test()
