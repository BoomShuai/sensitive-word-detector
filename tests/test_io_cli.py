import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from sensitive_detector.cli import main
from sensitive_detector.io import load_texts


class IOTests(unittest.TestCase):
    def test_formats_and_quotes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixtures = {"input.txt": "谦受益满招损\n今天散步\n", "input.csv": 'text,tag\n"谦受益,满招损",synthetic\n',
                        "input.jsonl": '{"text":"谦受益满招损"}\n"今天散步"\n'}
            for name, content in fixtures.items():
                path = root / name; path.write_text(content, encoding="utf-8")
                self.assertGreater(len(load_texts(str(path))), 0)
            self.assertEqual(load_texts(str(root / "input.csv")), ["谦受益,满招损"])

    def test_invalid_imports(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, content in {"x.csv": "other\nvalue", "x.jsonl": '{"wrong":true}', "x.txt": ""}.items():
                path = root / name; path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError): load_texts(str(path))
            path = root / "x.txt"; path.write_bytes(b"x" * (1024 * 1024 + 1))
            with self.assertRaises(ValueError): load_texts(str(path))
            path.write_bytes(b"\xff")
            with self.assertRaises(ValueError): load_texts(str(path))

    def test_cli_json_and_no_output_overwrite(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["scan", "--text", "示例敏感词"]), 0)
        self.assertEqual(json.loads(output.getvalue())["summary"]["review"], 1)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "result.json"
            self.assertEqual(main(["scan", "--text", "今天散步", "--output", str(path)]), 0)
            previous = path.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["scan", "--text", "示例敏感词", "--output", str(path)]), 2)
            self.assertEqual(path.read_bytes(), previous)


if __name__ == "__main__": unittest.main()
