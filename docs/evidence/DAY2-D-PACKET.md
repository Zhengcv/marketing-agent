# DAY2-D · 发布通道层调度与频控

## 1 改了什么

本车道实现 SQLite 发布记录、账号发布频控与始终 dry-run 的半自动 CLI 入口。

| 文件 | 说明 |
|---|---|
| `marketing-agent/publish/storage.py` | `PublishRecord` 数据结构与 `PublishRecordStore` SQLite 建表、pending/published/aborted 状态写回、最近发布时间和当日计数查询。 |
| `marketing-agent/publish/rate_limit.py` | `RateLimiter` 24 小时间隔与每日 1 篇硬约束；暴露 `config.rate_limit_hours` 和 `constraint`。 |
| `marketing-agent/publish/run.py` | UTF-8 CLI；频控、合规、可选质量提示、预览和人工确认；默认 Unittest/mock，不调用真实平台；`--live` 明确拒绝；支持 `--publisher-stub`/`PUBLISHER_STUB` 注入点。 |
| `marketing-agent/publish/tests/test_storage.py` | 5 个 tempfile SQLite 存储测试。 |
| `marketing-agent/publish/tests/test_rate_limit.py` | 6 个频控测试。 |
| `marketing-agent/publish/tests/test_run.py` | 3 个 CLI/工作流测试，覆盖 dry-run、频控拒绝和 `--live` 拒绝。 |
| `docs/evidence/DAY2-D-TDD-RED.txt` | TDD RED 证据。 |

提交记录：
- `5efe2f0 day2/d: add SQLite publish record storage`
- `9bb2210 day2/d: enforce publish frequency limits`
- `b785707 day2/d: add guarded publish CLI workflow`

## 2 怎么证明它对

TDD RED：见 `docs/evidence/DAY2-D-TDD-RED.txt`。三个新增实现文件不存在时，storage/rate_limit/run 测试分别以 `ModuleNotFoundError` 收集失败；实现后各自重跑全绿。

GREEN 命令：

```text
cd /d/llm/marketing-agent/marketing-agent && PYTHONIOENCODING=utf-8 python -m pytest publish/tests/ -v
```

尾部结果：

```text
======================= 44 passed, 1 warning in 18.35s ========================
```

另行验证：

```text
cd /d/llm/marketing-agent/marketing-agent && PYTHONIOENCODING=utf-8 python -m pytest publish/tests/test_storage.py -v
======================== 5 passed, 1 warning in 16.73s ========================

cd /d/llm/marketing-agent/marketing-agent && PYTHONIOENCODING=utf-8 python -m pytest publish/tests/test_rate_limit.py -v
======================== 6 passed, 1 warning in 3.05s ========================

cd /d/llm/marketing-agent/marketing-agent && PYTHONIOENCODING=utf-8 python -m pytest publish/tests/test_run.py -v
======================== 3 passed, 1 warning in 3.81s ========================
```

`git diff --check` 通过；代码文件行数核验：storage 129、rate_limit 109、run 215 行，均完整收尾。

## 3 FR 对账

| FR / 验收点 | 实现位置 | 验证方式 |
|---|---|---|
| `config.rate_limit_hours=24` | `publish/rate_limit.py` `config` | `test_default_constraints_are_one_per_day_and_24_hours` |
| `constraint.daily_max=1` | `publish/rate_limit.py` `constraint` | 同上 |
| `constraint.min_interval_hours=24` | `publish/rate_limit.py` `constraint` | 同上 |
| 无历史允许 | `RateLimiter.check` | `test_check_allows_account_with_no_published_record` |
| `<24h` 拒绝且原因含“间隔” | `RateLimiter.check` | `test_check_rejects_before_24_hours_and_reports_next_time` |
| `>=24h` 允许 | `RateLimiter.check` | `test_check_allows_at_exactly_24_hours` |
| pending 记录与 SQLite 文件创建 | `PublishRecordStore` | `test_sqlite_file_is_created_and_pending_can_be_read` |
| `mark_published` 更新状态/时间 | `PublishRecordStore.mark_published` | `test_mark_published_updates_status_and_time` |
| 未发布最近时间为 None | `latest_published_time` | `test_mark_aborted_does_not_count_as_published` |
| 最近 published 时间正确 | `latest_published_time` | `test_latest_published_time_returns_most_recent_record` |
| 当日统计按平台/账号/起始时间过滤 | `count_published_today` | `test_count_published_today_filters_platform_account_and_start` |
| CLI 参数解析和默认 dry-run | `publish/run.py` `main`/`run_workflow` | `test_default_dry_run_only_previews_and_does_not_publish` |
| `--live` 不可用 | `publish/run.py` `main` | `test_live_flag_is_rejected_without_publishing` |
| 频控拒绝清晰打印且不填表 | `publish/run.py` `run_workflow` | `test_frequency_rejection_is_printed_and_stub_is_not_called` |
| mock publisher 注入点 | `--publisher-stub` / `PUBLISHER_STUB` / `publisher` 参数 | `run_workflow` 接口及 `_load_stub` |
| CLI UTF-8 | `_ensure_utf8_stdout()` | `main()` 首行调用；全套测试使用 `PYTHONIOENCODING=utf-8` |

## 4 我踩的坑

- 卡在哪：第一次运行 storage 测试时，当前分支已有 Lane C 的 `publish/__init__.py`，它导入尚未同步到本车道工作树的 `human_gate.py`，因此测试在收集阶段报 `ModuleNotFoundError: publish.human_gate`；随后 rate-limit/run RED 也分别因实现文件缺失报 `ModuleNotFoundError`。
- 卡多久：每次定位约几分钟，没有等待外部依赖。
- 怎么绕过：确认 Lane C 文件已存在后，保留包初始化契约，先补本车道测试捕获真实 RED，再按冻结接口逐个实现 storage、rate_limit、run；未改 Lane C 或 Lane A/B 文件。
- 另一个坑：Windows 上使用很小的测试时间戳（如 1000）时，`datetime.timestamp()` 计算 1970 年本地午夜会抛 `OSError: [Errno 22] Invalid argument`；改为从输入时间戳减去当天已过秒数，避免平台时间范围限制。
- 重来先做什么：先 `git status --short`、`git rev-parse --show-toplevel`，再确认并读取已存在的 publish/browser 契约；测试使用显式 `now`，不要让频控断言依赖墙上时钟。

自查：本车道未修改 Lane A/B/C 代码；工作树中唯一未跟踪的非本车道文件是 `marketing-agent/browser/tests/test_cookie_store.py`，未加入任何提交。
