# DAY2-C PACKET · publish 发布通道层

## 1 改了什么

```
git diff --stat f2fd96b^..f2fd96b
```

| 文件 | 说明 |
|------|------|
| `marketing-agent/publish/__init__.py` | 发布通道包初始化，导出 HumanGate/GateDecision/GateResult |
| `marketing-agent/publish/platforms/__init__.py` | 发布平台子包初始化，导出 XhsPublisher/XhsPost/DyPublisher/DyPost |
| `marketing-agent/publish/platforms/xiaohongshu.py` | 小红书发布表单（XhsPost dataclass + XhsPublisher） |
| `marketing-agent/publish/platforms/douyin.py` | 抖音发布表单（DyPost dataclass + DyPublisher） |
| `marketing-agent/publish/human_gate.py` | 人工确认闸（HumanGate → 预览/确认/取消/编辑） |
| `marketing-agent/publish/tests/test_xiaohongshu.py` | 小红书 11 个测试（validate 7 + fill_form 2 + publish 2） |
| `marketing-agent/publish/tests/test_douyin.py` | 抖音 9 个测试（validate 5 + fill_form 2 + publish 2） |
| `marketing-agent/publish/tests/test_human_gate.py` | 人工闸 10 个测试（preview 2 + confirm 7 + static 1） |
| `docs/evidence/DAY2-C-TDD-RED.txt` | TDD RED 证据（1 失败 → 修复 → 全绿） |

## 2 怎么证明它对

### 测试命令与输出

```bash
cd /d/llm/marketing-agent/marketing-agent
python -m pytest publish/tests/test_xiaohongshu.py publish/tests/test_douyin.py publish/tests/test_human_gate.py -v
```

```
============================= test session starts =============================
platform win32 -- Python 3.9.7, pytest-6.2.4, py-1.10.0, pluggy-0.13.1
rootdir: D:\llm\marketing-agent\marketing-agent
collected 30 items

publish/tests/test_xiaohongshu.py::TestXhsValidate::test_empty_body_returns_error PASSED
publish/tests/test_xiaohongshu.py::TestXhsValidate::test_empty_title_returns_error PASSED
publish/tests/test_xiaohongshu.py::TestXhsValidate::test_no_images_returns_error PASSED
publish/tests/test_xiaohongshu.py::TestXhsValidate::test_title_too_long_returns_error PASSED
publish/tests/test_xiaohongshu.py::TestXhsValidate::test_too_many_images_returns_error PASSED
publish/tests/test_xiaohongshu.py::TestXhsValidate::test_too_many_tags_returns_error PASSED
publish/tests/test_xiaohongshu.py::TestXhsValidate::test_valid_post_returns_empty PASSED
publish/tests/test_xiaohongshu.py::TestXhsFillForm::test_fill_form_records_ops PASSED
publish/tests/test_xiaohongshu.py::TestXhsFillForm::test_fill_form_validates_first PASSED
publish/tests/test_xiaohongshu.py::TestXhsPublish::test_publish_after_fill_form_clicks PASSED
publish/tests/test_xiaohongshu.py::TestXhsPublish::test_publish_without_fill_form_raises PASSED
publish/tests/test_douyin.py::TestDyValidate::test_empty_title_returns_error PASSED
publish/tests/test_douyin.py::TestDyValidate::test_no_video_returns_error PASSED
publish/tests/test_douyin.py::TestDyValidate::test_title_too_long_returns_error PASSED
publish/tests/test_douyin.py::TestDyValidate::test_too_many_topics_returns_error PASSED
publish/tests/test_douyin.py::TestDyValidate::test_valid_post_returns_empty PASSED
publish/tests/test_douyin.py::TestDyFillForm::test_fill_form_records_ops PASSED
publish/tests/test_douyin.py::TestDyFillForm::test_fill_form_validates_first PASSED
publish/tests/test_douyin.py::TestDyPublish::test_publish_after_fill_form_clicks PASSED
publish/tests/test_douyin.py::TestDyPublish::test_publish_without_fill_form_raises PASSED
publish/tests/test_human_gate.py::TestHumanGatePreview::test_preview_contains_platform_and_title PASSED
publish/tests/test_human_gate.py::TestHumanGatePreview::test_preview_with_douyin_fields PASSED
publish/tests/test_human_gate.py::TestHumanGateConfirm::test_edit_returns_edit PASSED
publish/tests/test_human_gate.py::TestHumanGateConfirm::test_invalid_then_valid_retries PASSED
publish/tests/test_human_gate.py::TestHumanGateConfirm::test_no_lowercase_returns_abort PASSED
publish/tests/test_human_gate.py::TestHumanGateConfirm::test_no_returns_abort PASSED
publish/tests/test_human_gate.py::TestHumanGateConfirm::test_yes_full_word_returns_confirm PASSED
publish/tests/test_human_gate.py::TestHumanGateConfirm::test_yes_lowercase_returns_confirm PASSED
publish/tests/test_human_gate.py::TestHumanGateConfirm::test_yes_returns_confirm PASSED
publish/tests/test_human_gate.py::TestHumanGateStatic::test_is_auto_publish_disabled_returns_true PASSED
======================== 30 passed in 0.64s =========================
```

