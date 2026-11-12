"""Loopback-only HTTP interface with no request logging or text persistence."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit
from .engine import Detector

MAX_BODY = 256 * 1024
WEB = Path(__file__).parent / "web"
STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8")}


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, detector):
        if address[0] != "127.0.0.1":
            raise ValueError("服务仅允许绑定 127.0.0.1")
        self.detector = detector
        self.compute_lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(4)
        super().__init__(address, Handler)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        pass


class Handler(BaseHTTPRequestHandler):
    server_version = "LocalTextReview"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(8)

    def log_message(self, *args):
        pass

    def send_error(self, code, message=None, explain=None):
        self.reply(code, {"error": "请求被拒绝"})

    def reply(self, status, value, content_type="application/json; charset=utf-8"):
        data = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        self.wfile.write(data)

    def local_request(self):
        port = self.server.server_address[1]
        hosts = {"127.0.0.1:%s" % port, "localhost:%s" % port}
        origins = {"http://" + host for host in hosts}
        if self.headers.get_all("Host", []) not in [[host] for host in hosts]:
            return False
        origin = self.headers.get_all("Origin", [])
        return (not origin or len(origin) == 1 and origin[0] in origins) and self.headers.get("Sec-Fetch-Site") != "cross-site"

    def do_GET(self):
        if not self.local_request():
            self.reply(403, {"error": "仅接受本机页面请求"})
            return
        path = urlsplit(self.path).path
        if path in STATIC:
            file_name, content_type = STATIC[path]
            self.reply(200, (WEB / file_name).read_bytes(), content_type)
        elif path == "/api/health":
            self.reply(200, {"status": "ok", "backend": self.server.detector.backend, "stores_input": False})
        elif path == "/api/rules":
            self.reply(200, self.server.detector.rules)
        else:
            self.reply(404, {"error": "路径不存在"})

    def do_POST(self):
        if not self.local_request():
            self.reply(403, {"error": "请求来源不允许"})
            return
        if urlsplit(self.path).path != "/api/analyze":
            self.reply(404, {"error": "路径不存在"})
            return
        if self.headers.get_content_type() != "application/json":
            self.reply(415, {"error": "仅接受 application/json"})
            return
        lengths = self.headers.get_all("Content-Length", [])
        if self.headers.get("Transfer-Encoding") or len(lengths) != 1 or not lengths[0].isdigit():
            self.reply(400, {"error": "需要单个有效 Content-Length"})
            return
        size = int(lengths[0])
        if not 0 < size <= MAX_BODY:
            self.reply(413, {"error": "请求体为空或超过 256 KiB"})
            return
        try:
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError("请求体不完整")
            value = json.loads(raw.decode("utf-8"))
            if not isinstance(value, dict) or set(value) - {"texts", "rules"}:
                raise ValueError("需要含 texts 数组的 JSON 对象")
            detector = self.server.detector
            if "rules" in value:
                if detector.backend != "rules":
                    raise ValueError("语义模式请通过启动参数加载词库")
                from .rules import validate_rules
                detector = Detector(validate_rules(value["rules"]))
            with self.server.compute_lock:
                result = detector.analyze_batch(value.get("texts"))
            self.reply(200, result)
        except (UnicodeError, ValueError) as error:
            self.reply(400, {"error": str(error) if isinstance(error, ValueError) and not isinstance(error, json.JSONDecodeError) else "JSON 格式或编码无效"})
        except RuntimeError:
            self.reply(503, {"error": "本地模型推理失败，未自动切换后端"})


def serve_local(detector, port=8765):
    if not 1 <= port <= 65535:
        raise ValueError("端口必须在 1–65535 范围")
    with LocalServer(("127.0.0.1", port), detector) as server:
        print("本地工作台：http://127.0.0.1:%d/（Ctrl+C 停止）" % server.server_address[1])
        print("输入文本仅在内存处理，不记录访问日志，不自动保存结果。")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
