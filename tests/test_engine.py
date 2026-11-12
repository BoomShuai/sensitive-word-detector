import copy
import socket
import unittest
from unittest.mock import patch
from sensitive_detector import Detector
from sensitive_detector.rules import load_rules, validate_rules
from sensitive_detector.algorithms.v1 import HybridDetector
from sensitive_detector.algorithms.v2 import V2HybridDetector


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.detector = Detector()

    def test_default_labels(self):
        for text, label in [("今天适合出门散步。", 0), ("谦受益满招害", 1), ("谦受益，满招损。", 2)]:
            with self.subTest(text=text):
                self.assertEqual(self.detector.analyze(text)["label"], label)

    def test_warning_wins_over_correct_quote_in_different_sentence(self):
        value = self.detector.analyze("谦受益满招损。纸上得来终觉浅绝知此事须躬行。")
        self.assertTrue(value["needs_review"])
        self.assertEqual({f["label"] for f in value["findings"]}, {1, 2})

    def test_context_in_one_sentence_cannot_suppress_warning_in_another(self):
        value = self.detector.analyze("这里将生态资源转化为财富。谦受益满招害。")
        self.assertEqual(value["label"], 1)

    def test_keyword_cannot_be_suppressed_by_quote_context(self):
        value = self.detector.analyze("示例敏感词。谦受益满招损。")
        self.assertEqual(value["label"], 1)
        self.assertIn("keyword", {f["kind"] for f in value["findings"]})

    def test_normalization_and_original_offsets(self):
        rules = {"version": 1, "words": [{"id": "latin", "text": "bad", "ignore_separators": True}], "quotes": []}
        text = "甲Ｂ-Ａ\u200bＤ乙 bad"
        findings = Detector(rules).analyze(text)["findings"]
        self.assertEqual(len(findings), 2)
        for finding in findings:
            self.assertEqual(text[finding["start"]:finding["end"]], finding["matched"])
        self.assertEqual(findings[0]["matched"], "Ｂ-Ａ\u200bＤ")

    def test_separators_are_configurable(self):
        rules = {"version": 1, "words": [{"id": "latin", "text": "bad"}], "quotes": []}
        self.assertEqual(Detector(rules).analyze("b-a-d")["label"], 0)

    def test_custom_quote_overrides_default(self):
        rules = {"version": 1, "words": [], "quotes": [{"id": "custom", "text": "认真检查再提交", "anchors": ["认真检查", "提交"]}]}
        self.assertEqual(Detector(rules).analyze("认真检查再提交")["label"], 2)
        self.assertEqual(Detector(rules).analyze("认真检查才提交")["label"], 1)
        self.assertEqual(Detector(rules).analyze("谦受益满招损")["label"], 0)

    def test_batch_summary(self):
        value = self.detector.analyze_batch(["示例敏感词", "谦受益满招损", "今天散步"])
        self.assertEqual(value["summary"], {"total": 3, "review": 1, "quoted": 1, "unmatched": 1})

    def test_invalid_input_limits(self):
        for value in [None, "text", [], [None], [" "], ["x" * 8001], ["x"] * 101, ["x" * 8000] * 5]:
            with self.subTest(value_type=type(value).__name__), self.assertRaises(ValueError):
                self.detector.analyze_batch(value)
        with self.assertRaises(ValueError):
            self.detector.analyze("长" * 257)

    def test_invalid_rules(self):
        base = load_rules()
        variants = [None, [], {"version": 2}, {"version": 1, "words": [], "quotes": []}]
        duplicate = copy.deepcopy(base); duplicate["words"].append(duplicate["words"][0]); variants.append(duplicate)
        anchor = copy.deepcopy(base); anchor["quotes"][0]["anchors"] = ["不在引用中的词"]; variants.append(anchor)
        blank = copy.deepcopy(base); blank["words"][0]["text"] = "---"; variants.append(blank)
        for value in variants:
            with self.subTest(kind=type(value).__name__), self.assertRaises(ValueError):
                validate_rules(value)

    def test_rules_do_not_open_network_connections(self):
        with patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")):
            self.assertEqual(Detector().analyze("谦受益满招损")["label"], 2)

    def test_prior_generations_are_callable_without_numpy(self):
        for detector in (HybridDetector(), V2HybridDetector()):
            self.assertEqual(detector.predict(["今天散步", "谦受益满招损"]), [0, 2])


if __name__ == "__main__":
    unittest.main()
