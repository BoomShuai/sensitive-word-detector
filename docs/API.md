# 本地 JSON API

启动：`python3 -m sensitive_detector serve`。默认地址 `http://127.0.0.1:8765`。

| 路由 | 方法 | 返回 |
| --- | --- | --- |
| `/api/health` | GET | 后端类型与不保存输入的状态说明 |
| `/api/rules` | GET | 启动时的词库 |
| `/api/analyze` | POST | 批量检测与统计 |

请求头使用 `Content-Type: application/json`，请求体：

```json
{"texts":["谦受益满招害。","今天的天气适合散步。"]}
```

规则模式可增加 `rules` 字段，格式同默认词库，只影响本次请求。语义模式需在启动时通过 `--rules` 指定词库，不接受请求内修改。

响应包含 `results` 与 `summary`。每条结果包括原文 `text`、标签 `label`、中文状态 `status`、`needs_review`、实际使用的 `backend`、`findings` 和限制说明 `note`。发现包括规则 id、类型、原文范围、原文片段、参考文本和解释。

`start` 为从 0 开始的 Python Unicode 码点位置，`end` 为右开区间。关键词范围对应原文命中片段；引用发现范围对应整个句段。它们不是 UTF-8 字节偏移，也不是 JavaScript UTF-16 字符单元偏移。

`needs_review=false` 仅表示未触发优先复核标签，不表示免于人工判断。

限制：请求体最多 256 KiB；每批最多 100 条、总长 32000 字符；单条最多 8000 字符，单个句段最多 256 字符。空白文本、错误 schema、超限输入均明确拒绝。整个批次中任何一条无效时，不返回部分检测结果。

常见状态码：`400` 输入无效，`403` 来源或 Host 不允许，`404` 路由不存在，`413` 请求体超限，`415` Content-Type 不支持，`503` 本地模型失败。最多四个并发 HTTP 连接，检测计算串行执行；额外连接可能直接关闭。请求读写超时为 8 秒。

服务只允许 `127.0.0.1` 绑定。Host 必须为对应端口的 `127.0.0.1` 或 `localhost`；若携带 Origin，必须属于对应的本地来源；拒绝 cross-site 请求，不开放 CORS。无 Origin 的命令行调用允许使用。服务不提供账号、TLS、租户隔离或公网访问能力。
