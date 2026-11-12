import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from sensitive_detector import Detector
from sensitive_detector.algorithms.semantic import SemanticBackend


class SemanticTests(unittest.TestCase):
    def test_missing_model_does_not_attempt_download(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError): SemanticBackend(Path(folder) / "missing")

    def test_semantic_requires_explicit_path(self):
        with self.assertRaises(ValueError): Detector(backend="semantic")

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "optional numpy not installed")
    def test_local_only_configuration_and_failure_is_visible(self):
        import numpy as np
        calls = []
        class Model:
            def __init__(self, *args, **kwargs): calls.append(kwargs)
            def encode(self, texts, **kwargs): return np.array([[1.0, 0.0] for text in texts])
        with tempfile.TemporaryDirectory() as folder, patch.dict(sys.modules, {"sentence_transformers": types.SimpleNamespace(SentenceTransformer=Model)}):
            detector = Detector(backend="semantic", model_dir=folder)
            self.assertEqual(detector.analyze("与引用有关的意译候选")["backend"], "semantic")
            self.assertTrue(calls[0]["local_files_only"])
            self.assertFalse(calls[0]["trust_remote_code"])
            with patch.object(detector.quote_detector.backend._model, "encode", side_effect=RuntimeError("failure")):
                with self.assertRaises(RuntimeError): detector.analyze("谦受益满招损")


if __name__ == "__main__": unittest.main()
