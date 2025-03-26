# -*- coding=utf-8

from six import text_type, binary_type, string_types
from six.moves.urllib.parse import quote, unquote, urlparse
import hashlib
import base64
import os
import io
import re
import sys
import threading
import xml.dom.minidom
import xml.etree.ElementTree
from datetime import datetime
from xmltodict import unparse
from .xml2dict import Xml2Dict
from .cos_exception import CosClientError
from .cos_exception import CosServiceError

SINGLE_UPLOAD_LENGTH = 5 * 1024 * 1024 * 1024  # 单次上传文件最大为5GB
DEFAULT_CHUNK_SIZE = 1024 * 1024  # 计算MD5值时,文件单次读取的块大小为1MB
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
    'SSEKMSKeyId': 'x-cos-server-side-encryption-cos-kms-key-id',
    'SSEKMSContext': 'x-cos-server-side-encryption-context',
    'SSECustomerAlgorithm': 'x-cos-server-side-encryption-customer-algorithm',
    'SSECustomerKey': 'x-cos-server-side-encryption-customer-key',
    'SSECustomerKeyMD5': 'x-cos-server-side-encryption-customer-key-MD5',
    'CopySourceSSECustomerAlgorithm': 'x-cos-copy-source-server-side-encryption-customer-algorithm',
    'CopySourceSSECustomerKey': 'x-cos-copy-source-server-side-encryption-customer-key',
    'CopySourceSSECustomerKeyMD5': 'x-cos-copy-source-server-side-encryption-customer-key-MD5',
    'Referer': 'Referer',
    'PicOperations': 'Pic-Operations',
    'TrafficLimit': 'x-cos-traffic-limit',
    'Accept': 'Accept'
}


def to_str(s):
    """非字符串转换为字符串"""
    if isinstance(s, text_type) or isinstance(s, binary_type):
        return s
    return str(s)


def to_unicode(s):
    """将字符串转为unicode"""
    if isinstance(s, binary_type):
        try:
            return s.decode('utf-8')
        except UnicodeDecodeError as e:
            raise CosClientError('your bytes strings can not be decoded in utf8, utf8 support only!')
    return s


def to_bytes(s):
    """将字符串转为bytes"""
    if isinstance(s, text_type):
        try:
            return s.encode('utf-8')
        except UnicodeEncodeError as e:
            raise CosClientError('your unicode strings can not encoded in utf8, utf8 support only!')
    return s


def get_raw_md5(data):
    """计算md5 md5的输入必须为bytes"""
    data = to_bytes(data)
    m2 = hashlib.md5(data)
    etag = '"' + str(m2.hexdigest()) + '"'
    return etag


def get_md5(data):
    """计算 base64 md5 md5的输入必须为bytes"""
    data = to_bytes(data)
    m2 = hashlib.md5(data)
    MD5 = base64.standard_b64encode(m2.digest())
    return MD5


def get_content_md5(body):
    """计算任何输入流的md5值"""
    if isinstance(body, text_type) or isinstance(body, binary_type):
        return get_md5(body)
    elif hasattr(body, 'tell') and hasattr(body, 'seek') and hasattr(body, 'read'):
        file_position = body.tell()  # 记录文件当前位置
        # avoid OOM
        md5 = hashlib.md5()
        chunk = body.read(DEFAULT_CHUNK_SIZE)
        while chunk:
            md5.update(to_bytes(chunk))
            chunk = body.read(DEFAULT_CHUNK_SIZE)
        md5_str = base64.standard_b64encode(md5.digest())
        try:
            body.seek(file_position)  # 恢复初始的文件位置
        except Exception as e:
            raise CosClientError('seek unsupported to calculate md5!')
        return md5_str
    else:
        raise CosClientError('unsupported body type to calculate md5!')
    return None


