# 维护与贡献

`main` 保存可运行版本。开发使用 `feat/主题`、`fix/问题` 或 `docs/主题` 分支，通过 Pull Request 合并。提交前检查新增文件、提交身份和差异，避免提交个人词库、实际输入或结果。

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/frontend.test.mjs
git add sensitive_detector tests scripts docs examples README.md PRIVACY.md CONTRIBUTING.md
python3 scripts/privacy_check.py --history
git diff --cached --stat
```

新增功能必须补充对实际行为有意义的测试，特别是标签优先级、归一化位置、HTTP 来源与批量原子性。纯说明文档修改不需新增实现镜像测试。

推送使用 GitHub noreply 邮箱，避免公开私人邮箱。发布前再次检查全部历史；删除工作区里的文件不会自动清除已提交的历史。

默认依赖保持为零。任何联网能力、文本持久化或后端降级行为都必须明确披露，并更新隐私文档。示例及测试使用合成文本，不提交真实用户内容。不用合成样例成绩宣传真实场景准确率。

可选语义测试使用可控向量桩验证接口；真实模型验证需要本地模型，不属于默认 CI 的推理保证。变更必须在 PR 中区分这两种验证。
