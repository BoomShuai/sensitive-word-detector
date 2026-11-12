import argparse
import json
from pathlib import Path
import sys
from .engine import Detector
from .io import load_texts
from .rules import load_rules


def main(argv=None):
    parser = argparse.ArgumentParser(description="本地敏感词与引用差错检测")
    commands = parser.add_subparsers(dest="command", required=True)
    scan = commands.add_parser("scan", help="检测文本或批量文件")
    source = scan.add_mutually_exclusive_group(required=True)
    source.add_argument("--text")
    source.add_argument("--input", help="TXT/CSV/JSONL 路径，- 表示标准输入")
    scan.add_argument("--file-type", choices=("txt", "csv", "jsonl"))
    scan.add_argument("--column", default="text")
    scan.add_argument("--output", help="新建 JSON 结果文件；不覆盖既有文件")
    serve = commands.add_parser("serve", help="启动本机网页与 API")
    serve.add_argument("--port", type=int, default=8765)
    for command in (scan, serve):
        command.add_argument("--rules", help="自定义 JSON 词库")
        command.add_argument("--backend", choices=("rules", "semantic"), default="rules")
        command.add_argument("--model-dir", help="语义模式的本地模型目录")
    args = parser.parse_args(argv)
    try:
        detector = Detector(load_rules(args.rules), args.backend, args.model_dir)
        if args.command == "serve":
            from .server import serve_local
            serve_local(detector, args.port)
        else:
            texts = [args.text] if args.text is not None else load_texts(args.input, args.file_type, args.column)
            result = json.dumps(detector.analyze_batch(texts), ensure_ascii=False, indent=2) + "\n"
            if args.output:
                with Path(args.output).open("x", encoding="utf-8") as stream:
                    stream.write(result)
            else:
                print(result, end="")
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        if isinstance(error, OSError):
            print("操作失败：请检查文件权限、输出文件是否已存在，或端口是否被占用。", file=sys.stderr)
        else:
            print("操作失败：" + str(error), file=sys.stderr)
        return 2
