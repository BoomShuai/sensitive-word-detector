"""Validate user-supplied dictionaries before any detector is constructed."""
import json
from pathlib import Path
import unicodedata

DEFAULT_RULES = Path(__file__).parent / "data" / "default_rules.json"


def normalize(text, compact=True):
    output, positions = [], []
    for index, char in enumerate(text):
        for normalized in unicodedata.normalize("NFKC", char).casefold():
            if compact and not normalized.isalnum():
                continue
            output.append(normalized)
            positions.append(index)
    return "".join(output), positions


def validate_rules(value):
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("词库必须是 version=1 的 JSON 对象")
    if set(value) - {"version", "words", "quotes"}:
        raise ValueError("词库包含未知字段")
    words, quotes = value.get("words", []), value.get("quotes", [])
    if not isinstance(words, list) or not isinstance(quotes, list):
        raise ValueError("words 和 quotes 必须是数组")
    if len(words) > 1000 or len(quotes) > 10 or not words and not quotes:
        raise ValueError("词库需至少一条规则，最多 1000 个词和 10 条引用")
    result, seen = {"version": 1, "words": [], "quotes": []}, set()
    for kind, rows, limit in (("words", words, 64), ("quotes", quotes, 32)):
        allowed = {"id", "text", "category", "ignore_separators"} if kind == "words" else {"id", "text", "anchors"}
        for row in rows:
            if not isinstance(row, dict) or set(row) - allowed:
                raise ValueError("规则字段无效")
            ident, text = row.get("id"), row.get("text")
            if not isinstance(ident, str) or not ident or len(ident) > 80 or ident in seen:
                raise ValueError("规则 id 必须唯一且为 1–80 字符")
            if not isinstance(text, str) or not text.strip() or len(text) > limit:
                raise ValueError("规则文本为空或超长")
            compact, _ = normalize(text)
            if not compact:
                raise ValueError("规则必须包含字母、数字或汉字")
            seen.add(ident)
            if kind == "words":
                category = row.get("category", "自定义词")
                ignore = row.get("ignore_separators", False)
                if not isinstance(category, str) or not 1 <= len(category) <= 80 or type(ignore) is not bool:
                    raise ValueError("category 或 ignore_separators 无效")
                result[kind].append({"id": ident, "text": text, "category": category, "ignore_separators": ignore})
            else:
                anchors = row.get("anchors")
                if not isinstance(anchors, list) or not 1 <= len(anchors) <= 4:
                    raise ValueError("每条引用需 1–4 个锚词")
                normalized = []
                for anchor in anchors:
                    if not isinstance(anchor, str) or not anchor or not normalize(anchor)[0] or normalize(anchor)[0] not in compact:
                        raise ValueError("锚词必须是规范引用的一部分")
                    normalized.append(anchor)
                if len(set(normalize(a)[0] for a in normalized)) != len(normalized):
                    raise ValueError("锚词不能重复")
                result[kind].append({"id": ident, "text": text, "anchors": normalized})
    return result


def load_rules(path=None):
    path = Path(path) if path else DEFAULT_RULES
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("词库文件不能超过 1 MiB")
    return validate_rules(json.loads(path.read_text(encoding="utf-8-sig")))
