Qcloud COSv5 SDK
#######################
    
介绍
_______

腾讯云COSV5Python SDK, 目前可以支持Python2.6与Python2.7。

安装指南
__________

使用pip安装 ::

    pip install -U qcloud_cos_v5


手动安装::

    python setup.py install

使用方法
__________

使用python sdk，参照https://github.com/tencentyun/cos-python-sdk-v5/blob/master/qcloud_cos/test.py

.. code:: python

    # 设置用户属性, 包括appid, secret_id和secret_key
    appid = 100000              # 替换为用户的appid
    secret_id = u'xxxxxxxx'     # 替换为用户的secret_id
    secret_key = u'xxxxxxx'     # 替换为用户的secret_key
    region = "cn-north"         # 替换为用户的region，目前可以为 cn-east/cn-south/cn-north/cn-southwest，分别对应于上海，广州，天津,西南园区
    config = CosConfig(Appid=appid, Region=region, Access_id=secret_id, Access_key=secret_key)  #获取配置对象
    client = CosS3Client(config)                                                                #获取客户端对象

    ############################################################################
    # 文件操作                                                                 #
    ############################################################################
    # 1. 上传单个文件
    response = client.put_object(
        Bucket='test01',
        Body='TY'*1024*512*file_size,
        Key=file_name,
        CacheControl='no-cache',
        ContentDisposition='download.txt'
    )

    # 2. 下载单个文件
    response = client.get_object(
        Bucket='test01',
        Key=file_name,
    )

    # 3. 获取文件属性
    response = client.head_object(
        Bucket='test01',
        Key=file_name
    )

    # 4. 删除单个文件
    response = client.delete_object(
        Bucket='test01',
        Key=file_name
    )

    # 5. 创建分片上传
    response = client.create_multipart_upload(
        Bucket='test01',
        Key='multipartfile.txt',
    )
    uploadid = get_id_from_xml(response.text)

    # 6. 删除分片上传
    response = client.abort_multipart_upload(
        Bucket='test01',
        Key='multipartfile.txt',
        UploadId=uploadid
    )

    # 7. 再次创建分片上传
    response = client.create_multipart_upload(
        Bucket='test01',
        Key='multipartfile.txt',
    )
    uploadid = response['UploadId']

    # 8. 上传分片
    response = client.upload_part(
        Bucket='test01',
        Key='multipartfile.txt',
        UploadId=uploadid,
        PartNumber=1,
        Body='A'*1024*1024*4
    )
    etag = response['ETag']

    # 9. 列出分片
    response = clieent.list_parts(
        Bucket='test01',
        Key='mutilpartfile.txt',
        UploadId=uploadid
    )
    lst = response['Part']

    # 10. 完成分片上传
    response = client.complete_multipart_upload(
        Bucket='test01',
        Key='multipartfile.txt',
        UploadId=uploadid,
        MultipartUpload={'Part': lst}
    )


    ############################################################################
    # Bucket操作                                                                 #
    ############################################################################
    # 1. 创建Bucket
    response = client.create_bucket(
        Bucket='test02',
        ACL='public-read'
    )   

    # 2. 删除Bucket
    response = client.delete_bucket(
        Bucket='test02'
    )

    # 3. 获取文件列表
    response = client.list_objects(
        Bucket='test01'
    )
