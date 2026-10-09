# -*- coding=utf-8
"""Rapid 高级上传下载、断点续传和并发路径单测。"""

import os
import io
import shutil
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta

import crcmod
import requests

from qcloud_cos import CosClientError, CosConfig, CosS3Client, CosServiceError
from qcloud_cos.cos_comm import to_unicode
from qcloud_cos.session_auth import SessionCredential


RAPID_BUCKET = 'rapid-x--1250000000'


def _client():
    config = CosConfig(
        Region='ap-guangzhou',
        # NOCA:PasswordLeak(Synthetic credential for local test fixtures; not a real account)
        SecretId='AKIDTEST',
        # NOCA:PasswordLeak(Synthetic credential for local test fixtures; not a real account)
        SecretKey='test-secret',
        Scheme='http',
        EnableRapidDomain=True,
        EnableSessionAuth=True)
    return CosS3Client(config, session=requests.Session())


class _RangeBody(object):
    def __init__(self, payload):
        self.payload = payload

    def pget_stream_to_file(self, stream, start, length):
        stream.seek(start)
        stream.write(self.payload[:length])


class TestRapidAdvancedTransfer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix='rapid-advanced-unit-')

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_upload_file_resumes_existing_mpu_and_uses_workers(self):
        client = _client()
        payload = (b'advanced-upload-' * 220000)[:3 * 1024 * 1024 + 31]
        source_path = os.path.join(self.temp_dir, 'source.bin')
        with open(source_path, 'wb') as source:
            source.write(payload)

        list_calls = []
        client.list_multipart_uploads = lambda **kwargs: (
            list_calls.append(kwargs) or {
                'Upload': [{'Key': 'large.bin', 'UploadId': 'upload-existing'}],
                'IsTruncated': 'false',
            })

        def check_parts(_bucket, _key, upload_id, _path, _parts_num,
                        _part_size, _last_size, already_exist_parts):
            self.assertEqual(upload_id, 'upload-existing')
            already_exist_parts[1] = 'etag-1'
            return True

        client._check_all_upload_parts = check_parts
        client.create_multipart_upload = lambda **_kwargs: self.fail(
            'resumable upload must not create a new MPU')

        state_lock = threading.Lock()
        active = [0]
        max_active = [0]
        uploaded_parts = []
        md5_flags = []

        def upload_part(*args, **kwargs):
            part_number = kwargs.get('PartNumber')
            if part_number is None:
                part_number = args[3]
            md5_flags.append(args[5])
            with state_lock:
                active[0] += 1
                max_active[0] = max(max_active[0], active[0])
                uploaded_parts.append(part_number)
            time.sleep(0.02)
            with state_lock:
                active[0] -= 1
            return {'ETag': 'etag-%d' % part_number}

        client.upload_part = upload_part
        completed = []

        def complete_multipart_upload(**kwargs):
            completed.append(kwargs)
            return {'ETag': 'final-etag'}

        client.complete_multipart_upload = complete_multipart_upload
        result = client.upload_file(
            Bucket=RAPID_BUCKET,
            Key='large.bin',
            LocalFilePath=source_path,
            PartSize=1,
            MAXThread=3,
            EnableMD5=True,
            progress_callback=lambda *_args: None,
            ForbidOverwrite='true')

        self.assertEqual(result['ETag'], 'final-etag')
        self.assertEqual(len(list_calls), 1)
        self.assertNotIn('Prefix', list_calls[0])
        self.assertNotIn(1, uploaded_parts)
        self.assertEqual(sorted(uploaded_parts), [2, 3, 4])
        self.assertEqual(md5_flags, [True, True, True])
        self.assertGreaterEqual(max_active[0], 2)
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0]['UploadId'], 'upload-existing')
        self.assertEqual(completed[0]['ForbidOverwrite'], 'true')
        self.assertEqual(
            [part['PartNumber'] for part in
             completed[0]['MultipartUpload']['Part']],
            [1, 2, 3, 4])

    def test_rapid_high_level_rejects_unsupported_options_before_io(self):
        client = _client()
        client.send_request = lambda *_args, **_kwargs: self.fail('unexpected network')
        source = {'Bucket': RAPID_BUCKET, 'Region': 'ap-guangzhou', 'Key': 'source'}

        class UnreadableBody(object):
            def read(self, _size):
                raise AssertionError('body must not be consumed')

        for options in ({'VersionId': 'old'}, {'Callback': 'callback'},
                        {'CallbackVar': 'vars'}, {'ForbidOverwrite': 'yes'},
                        {'Metadata': {'X-Cos-Callback': 'callback'}},
                        {'Metadata': {'x-cos-forbid-overwrite': 'yes'}}):
            with self.assertRaises(CosClientError):
                client.upload_file(Bucket=RAPID_BUCKET, Key='key',
                                   LocalFilePath=os.path.join(self.temp_dir, 'missing'), **options)
            with self.assertRaises(CosClientError):
                client.upload_file_from_buffer(Bucket=RAPID_BUCKET, Key='key',
                                               Body=UnreadableBody(), **options)
            with self.assertRaises(CosClientError):
                client.copy(Bucket=RAPID_BUCKET, Key='key', CopySource=source, **options)

    def test_rapid_forbid_overwrite_reaches_initiate_and_commit(self):
        # Both MPU stages carry the header. This model applies the current
        # Rapid object-layer overwrite check at commit; it does not model CAM.
        for operation in ('upload_file', 'upload_file_from_buffer', 'copy'):
            for multipart in (False, True):
                for flag, header_alias in (('true', False), ('false', False),
                                           (None, False), ('true', True),
                                           ('false', True), (b'true', False)):
                    client = _client()
                    payload = b'x' * (1024 * 1024 + 1 if multipart else 10)
                    source_path = os.path.join(self.temp_dir, 'forbid.bin')
                    with open(source_path, 'wb') as stream:
                        stream.write(payload)
                    client._session_provider.get_credential = lambda *_args, **_kwargs: SessionCredential(
                        'session-ak', 'session-sk', 'session-token',
                        datetime.utcnow() + timedelta(hours=1))
                    client._get_resumable_uploadid = lambda *_args: None
                    client._conf._copy_part_threshold_size = 1024 * 1024
                    stored = [b'original']
                    initiated = []
                    commits = []
                    expected_flag = to_unicode(flag) if flag is not None else None

                    def request(method, url, **kwargs):
                        params = kwargs.get('params', {})
                        headers = requests.structures.CaseInsensitiveDict(kwargs.get('headers', {}))
                        value = headers.get('x-cos-forbid-overwrite')
                        value = to_unicode(value) if value is not None else None
                        response = requests.Response()
                        response.status_code = 200
                        response._content = b''
                        if method == 'HEAD':
                            response.headers['Content-Length'] = str(len(payload))
                            response.headers['x-cos-storage-class'] = 'RAPID'
                        elif 'uploads' in params:
                            self.assertEqual('x-cos-forbid-overwrite' in headers, flag is not None)
                            initiated.append(value)
                            response._content = (
                                b'<InitiateMultipartUploadResult><UploadId>upload</UploadId>'
                                b'</InitiateMultipartUploadResult>')
                        elif 'partNumber' in params:
                            response.headers['ETag'] = 'part-etag'
                            response._content = b'<CopyPartResult><ETag>part-etag</ETag></CopyPartResult>'
                        elif method == 'DELETE':
                            response.status_code = 204
                        else:
                            self.assertEqual('x-cos-forbid-overwrite' in headers, flag is not None)
                            commits.append(value)
                            if value == 'true':
                                response.status_code = 409
                                response._content = (
                                    b'<Error><Code>ObjectAlreadyExists</Code>'
                                    b'<Message>exists</Message></Error>')
                            else:
                                stored[0] = b'replaced'
                                response.headers['ETag'] = 'final-etag'
                                response._content = b'<Result><ETag>final-etag</ETag></Result>'
                        return response

                    client._session.request = request
                    options = {'Bucket': RAPID_BUCKET, 'Key': 'destination', 'PartSize': 1}
                    if flag is not None:
                        if header_alias:
                            options['Metadata'] = {'X-Cos-Forbid-Overwrite': flag}
                        else:
                            options['ForbidOverwrite'] = flag
                    if operation == 'copy':
                        options['CopySource'] = {
                            'Bucket': RAPID_BUCKET, 'Key': 'source', 'Region': 'ap-guangzhou'}
                    elif operation == 'upload_file':
                        options['LocalFilePath'] = source_path
                    else:
                        options['Body'] = io.BytesIO(payload)
                    try:
                        if expected_flag == 'true':
                            with self.assertRaises(CosServiceError):
                                getattr(client, operation)(**options)
                            self.assertEqual(stored[0], b'original')
                        else:
                            getattr(client, operation)(**options)
                            self.assertEqual(stored[0], b'replaced')
                        self.assertEqual(initiated, [expected_flag] if multipart else [])
                        self.assertEqual(commits, [expected_flag])
                    finally:
                        client._session.close()

    def test_upload_file_forbid_overwrite_on_resume_and_restart(self):
        source_path = os.path.join(self.temp_dir, 'resume-forbid.bin')
        with open(source_path, 'wb') as stream:
            stream.write(b'x' * (1024 * 1024 + 1))
        for resumable in (True, False):
            for flag in ('true', 'false', None):
                client = _client()
                client._session_provider.get_credential = lambda *_args, **_kwargs: SessionCredential(
                    'session-ak', 'session-sk', 'session-token',
                    datetime.utcnow() + timedelta(hours=1))
                initiated = []
                completed = []
                uploaded = []

                def check_parts(_bucket, _key, upload_id, _path, _count,
                                _part_size, _last_size, existing):
                    self.assertEqual(upload_id, 'old-upload')
                    # A failed validation may already have matched some parts.
                    existing[1] = 'part-etag'
                    return resumable

                client._check_all_upload_parts = check_parts

                def request(method, url, **kwargs):
                    params = kwargs.get('params', {})
                    headers = requests.structures.CaseInsensitiveDict(kwargs.get('headers', {}))
                    value = headers.get('x-cos-forbid-overwrite')
                    value = to_unicode(value) if value is not None else None
                    response = requests.Response()
                    response.status_code = 200
                    response._content = b''
                    if method == 'GET' and 'uploads' in params:
                        # The old MPU listing does not reveal its Initiate header.
                        response._content = (
                            b'<ListMultipartUploadsResult><IsTruncated>false</IsTruncated>'
                            b'<Upload><Key>resume.bin</Key><UploadId>old-upload</UploadId></Upload>'
                            b'</ListMultipartUploadsResult>')
                    elif method == 'POST' and 'uploads' in params:
                        self.assertEqual('x-cos-forbid-overwrite' in headers, flag is not None)
                        initiated.append(value)
                        response._content = (
                            b'<InitiateMultipartUploadResult><UploadId>new-upload</UploadId>'
                            b'</InitiateMultipartUploadResult>')
                    elif method == 'PUT' and 'partNumber' in params:
                        uploaded.append((to_unicode(params['uploadId']), int(params['partNumber'])))
                        response.headers['ETag'] = 'part-etag'
                    elif method == 'POST' and 'uploadId' in params:
                        self.assertEqual('x-cos-forbid-overwrite' in headers, flag is not None)
                        completed.append((to_unicode(params['uploadId']), value))
                        response._content = (
                            b'<CompleteMultipartUploadResult><ETag>final-etag</ETag>'
                            b'</CompleteMultipartUploadResult>')
                    else:
                        self.fail('unexpected request: %s %r' % (method, params))
                    return response

                client._session.request = request
                options = {} if flag is None else {'ForbidOverwrite': flag}
                try:
                    client.upload_file(Bucket=RAPID_BUCKET, Key='resume.bin',
                                       LocalFilePath=source_path, PartSize=1, **options)
                    upload_id = 'old-upload' if resumable else 'new-upload'
                    self.assertEqual(initiated, [] if resumable else [flag])
                    self.assertEqual(completed, [(upload_id, flag)])
                    self.assertEqual(sorted(uploaded), [(upload_id, 2)] if resumable else [
                        (upload_id, 1), (upload_id, 2)])
                finally:
                    client._session.close()

    def test_download_file_resumes_range_workers_after_interruption(self):
        client = _client()
        payload = (b'advanced-download-' * 220000)[:3 * 1024 * 1024 + 47]
        crc64 = crcmod.mkCrcFun(
            0x142F0E1EBA9EA3693, initCrc=0,
            xorOut=0xffffffffffffffff, rev=True)
        destination = os.path.join(self.temp_dir, 'download.bin')
        record_dir = os.path.join(self.temp_dir, 'records')
        client.head_object = lambda *_args, **_kwargs: {
            'Content-Length': str(len(payload)),
            'Last-Modified': 'Thu, 04 Sep 2026 00:00:00 GMT',
            'ETag': 'download-etag',
            # head_object already supplies the lowercase alias for Rapid responses.
            'x-cos-hash-crc64ecma': str(crc64(payload)),
        }

        state_lock = threading.Lock()
        calls = [0]
        active = [0]
        max_active = [0]

        def get_object(*_args, **kwargs):
            raw_range = kwargs.get('Range')
            self.assertTrue(raw_range.startswith('bytes='))
            start, end = [
                int(value) for value in raw_range[6:].split('-', 1)]
            with state_lock:
                calls[0] += 1
                call_number = calls[0]
                active[0] += 1
                max_active[0] = max(max_active[0], active[0])
            time.sleep(0.02)
            with state_lock:
                active[0] -= 1
            if call_number == 2:
                raise CosClientError('injected range interruption')
            return {'Body': _RangeBody(payload[start:end + 1])}

        client.get_object = get_object
        with self.assertRaises(CosClientError):
            client.download_file(
                Bucket=RAPID_BUCKET,
                Key='large.bin',
                DestFilePath=destination,
                PartSize=1,
                MAXThread=3,
                EnableCRC=True,
                DumpRecordDir=record_dir)
        self.assertTrue(os.listdir(record_dir))

        calls_after_failure = calls[0]
        client.download_file(
            Bucket=RAPID_BUCKET,
            Key='large.bin',
            DestFilePath=destination,
            PartSize=1,
            MAXThread=3,
            EnableCRC=True,
            DumpRecordDir=record_dir)
        with open(destination, 'rb') as downloaded:
            self.assertEqual(downloaded.read(), payload)
        self.assertEqual(calls[0] - calls_after_failure, 1)
        self.assertGreaterEqual(max_active[0], 2)
        self.assertEqual(os.listdir(record_dir), [])

    def test_download_file_consumes_mixed_case_head_metadata(self):
        client = _client()
        payload = b'metadata-download-' * 90000
        crc64 = crcmod.mkCrcFun(0x142F0E1EBA9EA3693, initCrc=0,
                                xorOut=0xffffffffffffffff, rev=True)
        response = requests.Response()
        response.status_code = 200
        response.headers = requests.structures.CaseInsensitiveDict({
            'content-length': str(len(payload)),
            'LAST-MODIFIED': 'Fri, 04 Sep 2026 00:00:00 GMT',
            'eTAG': '"download-etag"',
            'X-Cos-Hash-Crc64ecma': str(crc64(payload)),
        })
        client.send_request = lambda *_args, **_kwargs: response

        def get_object(*_args, **kwargs):
            start, end = [int(value) for value in kwargs['Range'][6:].split('-', 1)]
            return {'Body': _RangeBody(payload[start:end + 1])}

        client.get_object = get_object
        destination = os.path.join(self.temp_dir, 'mixed-headers.bin')
        records = os.path.join(self.temp_dir, 'mixed-records')
        client.download_file(Bucket=RAPID_BUCKET, Key='mixed.bin', DestFilePath=destination,
                             PartSize=1, MAXThread=2, EnableCRC=True, DumpRecordDir=records)
        with open(destination, 'rb') as stream:
            self.assertEqual(stream.read(), payload)
        self.assertEqual(os.listdir(records), [])

        # Keep CRC mismatch detection on the real Rapid header-normalization path.
        response.headers['X-Cos-Hash-Crc64ecma'] = str(crc64(payload) ^ 1)
        with self.assertRaises(CosClientError) as caught:
            client.download_file(Bucket=RAPID_BUCKET, Key='mixed.bin', DestFilePath=destination,
                                 PartSize=1, MAXThread=2, EnableCRC=True, DumpRecordDir=records)
        self.assertIn('mismatch with cos', str(caught.exception))

    def test_download_crc_preserves_missing_header_error(self):
        client = _client()
        payload = b'crc-header-required-' * 70000
        destination = os.path.join(self.temp_dir, 'missing-crc.bin')
        client.head_object = lambda *_args, **_kwargs: {
            'Content-Length': str(len(payload)),
            'Last-Modified': 'Thu, 04 Sep 2026 00:00:00 GMT',
            'ETag': 'missing-crc-etag',
        }

        def get_object(*_args, **kwargs):
            start, end = [
                int(value) for value in kwargs['Range'][6:].split('-', 1)]
            return {'Body': _RangeBody(payload[start:end + 1])}

        client.get_object = get_object
        try:
            client.download_file(
                Bucket=RAPID_BUCKET,
                Key='missing-crc.bin',
                DestFilePath=destination,
                PartSize=1,
                MAXThread=2,
                EnableCRC=True,
                DumpRecordDir=os.path.join(self.temp_dir, 'missing-crc-record'))
            self.fail('EnableCRC must reject a missing HeadObject CRC64 header')
        except KeyError as error:
            self.assertEqual(error.args, ('x-cos-hash-crc64ecma',))


if __name__ == '__main__':
    unittest.main()
