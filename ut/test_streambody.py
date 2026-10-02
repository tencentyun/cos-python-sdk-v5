import io
import os
import shutil
import tempfile
import unittest

from qcloud_cos.streambody import StreamBody


class Response(object):
    def __init__(self, data, length=None):
        self.headers = {'Content-Length': str(len(data) if length is None else length)}
        self.raw = io.BytesIO(data)

    def iter_content(self, chunk_size):
        while True:
            chunk = self.raw.read(chunk_size)
            if not chunk:
                return
            yield chunk


class TestStreamBody(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.directory)

    def test_long_destination_name(self):
        destination = os.path.join(self.directory, 'a' * 240)
        StreamBody(Response(b'contents')).get_stream_to_file(destination)
        with open(destination, 'rb') as source:
            self.assertEqual(source.read(), b'contents')
        self.assertEqual(os.listdir(self.directory), ['a' * 240])

    def test_incomplete_download_preserves_destination(self):
        destination = os.path.join(self.directory, 'a' * 240)
        with open(destination, 'wb') as target:
            target.write(b'original')
        with self.assertRaises(IOError) as raised:
            StreamBody(Response(b'short', length=10)).get_stream_to_file(destination)
        self.assertEqual(str(raised.exception), 'download failed with incomplete file')
        with open(destination, 'rb') as source:
            self.assertEqual(source.read(), b'original')
        self.assertEqual(os.listdir(self.directory), ['a' * 240])

    def test_disabled_temporary_file(self):
        destination = os.path.join(self.directory, 'a' * 240)
        StreamBody(Response(b'contents')).get_stream_to_file(destination, disable_tmp_file=True)
        with open(destination, 'rb') as source:
            self.assertEqual(source.read(), b'contents')
