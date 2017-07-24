# -*- coding=utf-8
import cos_client
import logging
import random
import sys

reload(sys)
sys.setdefaultencoding('utf-8')
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(asctime)s - %(message)s")
access_id = "AKID15IsskiBQKTZbAo6WhgcBqVls9SmuG00"
access_key = "ciivKvnnrMvSvQpMAWuIz12pThGGlWRW"
test_num = 10


def setUp():
    print "Test bucket interface"


def tearDown():
    print "test over"


def Test_bucket():
    for i in range(test_num):
        bucket_id = str(random.randint(0, 1000)) + str(random.randint(0, 1000))
        conf = cos_client.CosConfig(
                    appid="1252448703",
                    bucket="test" + str(bucket_id),
                    region="cn-north",
                    access_id=access_id,
                    access_key=access_key,
                    part_size=1,
                    max_thread=5)
        client = cos_client.CosS3Client(conf)
        buc_int = client.buc_int()
        print "Test create bucket " + conf._bucket
        sys.stdout.flush()
        rt = buc_int.create_bucket()
        assert rt
        print "Test get bucket " + conf._bucket
        sys.stdout.flush()
        rt = buc_int.get_bucket()
        assert rt
        print "Test put bucket acl " + conf._bucket
        sys.stdout.flush()
        rt = buc_int.put_bucket_acl("anyone,1231,3210232098/345725437", None, "anyone")
        assert rt
        print "Test get bucket acl " + conf._bucket
        sys.stdout.flush()
        rt = buc_int.get_bucket_acl()
        assert rt
        print "Test delete bucket " + conf._bucket
        sys.stdout.flush()
        rt = buc_int.delete_bucket()
        assert rt


if __name__ == "__main__":
    setUp()
    Test_bucket()
