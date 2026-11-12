"""Dictionary matching plus explainable, sentence-local quotation review."""
import re
from .algorithms.v3 import V3HybridDetector
from .rules import load_rules, normalize, validate_rules

MAX_TEXT = 8000
MAX_BATCH = 100
MAX_BATCH_CHARS = 32000
SENTENCE_SIZE = 256
LABELS = {0: "未命中", 1: "建议复核", 2: "引用命中"}


def validate_texts(texts):
    if not isinstance(texts, list) or not 1 <= len(texts) <= MAX_BATCH:
        raise ValueError("每批需要 1–100 条文本")
    if any(not isinstance(t, str) or not t.strip() or len(t) > MAX_TEXT for t in texts):
        raise ValueError("文本须非空且每条不超过 8000 字符")
    if sum(map(len, texts)) > MAX_BATCH_CHARS:
        raise ValueError("每批文本总长不能超过 32000 字符")
    return texts


class Detector:
    def __init__(self, rules=None, backend="rules", model_dir=None):
        self.rules = validate_rules(rules) if rules is not None else load_rules()
        if backend not in {"rules", "semantic"}:
            raise ValueError("backend 只能是 rules 或 semantic")
        self.backend = backend
        self.quotes = self.rules["quotes"]
        templates = [(normalize(q["text"])[0], [normalize(a)[0] for a in q["anchors"]]) for q in self.quotes]
        if backend == "semantic":
            if not model_dir or not self.quotes:
                raise ValueError("语义模式需要本地模型和引用规则")
            from .algorithms.semantic import SemanticBackend
            from .algorithms.v4 import V4HybridDetector
            model = SemanticBackend(model_dir)
            self.quote_detector = V4HybridDetector(backend=model, templates=templates)
        else:
            self.quote_detector = V3HybridDetector()
        self.quote_detector.sensitive_templates = templates

    def analyze(self, text):
        validate_texts([text])
        findings = []
        for rule in self.rules["words"]:
            compact = rule["ignore_separators"]
            normalized, positions = normalize(text, compact)
            needle = normalize(rule["text"], compact)[0]
            offset = 0
            while True:
                index = normalized.find(needle, offset)
                if index < 0:
                    break
                start, end = positions[index], positions[index + len(needle) - 1] + 1
                findings.append({"rule_id": rule["id"], "kind": "keyword", "label": 1,
                                 "start": start, "end": end, "matched": text[start:end], "reference": rule["text"],
                                 "reason": "词库命中：" + rule["category"]})
                offset = index + len(needle)
        for part in re.finditer(r"[^。！？!?；;\n]+", text):
            if len(part.group()) > SENTENCE_SIZE:
                raise ValueError("单个句段不能超过 256 字符，请按句号或换行分段")
            normalized, _ = normalize(part.group())
            if not normalized:
                continue
            sims = None
            if self.backend == "semantic":
                emb = self.quote_detector.backend.encode_batch([normalized])
                sims = (emb[0] @ self.quote_detector._temp_embs.T).tolist()
            for index, (rule, (template, anchors)) in enumerate(zip(self.quotes, self.quote_detector.sensitive_templates)):
                passes, anchor_hit = self.quote_detector._coarse_pass(normalized, template, anchors)
                if sims is not None:
                    passes = passes or sims[index] >= self.quote_detector.backend.sim_threshold
                if not passes:
                    continue
                args = (normalized, template, anchors, anchor_hit)
                label = self.quote_detector._classify_fine(*args, **({"sim": sims[index]} if sims is not None else {}))
                if not label:
                    continue
                findings.append({"rule_id": rule["id"], "kind": "quote", "label": int(label),
                                 "start": part.start(), "end": part.end(), "matched": part.group(), "reference": rule["text"],
                                 "reason": "引用近似或改写，建议人工复核" if label == 1 else "引用或上下文规则命中，仍需结合语境判断"})
        label = 1 if any(f["label"] == 1 for f in findings) else 2 if findings else 0
        return {"text": text, "label": label, "status": LABELS[label], "needs_review": label == 1,
                "backend": self.backend, "findings": findings,
                "note": "未命中不代表内容合规；规则与语义结果都需要结合使用场景复核。"}

    def analyze_batch(self, texts):
        validate_texts(texts)
        results = [self.analyze(text) for text in texts]
        return {"results": results, "summary": {"total": len(results), "review": sum(r["needs_review"] for r in results),
                "quoted": sum(r["label"] == 2 for r in results), "unmatched": sum(r["label"] == 0 for r in results)}}
