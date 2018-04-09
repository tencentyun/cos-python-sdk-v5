# -*- coding=utf-8

import hashlib
import base64
import os
import io
import sys
import xml.dom.minidom
import xml.etree.ElementTree
from urllib.parse import quote
from urllib.parse import unquote
from xml2dict import Xml2Dict
from dicttoxml import dicttoxml
from cos_exception import CosClientError
from cos_exception import CosServiceError

SINGLE_UPLOAD_LENGTH = 5*1024*1024*1024  # 单次上传文件最大为5G
LOGGING_UIN = 'id="qcs::cam::uin/100001001014:uin/100001001014"'
# kwargs中params到http headers的映射
maplist = {
            'ContentLength': 'Content-Length',
            'ContentMD5': 'Content-MD5',
            'ContentType': 'Content-Type',
            'CacheControl': 'Cache-Control',
            'ContentDisposition': 'Content-Disposition',
            'ContentEncoding': 'Content-Encoding',
            'ContentLanguage': 'Content-Language',
            'Expires': 'Expires',
            'ResponseContentType': 'response-content-type',
            'ResponseContentLanguage': 'response-content-language',
            'ResponseExpires': 'response-expires',
            'ResponseCacheControl': 'response-cache-control',
            'ResponseContentDisposition': 'response-content-disposition',
            'ResponseContentEncoding': 'response-content-encoding',
            'Metadata': 'Metadata',
            'ACL': 'x-cos-acl',
            'GrantFullControl': 'x-cos-grant-full-control',
            'GrantWrite': 'x-cos-grant-write',
            'GrantRead': 'x-cos-grant-read',
            'StorageClass': 'x-cos-storage-class',
            'Range': 'Range',
            'IfMatch': 'If-Match',
            'IfNoneMatch': 'If-None-Match',
            'IfModifiedSince': 'If-Modified-Since',
            'IfUnmodifiedSince': 'If-Unmodified-Since',
            'CopySourceIfMatch': 'x-cos-copy-source-If-Match',
            'CopySourceIfNoneMatch': 'x-cos-copy-source-If-None-Match',
            'CopySourceIfModifiedSince': 'x-cos-copy-source-If-Modified-Since',
            'CopySourceIfUnmodifiedSince': 'x-cos-copy-source-If-Unmodified-Since',
            'VersionId': 'versionId',
            'ServerSideEncryption': 'x-cos-server-side-encryption',
            'SSECustomerAlgorithm': 'x-cos-server-side-encryption-customer-algorithm',
            'SSECustomerKey': 'x-cos-server-side-encryption-customer-key',
            'SSECustomerKeyMD5': 'x-cos-server-side-encryption-customer-key-MD5',
            'SSEKMSKeyId': 'x-cos-server-side-encryption-cos-kms-key-id'
           }


def to_unicode(s):
    if isinstance(s, str):
        return s
    else:
        return s.decode('utf-8')


def get_md5(data):
    m2 = hashlib.md5(data)
    MD5 = base64.standard_b64encode(m2.digest())
    return MD5


def get_content_md5(body):
    body_type = type(body)
    # if body_type == str:
    if isinstance(body , str):
        return get_md5(body)
    elif isinstance(body,io.IOBase):
        if hasattr(body, 'tell') and hasattr(body, 'seek') and hasattr(body, 'read'):
            file_position = body.tell()  # 记录文件当前位置
            md5_str = get_md5(body.read())
            body.seek(file_position)  # 恢复初始的文件位置
            return md5_str
        else:
            raise CosClientError('can not get md5 digest for file without necessary attrs, including tell, seek and read')
    return None


def dict_to_xml(data):
    """V5使用xml格式，将输入的dict转换为xml"""
    doc = xml.dom.minidom.Document()
    root = doc.createElement('CompleteMultipartUpload')
    doc.appendChild(root)

    if 'Part' not in data.keys():
        raise CosClientError("Invalid Parameter, Part Is Required!")

    for i in data['Part']:
        nodePart = doc.createElement('Part')

        if 'PartNumber' not in i.keys():
            raise CosClientError("Invalid Parameter, PartNumber Is Required!")

        nodeNumber = doc.createElement('PartNumber')
        nodeNumber.appendChild(doc.createTextNode(str(i['PartNumber'])))

        if 'ETag' not in i.keys():
            raise CosClientError("Invalid Parameter, ETag Is Required!")

        nodeETag = doc.createElement('ETag')
        nodeETag.appendChild(doc.createTextNode(str(i['ETag'])))

        nodePart.appendChild(nodeNumber)
        nodePart.appendChild(nodeETag)
        root.appendChild(nodePart)
    return doc.toxml('utf-8')


def xml_to_dict(data, origin_str="", replace_str=""):
    """V5使用xml格式，将response中的xml转换为dict"""
    root = xml.etree.ElementTree.fromstring(data)
    xmldict = Xml2Dict(root)
    xmlstr = str(xmldict)
    xmlstr = xmlstr.replace("{http://www.qcloud.com/document/product/436/7751}", "")
    xmlstr = xmlstr.replace("{https://cloud.tencent.com/document/product/436}", "")
    xmlstr = xmlstr.replace("{http://doc.s3.amazonaws.com/2006-03-01}", "")
    xmlstr = xmlstr.replace("{http://www.w3.org/2001/XMLSchema-instance}", "")
    if origin_str:
        xmlstr = xmlstr.replace(origin_str, replace_str)
    xmldict = eval(xmlstr)
    return xmldict


