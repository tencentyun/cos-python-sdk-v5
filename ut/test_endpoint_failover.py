# -*- coding=utf-8
"""Offline regressions for switching to the backup COS endpoint."""

import unittest

import requests

import qcloud_cos.cos_client as cos_client_module
from qcloud_cos import CosClientError, CosConfig, CosS3Client
from qcloud_cos.cos_comm import switch_hostname_for_url


HOST = 'example-125000000.cos.ap-chengdu.myqcloud.com'
BACKUP_HOST = 'example-125000000.cos.ap-chengdu.tencentcos.cn'


class TestEndpointFailover(unittest.TestCase):
    def test_preserves_path_parameters_query_and_fragment(self):
        suffix = '/archive/{0};name={0}?source={0}&encoded=%2F%2B#{0}'.format(HOST)
        self.assertEqual(
            switch_hostname_for_url('https://' + HOST + suffix),
            'https://' + BACKUP_HOST + suffix)

    def test_preserves_userinfo_and_port(self):
        authority = HOST + ':password@' + HOST + ':8443'
        expected = HOST + ':password@' + BACKUP_HOST + ':8443'
        self.assertEqual(
            switch_hostname_for_url('https://' + authority + '/key'),
            'https://' + expected + '/key')

    def test_uppercase_hostname(self):
        self.assertEqual(
            switch_hostname_for_url('https://' + HOST.upper() + '/' + HOST),
            'https://' + BACKUP_HOST + '/' + HOST)

    def test_unchanged_endpoints(self):
        for host in (BACKUP_HOST, 'cos.ap-chengdu.myqcloud.com',
                     'service.cos.myqcloud.com', 'example-125000000.file.myqcloud.com',
                     'localhost:8000', '[::1]:8000'):
            url = 'https://' + host + '/' + HOST + '?source=' + HOST
            self.assertEqual(switch_hostname_for_url(url), url)

    def test_second_switch_is_unchanged(self):
        expected = 'https://' + BACKUP_HOST + '/' + HOST
        switched = switch_hostname_for_url('https://' + HOST + '/' + HOST)
        self.assertEqual(switch_hostname_for_url(switched), expected)

    def test_empty_url_rejected(self):
        with self.assertRaises(CosClientError):
            switch_hostname_for_url('')

    def _check_client_retry(self, first_status=None):
        original_sleep = cos_client_module.time.sleep
        self.addCleanup(setattr, cos_client_module.time, 'sleep', original_sleep)
        cos_client_module.time.sleep = lambda delay: None
        session = requests.Session()
        self.addCleanup(session.close)
        config = CosConfig(Region='ap-chengdu', Anonymous=True,
                           AutoSwitchDomainOnRetry=True)
        client = CosS3Client(config, retry=1, session=session)
        suffix = '/backups/' + HOST + '/data.csv?source=' + HOST
        attempts = []

        def transport(method, url, timeout, **kwargs):
            attempts.append(url)
            response = requests.Response()
            response.status_code = 200
            if len(attempts) == 1:
                if first_status is None:
                    raise requests.ConnectionError('synthetic connection failure')
                response.status_code = first_status
            return response

        client._http_once = transport
        result = client.send_request('GET', 'https://' + HOST + suffix)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(attempts, ['https://' + HOST + suffix,
                                    'https://' + BACKUP_HOST + suffix])

    def test_connection_error_retry_keeps_object_path(self):
        self._check_client_retry()

    def test_server_error_retry_keeps_object_path(self):
        self._check_client_retry(503)

    def test_redirect_retry_keeps_object_path(self):
        self._check_client_retry(302)


if __name__ == '__main__':
    unittest.main()
