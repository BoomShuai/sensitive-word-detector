import http.client
import json
import threading
import unittest
from sensitive_detector import Detector
from sensitive_detector.server import LocalServer


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = LocalServer(("127.0.0.1", 0), Detector())
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=5)
        if cls.thread.is_alive(): raise RuntimeError("server failed to stop")

    def request(self, method, path, payload=None, headers=None, raw=None):
        headers = dict(headers or {})
        if payload is not None: raw = json.dumps(payload, ensure_ascii=False).encode()
        if raw is not None: headers.setdefault("Content-Type", "application/json")
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request(method, path, body=raw, headers=headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally: connection.close()

    def test_ui_and_static_headers(self):
        for path in ("/", "/style.css", "/app.js"):
            status, headers, body = self.request("GET", path)
            self.assertEqual(status, 200); self.assertTrue(body)
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_api(self):
        status, _, body = self.request("POST", "/api/analyze", {"texts": ["示例敏感词", "谦受益满招损"]})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["summary"]["review"], 1)
        status, _, body = self.request("GET", "/api/health")
        self.assertEqual(status, 200); self.assertFalse(json.loads(body)["stores_input"])

    def test_bad_json_and_schema(self):
        for payload in ([], {}, {"texts": [None]}, {"texts": ["正常"], "rules": None}, {"texts": ["正常"], "extra": True}):
            self.assertEqual(self.request("POST", "/api/analyze", payload)[0], 400)
        self.assertEqual(self.request("POST", "/api/analyze", raw=b"{")[0], 400)

    def test_origin_host_and_cross_site_protection(self):
        for headers in ({"Origin": "https://example.test"}, {"Host": "example.test"}, {"Sec-Fetch-Site": "cross-site"}):
            self.assertEqual(self.request("POST", "/api/analyze", {"texts": ["正常"]}, headers)[0], 403)
        self.assertEqual(self.request("GET", "/", headers={"Host": "example.test"})[0], 403)

    def test_limits_and_unsupported_routes(self):
        self.assertEqual(self.request("POST", "/api/analyze", raw=b"x" * (256 * 1024 + 1))[0], 413)
        self.assertEqual(self.request("POST", "/api/analyze", raw=b"{}", headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("GET", "/../pyproject.toml")[0], 404)
        self.assertEqual(self.request("OPTIONS", "/api/analyze")[0], 501)

    def test_custom_rules_remain_request_local(self):
        rules = {"version": 1, "words": [{"id": "private", "text": "请求内测试词"}], "quotes": []}
        value = {"texts": ["请求内测试词"], "rules": rules}
        self.assertEqual(json.loads(self.request("POST", "/api/analyze", value)[2])["summary"]["review"], 1)
        self.assertEqual(json.loads(self.request("POST", "/api/analyze", {"texts": ["请求内测试词"]})[2])["summary"]["review"], 0)

    def test_non_loopback_binding_is_rejected(self):
        with self.assertRaises(ValueError): LocalServer(("0.0.0.0", 0), Detector())


if __name__ == "__main__": unittest.main()
