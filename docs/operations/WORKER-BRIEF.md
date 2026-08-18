# WORKER-BRIEF · 营销 Agent 执行者纪律

## 通用纪律（所有执行者必须遵守）

1. **N9: 必须带 isolation:"worktree"** — 在主工作树直接写码是死罪，commit 会被切走。
2. **N8: 收工必写「我踩的坑」** — 写入 PACKET 第 4 节，空 = 打回 INVALID。
3. **N1: 长文件分块写** — 写完 `wc -l` + `tail -5` 核验，再跑测试确认。
4. **禁止攒批到收工** — 每完成一个 Task 立即 `git commit`。
5. **禁止夹带文件** — 只改分派包指定的文件，`git diff --name-only` 自查。
6. **零外部依赖** — 能用标准库就标准库，需 `pip install` 的必须写在 PACKET 里。

## 营销仓库专有纪律

7. **路径用仓库根相对路径** — 禁止硬编码 `docs/marketing/design/`，用 `docs/design/`。
8. **预览文件不送质量/合规门** — `--no-call` 文件只做预览，真稿才审核。
9. **CLI 必须 UTF-8** — main() 第一行调 `_ensure_utf8_stdout()`。
10. **.gitignore 改完必验证** — `git check-ignore <路径>` 确认生效。

## 分派包启动动作

```bash
cat docs/operations/MARKETING-ERROR-LOG.md | tail -30
cat docs/operations/LESSONS-MARKETING.md | tail -20
git rev-parse --show-toplevel   # 确认仓库根
git status --short              # 确认工作树干净
```