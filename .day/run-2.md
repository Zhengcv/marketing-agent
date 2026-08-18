# Day 2 · 营销 Agent · 规划说明

> 设计者: 0813（deepseek-v4-pro-0813）
> 范围: P2（积木⑤ browser 反检测底座）+ P3（积木④ publish 发布通道）
> 仓库根: `D:/llm/marketing-agent/`（⚠️ 嵌套结构：代码在 `marketing-agent/` 子目录）

## 0. 本期目标

- **积木⑤ browser/**：反检测底座（引擎抽象 + 真性化行为 + Cookie 持久化 + 多账号）
- **积木④ publish/**：半自动发布通道（填表→预览→人工确认闸→回写，小红书+抖音）
- **验收锚点**：不依赖真账号/真代理，全绿测试离线可跑（参照 M004：不可测的真实登录环节不送门，留 check 标记）

## 1. 环境事实（侦查落定）

- 仓库根 `D:/llm/marketing-agent/`；代码在嵌套 `marketing-agent/`（M002 陷阱持续存在）
- 积木①②③ 全绿：content/31 + quality/13 + compliance/19 = **63 tests**
- `publish/`、`browser/` 均不存在，需全新创建
- **无 requirements.txt / pyproject**，Python 3.9，pytest 6.2.4
- `.day/`、`docs/evidence/` 本次创建
- HEAD `0aa072b`，工作区干净，远程 `github.com/Zhengcv/marketing-agent`

## 2. 车道划分（4 车道，2 轮）

| 车道 | 模型 | 积木 | 内容 | 轮次 | 依赖 |
|------|------|------|------|------|------|
| **Lane A** | exec-strong | ⑤ browser | `engine.py` 引擎抽象 + 工厂 + Humanize 鼠标/键盘 | 第1轮 | — |
| **Lane B** | exec-luna | ⑤ browser | `cookie_store.py` + `account_manager.py` + `requirements.txt` | 第1轮 | — |
| **Lane C** | exec-strong | ④ publish | `publish/` 小红书/抖音表单 + `human_gate.py` 人工确认闸（含接口/契约） | 第2轮 | 依赖 A+B 的接口 |
| **Lane D** | exec-luna | ④ publish | `rate_limit.py` + `sqlite.py` 发布记录 + `run.py` 入口 | 第2轮 | 依赖 A+B 的接口 |

> 分轮理由：发布通道必须消费 browser 层的**接口契约**。第一轮先把浏览器引擎接口定义冻结，第二轮 publish 按契约实现，避免 WebDrivere.路径漂移。第 1 轮结束统一 `git push`，第 2 轮从最新 origin/main 建底座。

## 3. 明确不做（本 day 边界）

- ❌ 不做「真账号登录小红书/抖音」——无账号/代理/密钥，不可离线验证（参照 M004 教训，真登录不送门）
- ❌ 不做 API 签名发布（纯 API 发布禁用，架构红线 6.1）
- ❌ 不做 CloakBrowser 商业订阅适配（架构 §7 决策 1：优先纯开源 invisible_playwright）
- ❌ 不改积木①②③ 既有代码（本次只新增）

## 4. 红线与历史坑（所有分道包必抄）

- **M001/M-L002**：文件路径全用仓库根相对路径，`BASE_DIR = Path(__file__).resolve().parent` 推导，禁止硬编码 `docs/marketing/...` 中间层
- **M002/M-L001**：commit 前 `git rev-parse --show-toplevel` 确认根；`git add` 从仓库根跑，别在 `marketing-agent/` 嵌套子目录跑；`git ls-tree -r HEAD --name-only | wc -l` 核对全量
- **M003/M-L005**：改 `.gitignore` 后逐行 `cat` 看 + `example check-ignore <path>`
- **M005/M-L003**：CLI 入口 main() 第一行 `_ensure_utf8_stdout()`；测试设 `PYTHONIOENCODING=utf-8`
- **M004/M-L004**：预览/中间产物不送质量门；逻辑不可真机测试时，标注 TODO 真机后续，不硬跑

## 5. 技术约束

- Python 3.9 兼容（不用 3.10+ 语法：`X | None` 类型标注用 `Optional`）
- 引擎抽象必须「可热替换」：`invisible_playwright` 优先，备 `patchright`
- 反检测四件套：指纹伪装 + 住宅代理粘性IP + humanize 真行为 + Cookie storageState
- 半自动红线：纯 API 签名发布禁用，每天 ≤1 篇/账号，间隔 24h+

## 6. 交付验收

- 每个 lane 产出 REVIEW-PACKET（四节：完成概况/测试/文件清单/证据）
- 4 车道全绿 + 全集 `python -m pytest`（或 per-包）通过
- `docs/evidence/DAY2-<lane>-PACKET.md` 落盘
- 全部 commit 后 `git push origin master`