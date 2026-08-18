# LESSONS-MARKETING · 营销 Agent 每日经验累积

**这是「Day1 犯的错 Day2 不再犯」成立的唯一机制。**
营销 agent 的独立错误日志回路，分派前必读。

## 怎么用

- **怎么写（Opus 收尾时做，2 分钟）**：读 M-code 错误日志 + 今天踩的坑，压成 2~3 条追加。多余废话不写。
- **怎么用（分派 P1-P4 前必做）**：`tail -60 docs/operations/MARKETING-ERROR-LOG.md`，挑相关的 1~3 条**原文抄进分派包**「⚠️ 历史同类坑」。

**一条合格的经验长这样**：

```
### M<序号> · <一句话现象>
- 触发: <什么情况下会遇到>
- 真因: <不是表象，是根因>
- 动作: <下次直接怎么做，具体到命令或文件>
- 该写进哪: 分派包 / WORKER-BRIEF / 就放这
```

---

# 经验条目

<!-- 最新的追加在最下面。 -->

### M-L001 · 仓库操作前先确认「仓库根」，commit 前核对全量
- 触发: 独立仓库/嵌套子目录交付时，`git add -A` 从子目录跑会把平级的 docs/ 漏掉
- 真因: 代码目录 ≠ 仓库根；git 默认从 cwd 限定范围
- 动作: `git rev-parse --show-toplevel` 确认根 → `git add -A` → `git ls-tree -r HEAD --name-only | wc -l` 核对文件数 → 再 commit。存疑就 `git ls-files` 单文件验证
- 该写进哪: 分派包「交付格式」

### M-L002 · 路径一律用仓库根相对路径，禁止硬编码中间层目录名
- 触发: 仓库迁移/目录改版后，硬编码 `docs/marketing/design/rules.json` 找不到文件
- 真因: 目录结构不是永久的，代码里写死层级会在迁移时断
- 动作: 用 `BASE_DIR = Path(__file__).resolve().parent` 推导，路径只写 `docs/design/rules.json` 一层；迁移后 `grep -rn "docs/marketing" --include="*.py"` 全量排查
- 该写进哪: 分派包「历史同类坑」

### M-L003 · CLI 必须统一 UTF-8 stdout，否则 Windows GBK 崩
- 触发: 打印 emoji/中文引号时 `UnicodeEncodeError: 'gbk' codec can't encode`
- 真因: Windows 控制台默认 GBK（cp936）
- 动作: 所有 CLI 入口（content/quality/compliance/check.py）main() 第一行调 `_ensure_utf8_stdout()`；测试设 `PYTHONIOENCODING=utf-8`
- 该写进哪: WORKER-BRIEF 通用禁项

### M-L004 · 预览文件不送质量/合规门，真稿才审核
- 触发: `--no-call` 生成的预览文件跑质量门出十几条假阳性
- 真因: 预览文件含完整 prompt 指令（禁词清单示例），模板铁律被当成正文扫
- 动作: `prepare_publication_text()` 识别 `mode: no-call` → 返回空串跳过；唯一的合法审核对象是 live 真稿
- 该写进哪: 分派包「合规闸」

### M-L005 · `.gitignore` 追加内容必须逐行核验 + check-ignore 验证
- 触发: echo 追加 `out/` 时与上一行无换行，内容粘连成 `*.pycout/`
- 真因: echo 追加不带换行
- 动作: 改完 .gitignore → `cat .gitignore` 逐行看 → `git check-ignore <路径>` 确认生效 → 再 commit
- 该写进哪: 分派包「交付格式」