# -*- coding: utf-8 -*-

import os
import random
import logging
import copy
import base64
import struct
from .cos_comm import *
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto import Random
from Crypto.Util import Counter
from Crypto.Cipher import PKCS1_OAEP, PKCS1_v1_5
from .cos_exception import CosClientError
from .streambody import StreamBody
from abc import ABCMeta, abstractmethod

logger = logging.getLogger(__name__)

_AES_CTR_COUNTER_BITS_LENGTH = 8 * 16
_AES_256_KEY_SIZE = 32


def random_key(key_len):
    return Random.new().read(key_len)


def random_iv():
    iv = Random.new().read(16)
    return iv


def iv_to_big_int(iv):
    iv_pair = struct.unpack(">QQ", iv)
    iv_int = iv_pair[0] << 64 | iv_pair[1]
    return iv_int


class AESCTRCipher(object):
    """数据加密类，用于加密用户数据"""

    def __init__(self):
        """初始化"""
        self.__block_size_len = AES.block_size
        self.__cipher = None
        self.__key_len = _AES_256_KEY_SIZE

    def new_cipher(self, key, start, offset=0):
        """初始化AES加解密对象

        :param key(string): 对称密钥
        :param start(int): 对称加密初始随机值
        :param offset(int): 主要用于解密，想要解密文本的偏移，必须为16的整数倍
        """
        block_index_offset = self.__calc_offset(offset)
        new_start = start + block_index_offset
        my_counter = Counter.new(_AES_CTR_COUNTER_BITS_LENGTH, initial_value=new_start)
        self.__cipher = AES.new(key, AES.MODE_CTR, counter=my_counter)

    def encrypt(self, plaintext):
        """加密数据

        :param plaintext(string): 需要加密的数据
        """
        if self.__cipher is None:
            raise CosClientError('cipher is not initialized')
        return self.__cipher.encrypt(plaintext)

    def decrypt(self, plaintext):
        """解密数据

        :param plaintext(string): 需要解密的数据，数据的起始位置必须为16的整数倍
        """
        if self.__cipher is None:
            raise CosClientError('cipher is not initialized')
        return self.__cipher.decrypt(plaintext)

    # offset 必须为block_size的整数倍
    def __calc_offset(self, offset):
        """通过文本偏移计算counter的偏移

        :param offset(int): 文本偏移
        """
        if not self.__is_block_aligned(offset):
            raise CosClientError('offset is not align to encrypt block')
        return offset // self.__block_size_len

    def __is_block_aligned(self, offset):
        """判断文本偏移是否是block_size对齐

        :param offset(int): 文本偏移
        """
        if offset is None:
            offset = 0
        return 0 == offset % self.__block_size_len

    def adjust_read_offset(self, offset):
        """用于调整读取的offset为block_size对齐"""

        if offset:
            offset = (offset // self.__block_size_len) * self.__block_size_len
        return offset

    def get_key(self):
        """获取随机密钥"""
        return random_key(self.__key_len)

    def get_counter_iv(self):
        """获取对称加密初始随机值"""
        return random_iv()


class RSAKeyPair:
    """封装有公钥和私钥"""

    def __init__(self, public_key, private_key):
        self.publick_key = public_key
        self.private_key = private_key


class RSAKeyPairPath:
    """封装有公钥和私钥的路径"""

    def __init__(self, public_key_path, private_key_path):
        self.public_key_path = public_key_path
        self.private_key_path = private_key_path


class BaseProvider(object):
    """客户端主密钥加密基类"""

    def __init__(self, cipher):
        """初始化
        :param cipher(an AES object): 数据加解密类
        """
        self.data_cipher = cipher

    def get_data_key(self):
        """随机获取数据加解密密钥"""
        return self.data_cipher.get_key()

    @abstractmethod
    def init_data_cipher(self):
        """初始化cipher"""
        pass

    @abstractmethod
    def init_data_cipter_by_user(self, encrypt_key, encrypt_iv, offset=0):
        """根据密钥初始化cipher"""
        pass

    def adjust_read_offset(self, start):
        """用于调整读取的offset为block_size对齐"""
        return self.data_cipher.adjust_read_offset(start)

    def make_data_encrypt_adapter(self, stream):
        """创建数据流加密适配器"""
        size = 0
        if hasattr(stream, '__len__'):
            size = len(stream)
        elif hasattr(stream, 'tell') and hasattr(stream, 'seek'):
            current = stream.tell()
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(current, os.SEEK_SET)
        else:
            return None
        return DataEncryptAdapter(stream, size, copy.copy(self.data_cipher))

    def make_data_decrypt_adapter(self, rt, offset):
        """创建数据流解密适配器"""
        return DataDecryptAdapter(rt, copy.copy(self.data_cipher), offset)


class RSAProvider(BaseProvider):
    """客户端非对称主密钥加密类"""

    def __init__(self, key_pair_info=None, cipher=AESCTRCipher(), passphrase=None):
        """初始化"""
        super(RSAProvider, self).__init__(cipher=cipher)

        default_rsa_dir = os.path.expanduser('~/.cos_local_rsa')
        default_public_key_path = os.path.join(default_rsa_dir, '.public_key.pem')
        default_private_key_path = os.path.join(default_rsa_dir, '.private_key.pem')
        self.__encrypt_obj = None
        self.__decrypt_obj = None
        self.__data_key = None
        self.__data_iv = None

        if isinstance(key_pair_info, RSAKeyPair):
            self.__encrypt_obj = PKCS1_v1_5.new(RSA.importKey(key_pair_info.publick_key, passphrase=passphrase))
            self.__decrypt_obj = PKCS1_v1_5.new(RSA.importKey(key_pair_info.private_key, passphrase=passphrase))
        elif isinstance(key_pair_info, RSAKeyPairPath):
            self.__encrypt_obj, self.__decrypt_obj = self.__get_key_by_path(key_pair_info.public_key_path,
                                                                            key_pair_info.private_key_path, passphrase)
        else:
            logger.info('key_pair_info is None, try to get key from default path')
            if os.path.exists(default_private_key_path) and os.path.exists(default_public_key_path):
                self.__encrypt_obj, self.__decrypt_obj = self.__get_key_by_path(default_public_key_path,
                                                                                default_private_key_path, passphrase)

        # 为用户自动创建rsa
        if self.__encrypt_obj is None and self.__decrypt_obj is None:
            logger.warning('fail to get rsa key, will generate key')
            private_key = RSA.generate(2048)
            public_key = private_key.publickey()

            self.__encrypt_obj = PKCS1_OAEP.new(public_key)
            self.__decrypt_obj = PKCS1_OAEP.new(private_key)

            if not os.path.exists(default_rsa_dir):
                os.makedirs(default_rsa_dir)

            with open(default_private_key_path, 'wb') as f:
                f.write(private_key.exportKey(passphrase=passphrase))

            with open(default_public_key_path, 'wb') as f:
                f.write(public_key.exportKey(passphrase=passphrase))

    @staticmethod
    def get_rsa_key_pair(public_key, private_key):
        """开放给用户，用于生成RSAKeyPair"""
        if public_key is None or private_key is None:
            raise CosClientError('public_key or private_key is not allowed to be None !!!')
        return RSAKeyPair(public_key, private_key)

    @staticmethod
    def get_rsa_key_pair_path(public_key_path, private_key_path):
        """开放给用户，用于生成RSAKeyPairPath"""
        if public_key_path is None or private_key_path is None:
            raise CosClientError('public_key or private_key is not allowed to be None !!!')
        return RSAKeyPairPath(public_key_path, private_key_path)

    def __get_key_by_path(self, public_path=None, private_path=None, passphrase=None):
        """用于从提供的路径中获取公钥和私钥"""
        if public_path is None or private_path is None:
            return None, None

        encrypt_obj, decrypt_obj = None, None

        if os.path.exists(public_path) and os.path.exists(private_path):
            with open(public_path, 'rb') as f:
                encrypt_obj = PKCS1_OAEP.new(RSA.importKey(f.read(), passphrase=passphrase))

            with open(private_path, 'rb') as f:
                decrypt_obj = PKCS1_OAEP.new(RSA.importKey(f.read(), passphrase=passphrase))

        return encrypt_obj, decrypt_obj

    def init_data_cipher(self):
        """初始化cipher"""
        encrypt_key = None
        encrypt_iv = None
        self.__data_key = self.get_data_key()
        self.__data_iv = self.data_cipher.get_counter_iv()
        start = iv_to_big_int(self.__data_iv)
        self.data_cipher.new_cipher(self.__data_key, start)
        encrypt_key = self.__encrypt_obj.encrypt(self.__data_key)
        encrypt_iv = self.__encrypt_obj.encrypt(self.__data_iv)
        return encrypt_key, encrypt_iv

    def init_data_cipter_by_user(self, encrypt_key, encrypt_iv, offset=0):
        """根据密钥初始化cipher"""
        self.__data_key = self.__decrypt_obj.decrypt(encrypt_key)
        self.__data_iv = self.__decrypt_obj.decrypt(encrypt_iv)
        start = iv_to_big_int(self.__data_iv)
        self.data_cipher.new_cipher(self.__data_key, start, offset)


class AESProvider(BaseProvider):
    """客户端对称主密钥加密类"""

    def __init__(self, aes_key=None, aes_key_path=None, cipher=AESCTRCipher()):
        """初始化"""
        super(AESProvider, self).__init__(cipher=cipher)
        self.__ed_obj = None
        self.__data_key = None
        self.__data_iv = None
        self.__my_counter = Counter.new(_AES_CTR_COUNTER_BITS_LENGTH, initial_value=0)
        self.__aes_key = aes_key
        self.__aes_key_path = aes_key_path

    def init_ed_obj(self):
        default_aes_dir = os.path.expanduser('~/.cos_local_aes')
        default_key_path = os.path.join(default_aes_dir, '.aes_key.pem')
        if self.__aes_key:
            aes_key = to_bytes(base64.b64decode(to_bytes(self.__aes_key)))
            self.__ed_obj = AES.new(aes_key, AES.MODE_CTR, counter=self.__my_counter)
        elif self.__aes_key_path:
            if os.path.exists(self.__aes_key_path):
                with open(self.__aes_key_path, 'rb') as f:
                    aes_key = f.read()
                    aes_key = to_bytes(base64.b64decode(to_bytes(aes_key)))
                    self.__ed_obj = AES.new(aes_key, AES.MODE_CTR, counter=self.__my_counter)
        else:
            logger.info('aes_key and aes_key_path is None, try to get key from default path')
            if os.path.exists(default_key_path):
                with open(default_key_path, 'rb') as f:
                    aes_key = f.read()
                    aes_key = to_bytes(base64.b64decode(to_bytes(aes_key)))
                    self.__ed_obj = AES.new(aes_key, AES.MODE_CTR, counter=self.__my_counter)

        if self.__ed_obj is None:
            logger.warning('fail to get aes key, will generate key')
            aes_key = random_key(_AES_256_KEY_SIZE)
            self.__ed_obj = AES.new(aes_key, AES.MODE_CTR, counter=self.__my_counter)
            if not os.path.exists(default_aes_dir):
                os.makedirs(default_aes_dir)

            with open(default_key_path, 'wb') as f:
                aes_key = to_bytes(base64.b64encode(to_bytes(aes_key)))
                f.write(aes_key)

    def init_data_cipher(self):
        """初始化cipher"""
        encrypt_key = None
        encrypt_iv = None
        self.__data_key = self.get_data_key()
        self.__data_iv = self.data_cipher.get_counter_iv()
        start = iv_to_big_int(self.__data_iv)
        self.data_cipher.new_cipher(self.__data_key, start)

        self.init_ed_obj()
        encrypt_key = self.__ed_obj.encrypt(self.__data_key)
        encrypt_iv = self.__ed_obj.encrypt(self.__data_iv)
        return encrypt_key, encrypt_iv

    def init_data_cipter_by_user(self, encrypt_key, encrypt_iv, offset=0):
        """根据密钥初始化cipher"""
        self.init_ed_obj()
        self.__data_key = self.__ed_obj.decrypt(encrypt_key)
        self.__data_iv = self.__ed_obj.decrypt(encrypt_iv)
        start = iv_to_big_int(self.__data_iv)
        self.data_cipher.new_cipher(self.__data_key, start, offset)


class MetaHandle(object):
    """用于获取/生成加密的元信息"""

    def __init__(self, encrypt_key=None, encrypt_iv=None):
        """初始化

        :param encrypt_key(string): 加密的数据密钥
        :param encrypt_iv(bytes): 加密counter的初始值
        """
        self.__encrypt_key = encrypt_key
        self.__encrypt_iv = encrypt_iv

    def set_object_meta(self, headers):
        """设置加密元信息到object的头部"""
        meta_data = dict()
        meta_data['x-cos-meta-client-side-encryption-key'] = to_bytes(base64.b64encode(to_bytes(self.__encrypt_key)))
        meta_data['x-cos-meta-client-side-encryption-iv'] = to_bytes(base64.b64encode(to_bytes(self.__encrypt_iv)))
        headers['Metadata'] = meta_data
        return headers

    def get_object_meta(self, headers):
        """从object的头部获取加密元信息"""
        if 'x-cos-meta-client-side-encryption-key' in headers and 'x-cos-meta-client-side-encryption-iv' in headers:
            self.__encrypt_key = base64.b64decode(to_bytes(headers['x-cos-meta-client-side-encryption-key']))
            self.__encrypt_iv = base64.b64decode(to_bytes(headers['x-cos-meta-client-side-encryption-iv']))
        return self.__encrypt_key, self.__encrypt_iv


class DataEncryptAdapter(object):
    """用于读取经过加密后的的数据"""

    def __init__(self, data, content_len, data_cipher):
        self._data = to_bytes(data)
        self._data_cipher = data_cipher
        self._content_len = content_len
        self._read_len = 0

    @property
    def len(self):
        return self._content_len

    def read(self, length):
        """读取加密后的数据"""
        if self._read_len >= self._content_len:
            return ''

        if length is None or length < 0:
            bytes_to_read = self._content_len - self._read_len
        else:
            bytes_to_read = min(length, self._content_len - self._read_len)

        if isinstance(self._data, bytes):
            content = self._data[self._read_len:self._read_len + bytes_to_read]
        else:
            content = self._data.read(bytes_to_read)

        self._read_len += bytes_to_read
        content = self._data_cipher.encrypt(content)
        return content


class DataDecryptAdapter(StreamBody):
    """用于读取经过解密后的数据"""

    def __init__(self, rt, data_cipher, offset=0):
        """初始化
        :param rt(request object): request请求返回的对象
        :param data_cipher(an AES object): 数据加解密类
        :param offset(int): 数据读取的偏移量
        """
        super(DataDecryptAdapter, self).__init__(rt)
        self._data_cipher = data_cipher
        self._offset = offset

    def read(self, length, auto_decompress=False):
        """读取解密后的数据"""
        if self._read_len >= self._content_len:
            return ''

        if self._use_encoding and not auto_decompress:
            content = self._rt.raw.read(length)
        else:
            try:
                content = next(self._rt.iter_content(length))
            except StopIteration:
                return ''

        content = self._data_cipher.decrypt(content)
        if self._read_len < self._offset and self._read_len + len(content) > self._offset:
            content = content[self._offset:]
            self._read_len = self._offset
        return content
