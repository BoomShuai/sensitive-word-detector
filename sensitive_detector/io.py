"""Bounded UTF-8 TXT, CSV and JSONL import; no document converters or network calls."""
import csv
import io
import json
from pathlib import Path
import sys
from .engine import validate_texts

MAX_BYTES = 1024 * 1024


def load_texts(source, file_type=None, column="text"):
    if source == "-":
        data = sys.stdin.buffer.read(MAX_BYTES + 1)
    else:
        with Path(source).open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("输入文件不能超过 1 MiB")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("输入文件必须是 UTF-8 编码") from error
    kind = file_type or (Path(source).suffix.lstrip(".") if source != "-" else "txt")
    if kind == "txt":
        texts = [line.strip() for line in text.splitlines() if line.strip()]
    elif kind == "jsonl":
        texts = []
        for line in text.splitlines():
            if line.strip():
                value = json.loads(line)
                texts.append(value.get(column) if isinstance(value, dict) else value)
    elif kind == "csv":
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if not reader.fieldnames or column not in reader.fieldnames:
            raise ValueError("CSV 缺少指定文本列")
        texts = [row.get(column) for row in reader]
    else:
        raise ValueError("仅支持 txt、csv、jsonl")
    return validate_texts(texts)
