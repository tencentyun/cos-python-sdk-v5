# -*- coding: utf-8 -*-
from cos_client import CosConfig, CosS3Client
from ConfigParser import SafeConfigParser
from argparse import ArgumentParser
import sys
import logging
import os

logger = logging.getLogger(__name__)

fs_coding = sys.getfilesystemencoding()


def to_printable_str(s):
    if isinstance(s, unicode):
        return s.encode(fs_coding)
    else:
        return s


def config(args):
    logger.debug("config: " + str(args))

    conf_path = os.path.expanduser('~/.cos.conf')

    with open(conf_path, 'w+') as f:
        cp = SafeConfigParser()
        cp.add_section("common")
        cp.set('common', 'access_id', args.access_id)
        cp.set('common', 'secret_key', args.secret_key)
        cp.set('common', 'appid', args.appid)
        cp.set('common', 'bucket', args.bucket)
        cp.set('common', 'region', args.region)
        cp.set('common', 'max_thread', str(args.max_thread))
        cp.set('common', 'part_size', str(args.part_size))
        cp.write(f)
        logger.info("Created configuration file in {path}".format(path=to_printable_str(conf_path)))


def load_conf():

    conf_path = os.path.expanduser('~/.cos.conf')
    if not os.path.exists(conf_path):
        logger.warn("{conf} couldn't be found, please config tool!".format(conf=to_printable_str(conf_path)))
        raise IOError
    else:
        logger.info('{conf} is found.'.format(conf=to_printable_str(conf_path)))

    with open(conf_path, 'r') as f:
        cp = SafeConfigParser()
        cp.readfp(fp=f)
        if cp.has_option('common', 'part_size'):
            part_size = cp.getint('common', 'part_size')
        else:
            part_size = 1

        if cp.has_option('common', 'max_thread'):
            max_thread = cp.getint('common', 'max_thread')
        else:
            max_thread = 5
        conf = CosConfig(
            appid=cp.get('common', 'appid'),
            access_id=cp.get('common', 'access_id'),
            access_key=cp.get('common', 'secret_key'),
            region=cp.get('common', 'region'),
            bucket=cp.get('common', 'bucket'),
            part_size=part_size,
            max_thread=max_thread
        )
        return conf


class ObjectOp(object):
    @staticmethod
    def upload(args):
        conf = load_conf()
        client = CosS3Client(conf)
        while args.cos_path.startswith('/'):
            args.cos_path = args.cos_path[1:]
        Intface = client.obj_int()

        if not isinstance(args.local_path, unicode):
            args.local_path = args.local_path.decode(fs_coding)
        if not isinstance(args.cos_path, unicode):
            args.cos_path = args.cos_path.decode(fs_coding)

        if not os.path.exists(args.local_path):
            logger.info('local_path %s not exist!' % to_printable_str(args.local_path))
            return -1

        if not os.access(args.local_path, os.R_OK):
            logger.info('local_path %s is not readable!' % to_printable_str(args.local_path))
            return -1
        if os.path.isdir(args.local_path):
            rt = Intface.upload_folder(args.local_path, args.cos_path)
            logger.info("upload {file} finished".format(file=to_printable_str(args.local_path)))
            logger.info("totol of {folders} folders, {files} files".format(folders=Intface._folder_num, files=Intface._file_num))
            if rt:
                return 0
            else:
                return -1
        elif os.path.isfile(args.local_path):
            if Intface.upload_file(args.local_path, args.cos_path) is True:
                logger.info("upload {file} success".format(file=to_printable_str(args.local_path)))
                return 0
            else:
                logger.info("upload {file} fail".format(file=to_printable_str(args.local_path)))
                return -1
        else:
            logger.info("file or folder not exsist!")
            return -1
        return -1

    @staticmethod
    def download(args):
        conf = load_conf()
        client = CosS3Client(conf)
        while args.cos_path.startswith('/'):
            args.cos_path = args.cos_path[1:]
        Intface = client.obj_int()
        if not isinstance(args.local_path, unicode):
            args.local_path = args.local_path.decode(fs_coding)

        if not isinstance(args. cos_path, unicode):
            args.cos_path = args.cos_path.decode(fs_coding)

        if Intface.download_file(args.local_path, args.cos_path):
            logger.info("download success!")
            return 0
        else:
            logger.info("download fail!")
            return -1

    @staticmethod
    def delete(args):
        conf = load_conf()
        client = CosS3Client(conf)
        while args.cos_path.startswith('/'):
            args.cos_path = args.cos_path[1:]
        Intface = client.obj_int()

        if not isinstance(args. cos_path, unicode):
            args.cos_path = args.cos_path.decode(fs_coding)
        if Intface.delete_file(args.cos_path):
            logger.info("delete success!")
            return 0
        else:
            logger.info("delete fail!")
            return -1

    @staticmethod
    def put_object_acl(args):
        conf = load_conf()
        client = CosS3Client(conf)
        while args.cos_path.startswith('/'):
            args.cos_path = args.cos_path[1:]
        if not isinstance(args. cos_path, unicode):
            args.cos_path = args.cos_path.decode(fs_coding)
        Intface = client.obj_int()
        rt = Intface.put_object_acl(args.grant_read, args.grant_write, args.grant_full_control, args.cos_path)
        if rt is True:
            logger.info("put success!")
            return 0
        else:
            logger.info("put fail!")
            return -1

    @staticmethod
    def get_object_acl(args):
        conf = load_conf()
        client = CosS3Client(conf)
        while args.cos_path.startswith('/'):
            args.cos_path = args.cos_path[1:]
        if not isinstance(args. cos_path, unicode):
            args.cos_path = args.cos_path.decode(fs_coding)
        Intface = client.obj_int()

        rt = Intface.get_object_acl(args.cos_path)
        if rt is True:
            logger.info("get success!")
            return 0
        else:
            logger.info("get fail!")
            return -1