### TDD RED 证据

TDD RED 证据已存 `docs/evidence/DAY2-C-TDD-RED.txt`。
首次运行 1 failed（`HumanGate.generate_preview` 中 `schedule_time=None` 时显示字面 "None" 而非 "立即"），修复后全绿。

## 3 FR 对账

| FR 编号 | 实现位置 | 验证方式 |
|---------|---------|---------|
| XhsPublisher.fill_form() 注入引擎后 ops 含 navigate+fill_form | `xiaohongshu.py:36-54` | `test_fill_form_records_ops` — 断言 op_names 包含 navigate 和 fill_form |
| XhsPublisher.validate() 空标题 → 错误 | `xiaohongshu.py:58-69` | `test_empty_title_returns_error` — 断言 `"标题不能为空"` in errors |
| XhsPublisher.validate() 标题>20字 → 错误 | `xiaohongshu.py:58-69` | `test_title_too_long_returns_error` — 断言 `"标题不能超过20字"` in errors |
| XhsPublisher.validate() 6标签 → 错误 | `xiaohongshu.py:58-69` | `test_too_many_tags_returns_error` — 断言 `"标签不能超过5个"` in errors |
| XhsPublisher.validate() 合法内容 → 空列表 | `xiaohongshu.py:58-69` | `test_valid_post_returns_empty` — 断言 `errors == []` |
| XhsPublisher.publish() 在 fill_form 后 ops 含 click | `xiaohongshu.py:71-75` | `test_publish_after_fill_form_clicks` — 断言 click_ops 有 1 条，selector 为 "#publish-btn" |
| DyPublisher.fill_form() 注入引擎后 ops 含 navigate+fill_form | `douyin.py:36-58` | `test_fill_form_records_ops` — 断言 op_names 包含 navigate 和 fill_form |
| DyPublisher.validate() 标题>55字 → 违规 | `douyin.py:62-73` | `test_title_too_long_returns_error` — 断言 `"标题不能超过55字"` in errors |
| DyPublisher.validate() video_path=None → 违规 | `douyin.py:62-73` | `test_no_video_returns_error` — 断言 `"视频文件路径不能为空"` in errors |
| DyPublisher.validate() 合法内容 → 空列表 | `douyin.py:62-73` | `test_valid_post_returns_empty` — 断言 `errors == []` |
| HumanGate.generate_preview() 含平台/标题/标签 | `human_gate.py:60-85` | `test_preview_contains_platform_and_title` — 断言预览含平台、标题、标签、图片数 |
| HumanGate.request_confirm() 注入 Y → CONFIRM | `human_gate.py:87-103` | `test_yes_returns_confirm` — 断言 decision == GateDecision.CONFIRM |
| HumanGate.request_confirm() 注入 N → ABORT | `human_gate.py:87-103` | `test_no_returns_abort` — 断言 decision == GateDecision.ABORT |
| HumanGate.request_confirm() 注入 E → EDIT | `human_gate.py:87-103` | `test_edit_returns_edit` — 断言 decision == GateDecision.EDIT |
| HumanGate.request_confirm() 无效输入 → 重试 | `human_gate.py:87-103` | `test_invalid_then_valid_retries` — 注入 `["x", "?", "Y"]`，最终 CONFIRM |
| HumanGate.is_auto_publish_disabled() → True | `human_gate.py:105-107` | `test_is_auto_publish_disabled_returns_true` — 断言 `== True` |

## 4 我踩的坑

| 坑 | 说明 |
|----|----|
| **卡在哪** | 第一个测试运行就炸：`HumanGate.generate_preview` 在 `schedule_time=None` 时显示字面 "None" 而非 "立即" |
| **卡多久** | 5 分钟（从首次运行到定位修复） |
| **怎么绕过** | 原来是 `post_summary.get("schedule_time", "立即")` — 当 `schedule_time` 作为 key 存在但值为 None 时，`.get()` 的默认值不生效。改为 `schedule = post_summary.get("schedule_time"); schedule if schedule else "立即"` |
| **重来先做什么** | 测试里对 `None` 值的边界要专门写断言，不要只测有值场景。`get()` 的默认值只在 key 缺失时生效，value 为 None 时不算缺失 |
| **并发文件冲突** | Lane A/B/D 与 Lane C 共享 worktree（未设 isolation）。browser/ 和 publish/ 的初始文件是其他车道写的。commit 前必须 `git ls-files` 确认哪些是已跟踪的，哪些是自己的，避免误提交他人文件。**第二次 commit 前 stgats 发现有 `publish/tests/__init__.py` 已被 Lane D 提交，还好我提前检查了 staged 列表** |

RISK: 最可能出问题的是 `HumanGate.request_confirm()` 的 input_fn 注入 — 如果生产环境 input() 被占用或阻塞，整个发布流程会卡住。建议后续加超时兜底。