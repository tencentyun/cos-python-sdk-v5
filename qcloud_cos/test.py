import cos_client
import random
import sys
import os
import xml.dom.minidom
from xml.dom.minidom import parse
from cos_client import CosS3Client
from cos_client import CosConfig

ACCESS_ID = os.environ["ACCESS_ID"]
ACCESS_KEY = os.environ["ACCESS_KEY"]

def gen_file(path, size):
    _file = open(path, 'w')
    _file.seek(1024*1024*size)
    _file.write('cos')
    _file.close()

def get_id_from_xml(data):
    tree = xml.dom.minidom.parseString(data)
    root = tree.documentElement
    result = root.getElementsByTagName('UploadId')
    # use childNodes to get a list, if has no child get itself
    return result[0].childNodes[0].nodeValue

def setUp():
    print "start test"

def tearDown():
    print "function teardown"


def Test():
    conf = CosConfig(
        Appid="1252448703",
        Region="cn-north",
        Access_id=ACCESS_ID,
        Access_key=ACCESS_KEY
    )
    client = cos_client.CosS3Client(conf)

    file_size = 2
    file_id = str(random.randint(0, 1000)) + str(random.randint(0, 1000))
    file_name = "tmp" + file_id + "_" + str(file_size) + "MB"

    print "Test Put Object " + file_name
    response = client.put_object(
        Bucket='test01',
        Body='TY'*1024*512*file_size,
        Key=file_name,
        CacheControl = 'no-cache',
        ContentDisposition = 'download.txt',
        ACL = 'public-read'
    )
    assert response.status_code == 200

    print "Test Get Object " + file_name
    response = client.get_object(
        Bucket='test01',
        Key=file_name,
    )
    assert response.status_code == 200

    print "Test Head Object " + file_name
    response = client.head_object(
        Bucket='test01',
        Key=file_name
    )
    assert response.status_code == 200

    print "Test Delete Object " + file_name
    response = client.delete_object(
        Bucket='test01',
        Key=file_name
    )
    assert response.status_code == 204

    print "Test List Objects"
    response = client.list_objects(
        Bucket='test01'
    )
    assert response.status_code == 200

    print "Test Create Bucket"
    response = client.create_bucket(
        Bucket='test02',
        ACL = 'public-read'
    )
    assert response.status_code == 200

    print "Test Delete Bucket"
    response = client.delete_bucket(
        Bucket='test02'
    )
    assert response.status_code == 204

    print "Test Create MultipartUpload"
    response = client.create_multipart_upload(
        Bucket='test01',
        Key = 'multipartfile.txt',    
    )
    assert response.status_code == 200
    uploadid = get_id_from_xml(response.text)

    
    print "Test Abort MultipartUpload"
    response = client.abort_multipart_upload(
        Bucket='test01',
        Key = 'multipartfile.txt',
        UploadId = uploadid
    )
    assert response.status_code == 200
    
    print "Test Create MultipartUpload"
    response = client.create_multipart_upload(
        Bucket='test01',
        Key = 'multipartfile.txt',    
    )
    uploadid = get_id_from_xml(response.text)
    assert response.status_code == 200
    
    print "Test Upload Part"
    response = client.upload_part(
        Bucket='test01',
        Key = 'multipartfile.txt',
        UploadId = uploadid,
        PartNumber = 1,
        Body = 'A'*1024*1024*4
    )
    etag = response.headers['ETag']
    assert response.status_code == 200
    
    print "Test Complete MultipartUpload"
    response = client.complete_multipart_upload(
        Bucket='test01',
        Key = 'multipartfile.txt',
        UploadId = uploadid,
        MultipartUpload = {'Parts':[{'PartNumber':1, 'ETag':etag}]}
    )
    assert response.status_code == 200

if __name__ == "__main__":
    setUp()
    Test()