def dict_to_xml(data):
    """V5使用xml格式，将输入的dict转换为xml"""
    doc = xml.dom.minidom.Document()
    root = doc.createElement('CompleteMultipartUpload')
    doc.appendChild(root)

    if 'Part' not in data:
        raise CosClientError("Invalid Parameter, Part Is Required!")

    for i in data['Part']:
        nodePart = doc.createElement('Part')

        if 'PartNumber' not in i:
            raise CosClientError("Invalid Parameter, PartNumber Is Required!")

        nodeNumber = doc.createElement('PartNumber')
        nodeNumber.appendChild(doc.createTextNode(str(i['PartNumber'])))

        if 'ETag' not in i:
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
    xmlstr = xmlstr.replace("{http://s3.amazonaws.com/doc/2006-03-01/}", "")
    xmlstr = xmlstr.replace("{http://www.w3.org/2001/XMLSchema-instance}", "")
    if origin_str:
        xmlstr = xmlstr.replace(origin_str, replace_str)
    xmldict = eval(xmlstr)
    return xmldict


# def get_id_from_xml(data, name):
#     """解析xml中的特定字段"""
#     tree = xml.dom.minidom.parseString(data)
#     root = tree.documentElement
#     result = root.getElementsByTagName(name)
#     # use childNodes to get a list, if has no child get itself
#     return result[0].childNodes[0].nodeValue


def mapped(headers):
    """S3到COS参数的一个映射"""
    _headers = dict()
    for i in headers:
        if i in maplist:
            if i == 'Metadata':
                for meta in headers[i]:
                    _headers[meta] = headers[i][meta]
            else:
                _headers[maplist[i]] = headers[i]
        else:
            raise CosClientError('No Parameter Named ' + i + ' Please Check It')
    return _headers


# def format_xml(data, root, lst=list(), parent_child=False):
#     """将dict转换为xml, xml_config是一个bytes"""
#     if parent_child:
#         xml_config = dicttoxml(data, item_func=lambda x: x[:-2], custom_root=root, attr_type=False)
#     else:
#         xml_config = dicttoxml(data, item_func=lambda x: x, custom_root=root, attr_type=False)
#     for i in lst:
#         xml_config = xml_config.replace(to_bytes(i + i), to_bytes(i))
#     return xml_config


def format_xml(data, root):
    """将dict转换为xml, xml_config是一个bytes"""
    input_dict = {root: data}
    xml_config = unparse(input_dict=input_dict).encode('utf-8')
    return xml_config


def format_values(data):
    """格式化headers和params中的values为bytes"""
    for i in data:
        data[i] = to_bytes(data[i])
    return data


def format_endpoint(endpoint, region, module, EnableOldDomain, EnableInternalDomain):
    # 客户使用全球加速域名时，只会传endpoint不会传region。此时这样endpointCi和region同时为None，就会报错。
    if not endpoint and not region and module == u'cos.':
        raise CosClientError("Region or Endpoint is required not empty!")

    """格式化终端域名"""
    if endpoint:
        return to_unicode(endpoint)
    elif region:
        region = format_region(region, module, EnableOldDomain, EnableInternalDomain)
        if EnableOldDomain:
            return u"{region}.myqcloud.com".format(region=region)
        else:
            return u"{region}.tencentcos.cn".format(region=region)
    else:
        return None

def switch_hostname(host):
    if not host:
        raise CosClientError("Host is required not empty!")
    
    # {bucket}-{appid}.cos.{region}.myqcloud.com
    if re.match(r'^([a-z0-9-]+-[0-9]+\.)(cos\.[a-z]+-[a-z]+(-[a-z]+)?(-1)?)\.(myqcloud\.com)$', host):
        host = host[:-len(".myqcloud.com")] + ".tencentcos.cn"
    
    return host

def switch_hostname_for_url(url):
    if not url:
        raise CosClientError("Url is required not empty!")

    url_parsed = urlparse(url)
    if url_parsed.hostname is not None:
        host = url_parsed.hostname
        new_host = switch_hostname(host)
        if host != new_host:
            new_url = url.replace(host, new_host)
            return new_url

    return url


