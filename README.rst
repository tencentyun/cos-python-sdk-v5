Qcloud COSv5 SDK
#######################
    
介绍
_______

腾讯云COSV5Python SDK, 目前可以支持Python2.6与Python2.7。

安装指南
__________

使用pip安装 ::

    pip install -U cos-python-sdk-v5

手动安装::

    python setup.py install

使用方法
__________

使用python sdk，参照https://github.com/tencentyun/cos-python-sdk-v5/blob/master/qcloud_cos/demo.py

cos最新可用地域,参照https://www.qcloud.com/document/product/436/6224

.. code:: python

    # 设置用户属性, 包括secret_id, secret_key, region
    # appid已在配置中移除,请在参数Bucket中带上appid。Bucket由bucketname-appid组成
    secret_id = 'xxxxxxxx'     # 替换为用户的secret_id
    secret_key = 'xxxxxxx'     # 替换为用户的secret_key
    region = 'ap-beijing-1'    # 替换为用户的region 
    token = ''                 # 使用临时秘钥需要传入Token，默认为空,可不填
    config = CosConfig(Region=region, Secret_id=secret_id, Secret_key=secret_key, Token=token)  #获取配置对象
    client = CosS3Client(config)                                                                #获取客户端对象


    ############################################################################
    # 文件操作                                                                 #
    ############################################################################
    # 1. 上传单个文件
    response = client.put_object(
        Bucket='test01-123456789',  # Bucket由bucketname-appid组成
        Body='TY'*1024*512*file_size,
        Key=file_name,
        CacheControl='no-cache',
        ContentDisposition='download.txt'
    )

    # 2. 下载单个文件
    response = client.get_object(
        Bucket='test01-123456789',
        Key=file_name,
    )

    # 3. 获取文件属性
    response = client.head_object(
        Bucket='test01-123456789',
        Key=file_name
    )

    # 4. 删除单个文件
    response = client.delete_object(
        Bucket='test01-123456789',
        Key=file_name
    )

    # 5. 创建分片上传
    response = client.create_multipart_upload(
        Bucket='test01-123456789',
        Key='multipartfile.txt',
    )
    uploadid = get_id_from_xml(response.text)

    # 6. 删除分片上传
    response = client.abort_multipart_upload(
        Bucket='test01-123456789',
        Key='multipartfile.txt',
        UploadId=uploadid
    )

    # 7. 再次创建分片上传
    response = client.create_multipart_upload(
        Bucket='test01-123456789',
        Key='multipartfile.txt',
    )
    uploadid = response['UploadId']

    # 8. 上传分片
    response = client.upload_part(
        Bucket='test01-123456789',
        Key='multipartfile.txt',
        UploadId=uploadid,
        PartNumber=1,
        Body='A'*1024*1024*4
    )
    etag = response['ETag']

    # 9. 列出分片
    response = clieent.list_parts(
        Bucket='test01-123456789',
        Key='mutilpartfile.txt',
        UploadId=uploadid
    )
    lst = response['Part'] # list_parts最大数量为1000

    # 10. 完成分片上传
    response = client.complete_multipart_upload(
        Bucket='test01-123456789',
        Key='multipartfile.txt',
        UploadId=uploadid,
        MultipartUpload={'Part': lst} # 超过1000个分块，请本地保存分块信息，再complete
    )


    ############################################################################
    # Bucket操作                                                                 #
    ############################################################################
    # 1. 创建Bucket
    response = client.create_bucket(
        Bucket='test02-123456789',
        ACL='public-read'
    )   

    # 2. 删除Bucket
    response = client.delete_bucket(
        Bucket='test02-123456789'
    )

    # 3. 获取文件列表
    response = client.list_objects(
        Bucket='test01-123456789'
    )
