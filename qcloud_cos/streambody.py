# -*- coding=utf-8
import requests


class StreamBody():
    def __init__(self, rt):
        self._rt = rt

    def get_raw_stream(self):
        return self._rt.raw

    def get_stream(self, chunk_size=1024):
        return self._rt.iter_content(chunk_size=chunk_size)

    def get_stream_to_file(self, file_name):
        if 'Content-Length' in self._rt.headers:
            content_len = int(self._rt.headers['Content-Length'])
        else:
            raise IOError("download failed without Content-Length header")

        file_len = 0
        with open(file_name, 'wb') as fp:
            for chunk in self._rt.iter_content(chunk_size=1024):
                if chunk:
                    file_len += len(chunk)
                    fp.write(chunk)
            fp.flush()
            fp.close()
        if file_len != content_len:
            raise IOError("download failed with incomplete file")