def format_region(region, module, EnableOldDomain, EnableInternalDomain):
    """格式化地域"""
    if not isinstance(region, string_types):
        raise CosClientError("region is not string type")
    if not region:
        raise CosClientError("region is required not empty!")
    region = to_unicode(region)
    if not re.match(r'^[A-Za-z0-9][A-Za-z0-9.\-]*[A-Za-z0-9]$', region):
        raise CosClientError("region format is illegal, only digit, letter and - is allowed!")
    if region.find(module) != -1:
        return region  # 传入cos.ap-beijing-1这样显示加上cos.的region
    if region == u'cn-north' or region == u'cn-south' or region == u'cn-east' or region == u'cn-south-2' or region == u'cn-southwest' or region == u'sg':
        return region  # 老域名不能加cos.
    #  支持v4域名映射到v5

    # 转换为内部域名 (只有新域名才支持内部域名)
    if not EnableOldDomain and EnableInternalDomain and module == u'cos.':
        module = u'cos-internal.'

    if region == u'cossh':
        return module + u'ap-shanghai'
    if region == u'cosgz':
        return module + u'ap-guangzhou'
    if region == 'cosbj':
        return module + u'ap-beijing'
    if region == 'costj':
        return module + u'ap-beijing-1'
    if region == u'coscd':
        return module + u'ap-chengdu'
    if region == u'cossgp':
        return module + u'ap-singapore'
    if region == u'coshk':
        return module + u'ap-hongkong'
    if region == u'cosca':
        return module + u'na-toronto'
    if region == u'cosger':
        return module + u'eu-frankfurt'

    return module + region  # 新域名加上cos.


def format_bucket(bucket, appid):
    """兼容新老bucket长短命名,appid为空默认为长命名,appid不为空则认为是短命名"""
    if not isinstance(bucket, string_types):
        raise CosClientError("bucket is not string")
    if not bucket:
        raise CosClientError("bucket is required not empty")
    if not (re.match(r'^[A-Za-z0-9][A-Za-z0-9\-]*[A-Za-z0-9]$', bucket) or re.match('^[A-Za-z0-9]$', bucket)):
        raise CosClientError("bucket format is illegal, only digit, letter and - is allowed!")
    # appid为空直接返回bucket
    if not appid:
        return to_unicode(bucket)
    if not isinstance(appid, string_types):
        raise CosClientError("appid is not string")
    bucket = to_unicode(bucket)
    appid = to_unicode(appid)
    # appid不为空,检查是否以-appid结尾
    if bucket.endswith(u"-" + appid):
        return bucket
    return bucket + u"-" + appid


def path_simplify_check(path):
    """将path按照posix路径语义合并后,如果结果为空或'/'则抛异常"""
    path = to_unicode(path)
    stack = list()
    tokens = path.split(u'/')
    for token in tokens:
        if token == u'..':
            if stack:
                stack.pop()
        elif token and token != u'.':
            stack.append(token)
    path = u'/' + u'/'.join(stack)
    if path == u'/':
        raise CosClientError("GetObject Key is invalid")


def format_path(path):
    """检查path是否合法,格式化path"""
    if not isinstance(path, string_types):
        raise CosClientError("key is not string")
    if not path:
        raise CosClientError("Key is required not empty")
    path = to_unicode(path)
    if path[0] == u'/':
        path = path[1:]
    # 提前对path进行encode
    path = quote(to_bytes(path), b'/-_.~')
    return path


