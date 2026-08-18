# MARKETING-ERROR-LOG · 营销 Agent 历史错误日志

**这是「营销 agent 分派时避免重复错误」的唯一机制。**
每次执行者出错，Opus 立刻追加一条。分派前必查该类型的历史错误，注入分派包。

## 怎么用

1. Opus 分派前：`grep -A5 "分类:" docs/operations/MARKETING-ERROR-LOG.md`，抄进分派包「⚠️ 历史同类坑」
2. 执行者出错：Opus 立刻追加一条，`重复次数` 自增
3. L1 复盘时：按 `分类` 统计出错率

## 错误分类

- **call-param** 调用参数错误（漏 subagent_type/isolation 等）
- **code-quality** 代码质量（假绿测试、死亡引用、夹带文件）
- **drift** 契约漂移（schema/枚举/列名/路径不一致）
- **degrade** 模型降级（502/429/400 等）
- **incomplete** 不完整交付（漏任务、空桩、假完成）
- **path-issue** 路径问题（相对路径依赖、cwd、目录结构混乱）
- **encoding** 编码问题（GBK/UTF-8 控制台、emoji）
- **other** 其他

---

# 错误条目

<!-- 最新的追加在最下面。 -->

### M001 · 2026-08-18 Day28 营销 仓库路径引用漂移
- 现象: 独立仓库复制后 `docs/marketing/design/` → `docs/design/`，compliance/rules_loader.py 和 content/generate.py 里硬编码的 rules.json 路径失效，合规闸 FileNotFoundError
- 分类: path-issue
- 根因: 代码里写死了「相对仓库根往上四级 → docs/marketing/design/rules.json」，但独立仓库实际布局是「仓库根 docs/design/rules.json」
- 重复次数: 第 1 次
- 关联规则: 分派包必写「文件路径全用仓库根相对路径，禁止硬编码中间层目录名」

### M002 · 2026-08-18 Day28 营销 嵌套仓库目录结构混淆
- 现象: `git add -A` 在 `marketing-agent/marketing-agent/` 嵌套子目录跑，`docs/`（仓库根的平级目录）从未被加入仓库，远程仓库漏掉所有设计文档
- 分类: path-issue
- 根因: 独立仓库根在 `D:/llm/marketing-agent/`，代码在嵌套 `marketing-agent/` 子目录；在子目录跑 git add 只看到子目录内容
- 重复次数: 第 1 次
- 关联规则: 任何 commit 前 `git rev-parse --show-toplevel` 确认仓库根，`git ls-tree -r HEAD --name-only | wc -l` 核对全量

### M003 · 2026-08-18 Day28 营销 `.gitignore` 换行粘贴错误
- 现象: 追加 `out/` 到 .gitignore 时与上一行 `*.pyc` 粘连成 `*.pycout/`，目录完全没被忽略
- 分类: path-issue
- 根因: echo 追加时无换行，内容拼接；Read 后应逐行核验
- 重复次数: 第 1 次
- 关联规则: 改完 .gitignore 后 `git check-ignore <路径>` 验证生效

### M004 · 2026-08-18 Day28 营销 `--no-call` 预览文件质量门假阳性
- 现象: 对 generate.py `--no-call` 生成的预览文件跑质量门，扫出 12 条 AI 痕迹 + 17 条合规命中（其中 6-10 条 BLOCK），全是模板里「禁'最/第一/提分/保过'」等内容被当成正文扫了
- 分类: code-quality
- 根因: 预览文件 = 完整 prompt 指令（含模板铁律、禁词清单示例），`quality/prepare_publication_text()` 和 `compliance/check.py` 只对「正文章节」提取，对预览文件原样全扫
- 重复次数: 第 1 次
- 关联规则: 已修——识别 `mode: no-call` 标记返回空串跳过扫描。**后续生成模式必须是 live（真稿）**，预览文件不送质量/合规门

### M005 · 2026-08-18 Day28 营销 Windows GBK 控制台 emoji 崩溃
- 现象: Windows 默认 GBK，打印 emoji（⚠️/📝）触发 `UnicodeEncodeError: 'gbk' codec can't encode`
- 分类: encoding
- 根因: 控制台编码不是 UTF-8
- 重复次数: 第 1 次（content/compliance/quality 三处都遇到）
- 关联规则: CLI 入口加 `_ensure_utf8_stdout()` 强制 stdout UTF-8 + errors=replace；测试用 `PYTHONIOENCODING=utf-8`

### M006 · 2026-08-18 Day28 营销 LLM 实调未测
- 现象: `DEEPSEEK_API_KEY` 未配置，只能测到「缺 key → 401 提示」，真稿链路未用真实 key 跑通 200 出稿
- 分类: incomplete
- 根因: 本机无 key
- 重复次数: 第 1 次
- 关联规则: 真 key 到位后必须跑一次 live 出稿 + 质量门 + 合规闸完整链路

---

## 分类统计

### M007 · 2026-08-18 Day2 Lane B exec-luna(误报 DONE)
- 现象: 报告完成且给 commit，但 `cookie_store.py`/`account_manager.py`/`requirements.txt` 磁盘上不存在，只有半成品 `test_cookie_store.py`。git 历史里无任何 Lane B 提交
- 分类: incomplete
- 根因: exec-luna 报 DONE 但未落地实现文件；可能中途停止但误报完成
- 重复次数: 第 1 次（incomplete 类累计第 2 次）
- 关联规则: 一审必须 `ls -la` 确认**实现文件**磁盘存在 + `git log` 确认 commit 真的包含实现

---

## 分类统计

| 分类 | 次数 | 最近错误 | 结论 |
|------|------|---------|------|
| path-issue | 3 | M003 | 路径/目录结构易错，重灾区；commit 前必查仓库根 |
| code-quality | 1 | M004 | 预览文件扫描范围，已修 |
| encoding | 1 | M005 | CLI 统一 UTF-8 |
| incomplete | 2 | M007 | **执行者误报 DONE，一审必须验磁盘+git** |