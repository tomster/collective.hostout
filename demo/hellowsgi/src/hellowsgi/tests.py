import unittest
from webob import Request
from main import MainApplication

class TestMainApplication(unittest.TestCase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self.app = MainApplication()

    def test_root_output(self):
        request = Request.blank('/')
        expected_body = 'Powered by collective.hostout!'
        expected_status = '200 OK'
        status, headers, body = request.call_application(self.app)
        self.assertEqual(status, expected_status)
        self.assertEqual(expected_body, body[0])