def get_copy_source_info(CopySource, EnableOldDomain, EnableInternalDomain):
    """获取拷贝源的所有信息"""
    appid = u""
    versionid = u""
    region = u""
    endpoint = u""
    if 'Appid' in CopySource:
        appid = CopySource['Appid']
    if 'Bucket' in CopySource:
        bucket = CopySource['Bucket']
        bucket = format_bucket(bucket, appid)
    else:
        raise CosClientError('CopySource Need Parameter Bucket')
    if 'Region' in CopySource:
        region = CopySource['Region']
    if 'Endpoint' in CopySource:
        endpoint = CopySource['Endpoint']
    endpoint = format_endpoint(endpoint, region, u'cos.', EnableOldDomain, EnableInternalDomain)
    if 'Key' in CopySource:
        path = to_unicode(CopySource['Key'])
        if path and path[0] == '/':
            path = path[1:]
    else:
        raise CosClientError('CopySource Need Parameter Key')
    if 'VersionId' in CopySource:
        versionid = to_unicode(CopySource['VersionId'])
    return bucket, path, endpoint, versionid


def gen_copy_source_url(CopySource, EnableOldDomain, EnableInternalDomain):
    """拼接拷贝源url"""
    bucket, path, endpoint, versionid = get_copy_source_info(CopySource, EnableOldDomain, EnableInternalDomain)
    path = format_path(path)
    if versionid != u'':
        path = path + u'?versionId=' + versionid
    url = u"{bucket}.{endpoint}/{path}".format(
        bucket=bucket,
        endpoint=endpoint,
        path=path
    )
    return url


def gen_copy_source_range(begin_range, end_range):
    """拼接bytes=begin-end形式的字符串"""
    range = u"bytes={first}-{end}".format(
        first=to_unicode(begin_range),
        end=to_unicode(end_range)
    )
    return range


def get_file_like_object_length(data):
    try:
        total_length = os.fstat(data.fileno()).st_size
    except IOError:
        if hasattr(data, '__len__'):
            total_length = len(data)
        else:
            # support BytesIO file-like object
            total_length = len(data.getvalue())
    try:
        current_position = data.tell()
    except IOError:
        current_position = 0
    content_len = total_length - current_position
    return content_len


def check_object_content_length(data):
    """put_object接口和upload_part接口的文件大小不允许超过5G"""
    content_len = 0
    if isinstance(data, text_type) or isinstance(data, binary_type):
        content_len = len(to_bytes(data))
    elif hasattr(data, 'fileno') and hasattr(data, 'tell'):
        content_len = get_file_like_object_length(data)
    else:
        # can not get the content-length, use chunked to upload the file
        pass
    if content_len > SINGLE_UPLOAD_LENGTH:
        raise CosClientError('The object size you upload can not be larger than 5GB in put_object or upload_part')
    return None


def format_dict(data, key_lst):
    """转换返回dict中的可重复字段为list"""
    if not (isinstance(data, dict) and isinstance(key_lst, list)):
        return data
    for key in key_lst:
        # 将dict转为list，保持一致
        if key in data and (isinstance(data[key], dict) or isinstance(data[key], string_types)):
            lst = []
            lst.append(data[key])
            data[key] = lst
        if key in data and data[key] is None:
            lst = []
            data[key] = lst
    return data


def format_dict_or_list(data, key_lst):
    """转换返回dict或list中的可重复字段为list"""
    if not ((isinstance(data, list) or isinstance(data, dict)) and isinstance(key_lst, list)):
        return data
    if isinstance(data, dict):
        return format_dict(data, key_lst)

    for data_item in data:
        format_dict(data_item, key_lst)

    return data


def decode_result(data, key_lst, multi_key_list):
    """decode结果中的字段"""
    for key in key_lst:
        if key in data and data[key]:
            data[key] = unquote(data[key])
    for multi_key in multi_key_list:
        if multi_key[0] in data:
            for item in data[multi_key[0]]:
                if multi_key[1] in item and item[multi_key[1]]:
                    item[multi_key[1]] = unquote(item[multi_key[1]])
    return data


def get_date(yy, mm, dd):
    """获取lifecycle中Date字段"""
    date_str = datetime(yy, mm, dd).isoformat()
    final_date_str = date_str + '+08:00'
    return final_date_str