def get_id_from_xml(data, name):
    """解析xml中的特定字段"""
    tree = xml.dom.minidom.parseString(data)
    root = tree.documentElement
    result = root.getElementsByTagName(name)
    # use childNodes to get a list, if has no child get itself
    return result[0].childNodes[0].nodeValue


def mapped(headers):
    """S3到COS参数的一个映射"""
    _headers = dict()
    for i in headers.keys():
        if i in maplist:
            _headers[maplist[i]] = headers[i]
        else:
            raise CosClientError('No Parameter Named '+i+' Please Check It')
    return _headers


def format_xml(data, root, lst=list()):
    """将dict转换为xml"""
    xml_config = dicttoxml(data, item_func=lambda x: x, custom_root=root, attr_type=False)
    for i in lst:
        xml_config = xml_config.replace(i+i, i)
    return xml_config


def format_region(region):
    """格式化地域"""
    if not region:
        raise CosClientError("region is required not empty!")
    if region.find('cos.') != -1:
        return region  # 传入cos.ap-beijing-1这样显示加上cos.的region
    if region == 'cn-north' or region == 'cn-south' or region == 'cn-east' or region == 'cn-south-2' or region == 'cn-southwest' or region == 'sg':
        return region  # 老域名不能加cos.
    #  支持v4域名映射到v5
    if region == 'cossh':
        return 'cos.ap-shanghai'
    if region == 'cosgz':
        return 'cos.ap-guangzhou'
    if region == 'cosbj':
        return 'cos.ap-beijing'
    if region == 'costj':
        return 'cos.ap-beijing-1'
    if region == 'coscd':
        return 'cos.ap-chengdu'
    if region == 'cossgp':
        return 'cos.ap-singapore'
    if region == 'coshk':
        return 'cos.ap-hongkong'
    if region == 'cosca':
        return 'cos.na-toronto'
    if region == 'cosger':
        return 'cos.eu-frankfurt'

    return 'cos.' + region  # 新域名加上cos.


def format_bucket(bucket, appid):
    """兼容新老bucket长短命名,appid为空默认为长命名,appid不为空则认为是短命名"""
    if not isinstance(bucket, str):
        raise CosClientError("bucket is not str")
    # appid为空直接返回bucket
    if not appid:
        return bucket
    # appid不为空,检查是否以-appid结尾
    if bucket.endswith("-"+appid):
        return bucket
    return bucket + "-" + appid


def format_path(path):
    """检查path是否合法,格式化path"""
    if not isinstance(path, str):
        raise CosClientError("your Key is not str")
    if path == "":
        raise CosClientError("Key can't be empty string")
    if path[0] == '/':
        path = path[1:]
    # 提前对path进行encode
    path = quote(path, '/-_.~')
    return path


def get_copy_source_info(CopySource):
    """获取拷贝源的所有信息"""
    appid = ""
    versionid = ""
    if 'Appid' in CopySource.keys():
        appid = CopySource['Appid']
    if 'Bucket' in CopySource.keys():
        bucket = CopySource['Bucket']
        bucket = format_bucket(bucket, appid)
    else:
        raise CosClientError('CopySource Need Parameter Bucket')
    if 'Region' in CopySource.keys():
        region = CopySource['Region']
        region = format_region(region)
    else:
        raise CosClientError('CopySource Need Parameter Region')
    if 'Key' in CopySource.keys():
        path = CopySource['Key']
    else:
        raise CosClientError('CopySource Need Parameter Key')
    if 'VersionId' in CopySource.keys():
        versionid = CopySource['VersionId']
    return bucket, path, region, versionid


def gen_copy_source_url(CopySource):
    """拼接拷贝源url"""
    bucket, path, region, versionid = get_copy_source_info(CopySource)
    path = format_path(path)
    if versionid != '':
        path = path + '?versionId=' + versionid
    url = "{bucket}.{region}.myqcloud.com/{path}".format(
            bucket=bucket,
            region=region,
            path=path
            )
    return url


def gen_copy_source_range(begin_range, end_range):
    """拼接bytes=begin-end形式的字符串"""
    range = "bytes={first}-{end}".format(
            first=begin_range,
            end=end_range
            )
    return range


def deal_with_empty_file_stream(data):
    """对于文件流的剩余长度为0的情况下，返回空字节流"""
    if hasattr(data, 'fileno') and hasattr(data, 'tell'):
        try:
            fileno = data.fileno()
            total_length = os.fstat(fileno).st_size
            current_position = data.tell()
            if total_length - current_position == 0:
                return ""
        except io.UnsupportedOperation:
            return ""
    return data


def format_dict(data, key_lst):
    """转换返回dict中的可重复字段为list"""
    for key in key_lst:
        # 将dict转为list，保持一致
        if key in data.keys() and isinstance(data[key], dict):
            lst = []
            lst.append(data[key])
            data[key] = lst
    return data


def decode_result(data, key_lst, multi_key_list):
    """decode结果中的字段"""
    for key in key_lst:
        if key in data.keys() and data[key]:
            data[key] = unquote(data[key])
    for multi_key in multi_key_list:
        if multi_key[0] in data.keys():
            for item in data[multi_key[0]]:
                if multi_key[1] in item.keys() and item[multi_key[1]]:
                    item[multi_key[1]] = unquote(item[multi_key[1]])
    return data
