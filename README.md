# Sensitive Word Detector · 本地文本筛查系统

[![CI](https://github.com/BoomShuai/sensitive-word-detector/actions/workflows/ci.yml/badge.svg)](https://github.com/BoomShuai/sensitive-word-detector/actions/workflows/ci.yml)

一个可独立运行的中文文本筛查系统：**自定义敏感词匹配 + 引用差错预警**，提供网页工作台、命令行、Python SDK 和本地 JSON API。

默认模式仅依赖 Python 标准库，离线工作。输入不写入日志、不自动落盘，页面不使用浏览器持久化存储。公开仓库仅包含整理后的代码、公开短句和人工构造示例。

## 三步启动

需要 Python 3.9 或更新版本。在终端执行：

```sh
git clone https://github.com/BoomShuai/sensitive-word-detector.git
cd sensitive-word-detector
python3 -m sensitive_detector serve
```

打开终端显示的 **http://127.0.0.1:8765/**，点击“载入演示”，再点击“开始检测”。Windows 可将 `python3` 改为 `python`。端口冲突时加 `--port 8766`。

无需 API Key、Node.js、模型下载或依赖安装。Node.js 只用于开发时运行前端逻辑测试。

## 系统包含什么

| 能力 | 当前行为 |
| --- | --- |
| 敏感词筛查 | 自定义词库、多次命中、原文位置、NFKC 全半角与大小写归一化 |
| 分隔符变体 | 每个词可选择忽略标点、空白、不可见字符；会增加误报可能 |
| 引用差错预警 | 基于锚词、字符相似度、编辑距离和上下文的 V3 规则 |
| 可选语义增强 | V4 本地句向量召回；用户明确选择并提供本地模型 |
| 网页工作台 | 多条文本检测、TXT 导入、词库编辑、统计与 JSON 导出 |
| 命令行与 SDK | TXT / CSV / JSONL 批量导入，JSON 结果与逐条证据 |
| 工程维护 | 自动测试、打包验证、隐私模式扫描、贡献规范和变更记录 |

**内置词库是演示词库，不是完整的通用敏感词表。** 三条公开短句用于演示引用核对，不表示这些短句本身属于禁止内容。请按实际需求配置词库。

## 检测结果

| 标签 | 含义 | 示例 |
| --- | --- | --- |
| `0` 未命中 | 当前规则没有命中 | 今天的天气适合散步。 |
| `1` 建议复核 | 词库命中或疑似引用差错 | 谦受益满招害。 |
| `2` 引用命中 | 规范引用或上下文启发式命中 | 谦受益，满招损。 |

同一文本存在多个发现时，`1` 优先于 `2`。`2` 不等于内容通过审核，`0` 也不等于内容一定合规。完全同义改写、复杂上下文、跨句引用及未知词均可能漏检或误判；需要人工复核。

## 命令行

```sh
python3 -m sensitive_detector scan --text "谦受益满招害。"
python3 -m sensitive_detector scan --input examples/demo.txt
python3 -m sensitive_detector scan --input examples/demo.csv --column text
python3 -m sensitive_detector scan --input examples/demo.jsonl --output result.json
```

输入文件须为 UTF-8，最多 1 MiB、100 条、总长 32000 字符；每条不超过 8000 字符。引用检测以句号、问号、感叹号、分号或换行分段，单个句段最多 256 字符，超限会拒绝而不是截断。CLI 输出文件须不存在，不覆盖原有结果。

## 自定义词库

复制 [默认词库](sensitive_detector/data/default_rules.json) 到本地忽略目录 `private/`，编辑后启动：

```sh
python3 -m sensitive_detector serve --rules private/rules.json
```

```json
{
  "version": 1,
  "words": [{"id": "demo", "text": "示例敏感词", "category": "演示词", "ignore_separators": true}],
  "quotes": [{"id": "quote", "text": "谦受益满招损", "anchors": ["谦受益", "满招损"]}]
}
```

支持最多 1000 个词、10 条规范引用。`words` 和 `quotes` 可单独使用。引用最多 32 字，需提供 1–4 个不重复、包含于引用中的锚词。词库只包含文字规则，不执行正则表达式或自定义代码。

## Python SDK 与本地 API

在仓库目录可直接导入；要在其他目录使用，先执行 `python3 -m pip install .`：

```python
from sensitive_detector import Detector

result = Detector().analyze("谦受益满招害。")
print(result["status"], result["findings"])
```

启动工作台后可访问同一个 API：

```sh
curl http://127.0.0.1:8765/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"texts":["谦受益满招害。","今天的天气适合散步。"]}'
```

接口格式、输入限制与来源检查见 [API 文档](docs/API.md)。该服务仅绑定本机回环地址，无用户认证，不提供公网部署入口。

## 可选语义模式

```sh
python3 -m pip install '.[semantic]'
python3 -m sensitive_detector serve --backend semantic --model-dir models/embedding
```

需要自行准备可信、可由 Sentence Transformers 加载的完整本地模型。系统不下载模型，不调用外部推理 API；加载或推理异常会明确报错，不会静默改用规则结果。模型文件、许可与依赖安装由使用者管理，均不包含在本仓库中。

语义召回可能增加误报，不承诺优于规则模式。实现使用 [Sentence Transformers 的本地加载参数](https://sbert.net/docs/package_reference/sentence_transformer/model.html)，设置 `local_files_only=True` 和 `trust_remote_code=False`。

## 测试与项目结构

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/frontend.test.mjs
python3 scripts/privacy_check.py --history
```

```text
sensitive_detector/
  algorithms/       V1–V4 算法及可选本地语义后端
  data/             演示词库
  web/              本地网页，无外部 CDN
  engine.py         多规则融合与证据输出
  cli.py / server.py
examples/           合成演示输入
tests/              检测、导入、HTTP、语义接口与前端测试
scripts/            发布前隐私检查
docs/               API、架构、隐私与验证说明
```

算法从实验代码整理而来，公开版本使用全新的 Git 历史。未纳入个人报告、原始实验语料、历史结果日志、模型权重或旧文件路径；不沿用历史实验中的“零漏报”“100% 准确率”等表述。见 [架构与局限](docs/ARCHITECTURE.md)、[验证记录](docs/VALIDATION.md)、[隐私边界](PRIVACY.md)、[维护规范](CONTRIBUTING.md)。

许可证：暂未指定。