def parse_object_canned_acl(result_acl, rsp_headers):
    """根据ACL返回的body信息,以及default头部来判断CannedACL"""
    if "x-cos-acl" in rsp_headers and rsp_headers["x-cos-acl"] == "default":
        return "default"
    public_read = {'Grantee': {'Type': 'Group', 'URI': 'http://cam.qcloud.com/groups/global/AllUsers'},
                   'Permission': 'READ'}
    if 'AccessControlList' in result_acl and result_acl['AccessControlList'] is not None and 'Grant' in result_acl['AccessControlList']:
        if public_read in result_acl['AccessControlList']['Grant']:
            return "public-read"
    return "private"


def parse_bucket_canned_acl(result_acl):
    """根据ACL返回的body信息来判断Bucket CannedACL"""
    public_read = {'Grantee': {'Type': 'Group', 'URI': 'http://cam.qcloud.com/groups/global/AllUsers'},
                   'Permission': 'READ'}
    public_write = {'Grantee': {'Type': 'Group', 'URI': 'http://cam.qcloud.com/groups/global/AllUsers'},
                    'Permission': 'WRITE'}
    if 'AccessControlList' in result_acl and result_acl['AccessControlList'] is not None and 'Grant' in result_acl['AccessControlList']:
        if public_read in result_acl['AccessControlList']['Grant']:
            if public_write in result_acl['AccessControlList']['Grant']:
                return "public-read-write"
            return "public-read"
    return "private"


def client_can_retry(file_position, **kwargs):
    """如果客户端请求中不包含data则可以重试,以及判断包含data的请求是否可以重试"""
    if 'data' not in kwargs:
        return True
    body = kwargs['data']
    if isinstance(body, text_type) or isinstance(body, binary_type):
        return True
    if file_position is not None and hasattr(body, 'tell') and hasattr(body, 'seek') and hasattr(body, 'read'):
        try:
            kwargs['data'].seek(file_position)
            return True
        except Exception as ioe:
            return False
    return False


class CiDetectType():
    """ci内容设备的类型设置,可与操作设多个"""
    PORN = 1
    TERRORIST = 2
    POLITICS = 4
    ADS = 8
    ILLEGAL = 16
    ABUSE = 32
    TEENAGER = 64

    @staticmethod
    def get_detect_type_str(DetectType):
        """获取审核的文字描述，这里只支持ci域名的入参，cos的跟这个还不一样"""
        detect_type = ''
        if DetectType & CiDetectType.PORN > 0:
            detect_type += 'Porn'
        if DetectType & CiDetectType.TERRORIST > 0:
            if len(detect_type) > 0:
                detect_type += ','
            detect_type += 'Terrorism'
        if DetectType & CiDetectType.POLITICS > 0:
            if len(detect_type) > 0:
                detect_type += ','
            detect_type += 'Politics'
        if DetectType & CiDetectType.ADS > 0:
            if len(detect_type) > 0:
                detect_type += ','
            detect_type += 'Ads'
        if DetectType & CiDetectType.ILLEGAL > 0:
            if len(detect_type) > 0:
                detect_type += ','
            detect_type += 'Illegal'
        if DetectType & CiDetectType.ABUSE > 0:
            if len(detect_type) > 0:
                detect_type += ','
            detect_type += 'Abuse'
        if DetectType & CiDetectType.TEENAGER > 0:
            if len(detect_type) > 0:
                detect_type += ','
            detect_type += 'Teenager'

        return detect_type


class ProgressCallback():
    def __init__(self, file_size, progress_callback):
        self.__lock = threading.Lock()
        self.__finished_size = 0
        self.__file_size = file_size
        self.__progress_callback = progress_callback

    def report(self, size):
        with self.__lock:
            self.__finished_size += size
            self.__progress_callback(self.__finished_size, self.__file_size)