class BucketOp(object):

    @staticmethod
    def create(args):
        conf = load_conf()
        client = CosS3Client(conf)
        Intface = client.buc_int()
        if Intface.create_bucket():
            logger.info("create success!")
            return 0
        else:
            logger.info("create fail!")
            return -1

    @staticmethod
    def delete(args):
        conf = load_conf()
        client = CosS3Client(conf)
        Intface = client.buc_int()
        if Intface.delete_bucket():
            logger.info("delete success!")
            return 0
        else:
            logger.info("delete fail!")
            return -1

    @staticmethod
    def list(args):
        conf = load_conf()
        client = CosS3Client(conf)
        Intface = client.buc_int()
        if Intface.get_bucket():
            logger.info("save as tmp.xml in the current directory！")
            logger.info("list success!")
            return 0
        else:
            logger.info("list fail!")
            return -1

    @staticmethod
    def put_bucket_acl(args):
        conf = load_conf()
        client = CosS3Client(conf)
        Intface = client.buc_int()
        rt = Intface.put_bucket_acl(args.grant_read, args.grant_write, args.grant_full_control)
        if rt is True:
            logger.info("put success!")
            return 0
        else:
            logger.info("put fail!")
            return -1

    @staticmethod
    def get_bucket_acl(args):
        conf = load_conf()
        client = CosS3Client(conf)
        Intface = client.buc_int()
        rt = Intface.get_bucket_acl()
        if rt is True:
            logger.info("get success!")
            return 0
        else:
            logger.info("get fail!")
            return -1


def _main():

    parser = ArgumentParser()
    parser.add_argument('-v', '--verbose', help="verbose mode", action="store_true", default=False)

    sub_parser = parser.add_subparsers(help="config")
    parser_config = sub_parser.add_parser("config")
    parser_config.add_argument('-a', '--access_id', help='specify your access id', type=str, required=True)
    parser_config.add_argument('-s', '--secret_key', help='specify your secret key', type=str, required=True)
    parser_config.add_argument('-u', '--appid', help='specify your appid', type=str, required=True)
    parser_config.add_argument('-b', '--bucket', help='specify your bucket', type=str, required=True)
    parser_config.add_argument('-r', '--region', help='specify your bucket', type=str, required=True)
    parser_config.add_argument('-m', '--max_thread', help='specify the number of threads (default 5)', type=int, default=5)
    parser_config.add_argument('-p', '--part_size', help='specify min part size in MB (default 1MB)', type=int, default=1)
    parser_config.set_defaults(func=config)

    parser_upload = sub_parser.add_parser("upload")
    parser_upload.add_argument('local_path', help="local file path as /tmp/a.txt", type=str)
    parser_upload.add_argument("cos_path", help="cos_path as a/b.txt", type=str)
    parser_upload.add_argument("-t", "--type", help="storage class type: standard/nearline/coldline", type=str, choices=["standard", "nearline", "coldline"], default="standard")
    parser_upload.set_defaults(func=ObjectOp.upload)

    parser_download = sub_parser.add_parser("download")
    parser_download.add_argument('local_path', help="local file path as /tmp/a.txt", type=str)
    parser_download.add_argument("cos_path", help="cos_path as a/b.txt", type=str)
    parser_download.set_defaults(func=ObjectOp.download)

    parser_delete = sub_parser.add_parser("delete")
    parser_delete.add_argument("cos_path", help="cos_path as a/b.txt", type=str)
    parser_delete.set_defaults(func=ObjectOp.delete)

    parser_create_bucket = sub_parser.add_parser("createbucket")
    parser_create_bucket.set_defaults(func=BucketOp.create)

    parser_delete_bucket = sub_parser.add_parser("deletebucket")
    parser_delete_bucket.set_defaults(func=BucketOp.delete)

    parser_list_bucket = sub_parser.add_parser("listbucket")
    parser_list_bucket.set_defaults(func=BucketOp.list)

    parser_put_object_acl = sub_parser.add_parser("putobjectacl")
    parser_put_object_acl.add_argument("cos_path", help="cos_path as a/b.txt", type=str)
    parser_put_object_acl.add_argument('--grant-read', dest='grant_read', help='set grant-read', type=str, required=False)
    parser_put_object_acl.add_argument('--grant-write', dest='grant_write', help='set grant-write', type=str, required=False)
    parser_put_object_acl.add_argument('--grant-full-control', dest='grant_full_control', help='set grant-full-control', type=str, required=False)
    parser_put_object_acl.set_defaults(func=ObjectOp.put_object_acl)

    parser_get_object_acl = sub_parser.add_parser("getobjectacl")
    parser_get_object_acl.add_argument("cos_path", help="cos_path as a/b.txt", type=str)
    parser_get_object_acl.set_defaults(func=ObjectOp.get_object_acl)

    parser_put_bucket_acl = sub_parser.add_parser("putbucketacl")
    parser_put_bucket_acl.add_argument('--grant-read', dest='grant_read', help='set grant-read', type=str, required=False)
    parser_put_bucket_acl.add_argument('--grant-write', dest='grant_write', help='set grant-write', type=str, required=False)
    parser_put_bucket_acl.add_argument('--grant-full-control', dest='grant_full_control', help='set grant-full-control', type=str, required=False)
    parser_put_bucket_acl.set_defaults(func=BucketOp.put_bucket_acl)

    parser_get_bucket_acl = sub_parser.add_parser("getbucketacl")
    parser_get_bucket_acl.set_defaults(func=BucketOp.get_bucket_acl)
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, format="%(asctime)s - %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(asctime)s - %(message)s")

    return args.func(args)


if __name__ == '__main__':
    _main()
