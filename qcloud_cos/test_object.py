# -*- coding=utf-8
import cos_client
import logging
import random
import sys
import os

reload(sys)
sys.setdefaultencoding('utf-8')
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(asctime)s - %(message)s")
access_id = "AKID15IsskiBQKTZbAo6WhgcBqVls9SmuG00"
access_key = "ciivKvnnrMvSvQpMAWuIz12pThGGlWRW"
file_id = str(random.randint(0, 1000)) + str(random.randint(0, 1000))
test_num = 10


def gen_file(path, size):
    file = open(path, 'w')
    file.seek(1024*1024*size)
    file.write('\x00')
    file.close()


def setUp():
    print "object interface test"
    print "config"
    conf = cos_client.CosConfig(
        appid="1252448703",
        bucket="lewzylu06",
        region="cn-north",
        access_id=access_id,
        access_key=access_key,
        part_size=1,
        max_thread=5
    )
    client = cos_client.CosS3Client(conf)
    global obj_int
    obj_int = client.obj_int()


def tearDown():
    print "test over"


def Test_object():
    for i in range(test_num):
        file_size = 3.1 * i + 0.1
        file_name = "tmp" + file_id + "_" + str(file_size) + "MB"
        print "Test upload " + file_name
        sys.stdout.flush()
        gen_file(file_name, file_size)
        global obj_int
        rt = obj_int.upload_file(file_name, file_name)
        assert rt
        print "Test put object acl " + file_name
        sys.stdout.flush()
        rt = obj_int.put_object_acl("anyone,1231,3210232098/345725437", None, "anyone", file_name)
        assert rt
        print "Test get object acl " + file_name
        sys.stdout.flush()
        rt = obj_int.get_object_acl(file_name)
        assert rt
        print "Test download " + file_name
        sys.stdout.flush()
        rt = obj_int.download_file(file_name, file_name)
        assert rt
        os.remove(file_name)
        print "Test delete " + file_name
        sys.stdout.flush()
        rt = obj_int.delete_file(file_name)
        assert rt


if __name__ == "__main__":
    setUp()
    Test_object()
