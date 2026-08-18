# DAY2-A-PACKET.md · Lane A 浏览器反检测底座

## 1. 完成概况

按分派包 `DAY2-A-PACKET.md` 实现积木⑤ browser 反检测底座的全部内容：

| 模块 | 文件 | 说明 |
|------|------|------|
| 引擎抽象层 | `browser/engine.py` | `BrowserConfig` + `AbstractBrowserEngine`(8 抽象方法) + `UnittestEngine`(离线测试桩) + `PlaywrightEngine`(惰性初始化占位) + `engine_factory(name)` |
| 真人行为模拟器 | `browser/humanize.py` | `generate_bezier_path`(三次贝塞尔弯曲鼠标路径) + `human_type`(打字错误/退格/修正) + `random_pause`(对数正态分布停留) + `mouse_jitter`(高斯抖动) |
| 包入口 | `browser/__init__.py` | 导出全部公共符号 |
| 测试目录 | `browser/tests/__init__.py` | 测试包初始化 |
| 引擎测试 | `browser/tests/test_engine.py` | 11 个测试用例，覆盖工厂/配置/8 方法 ops 记录/Playwright 零依赖/抽象基类不可实例化 |
| 行为测试 | `browser/tests/test_humanize.py` | 16 个测试用例，覆盖贝塞尔路径/键盘输入/停留/抖动 |

### 影响面

- 新建模块 `browser/` 包，不涉及任何现有模块更改
- 零第三方依赖，仅 Python 3.9+ 标准库
- 后续发动机 ⑦ (session) 可通过 `browser.engine.engine_factory("unittest")` 使用
- 不触碰订单/资金/KYC/Design Tokens 等任何跨模块领域

## 2. 测试结果

```
platform win32 -- Python 3.9.7, pytest-6.2.4, py-1.10.0, pluggy-0.13.1
rootdir: D:\llm\marketing-agent\marketing-agent

browser/tests/test_engine.py::TestEngineFactory::test_factory_playwright PASSED
browser/tests/test_engine.py::TestEngineFactory::test_factory_unittest    PASSED
browser/tests/test_engine.py::TestEngineFactory::test_factory_unknown_raises PASSED
browser/tests/test_engine.py::TestBrowserConfig::test_custom_values      PASSED
browser/tests/test_engine.py::TestBrowserConfig::test_default_values     PASSED
browser/tests/test_engine.py::TestUnittestEngine::test_all_8_methods_record_ops PASSED
browser/tests/test_engine.py::TestUnittestEngine::test_initialize_records_op PASSED
browser/tests/test_engine.py::TestUnittestEngine::test_reset_clears_ops  PASSED
browser/tests/test_engine.py::TestUnittestEngine::test_storage_state_preserved_across_save_load PASSED
browser/tests/test_engine.py::TestPlaywrightEngine::test_can_instantiate_without_playwright PASSED
browser/tests/test_engine.py::TestAbstractBase::test_abstract_cannot_instantiate PASSED
browser/tests/test_humanize.py::TestBezierPath::test_first_and_last_points_match PASSED
browser/tests/test_humanize.py::TestBezierPath::test_jitter_affects_inner_points PASSED
browser/tests/test_humanize.py::TestBezierPath::test_minimum_steps       PASSED
browser/tests/test_humanize.py::TestBezierPath::test_path_is_not_straight_line PASSED
browser/tests/test_humanize.py::TestBezierPath::test_returns_correct_number_of_steps PASSED
browser/tests/test_humanize.py::TestHumanType::test_each_char_has_delay_ms PASSED
browser/tests/test_humanize.py::TestHumanType::test_high_error_rate_has_corrected_keys PASSED
browser/tests/test_humanize.py::TestHumanType::test_output_length_with_errors PASSED
browser/tests/test_humanize.py::TestHumanType::test_returns_list_of_dicts_with_required_keys PASSED
browser/tests/test_humanize.py::TestHumanType::test_zero_error_rate_no_corrected_keys PASSED
browser/tests/test_humanize.py::TestRandomPause::test_min_equals_max    PASSED
browser/tests/test_humanize.py::TestRandomPause::test_returns_float     PASSED
browser/tests/test_humanize.py::TestRandomPause::test_within_range      PASSED
browser/tests/test_humanize.py::TestMouseJitter::test_offset_within_amplitude PASSED
browser/tests/test_humanize.py::TestMouseJitter::test_returns_tuple_of_ints PASSED
browser/tests/test_humanize.py::TestMouseJitter::test_zero_amplitude_no_offset PASSED

======================== 27 passed, 1 warning in 0.22s ========================
```

全部 27 个测试通过，0 失败 0 错误。

## 3. 文件清单

新建文件（6 个）：

| 文件 | 行数 | 说明 |
|------|------|------|
| `D:\llm\marketing-agent\marketing-agent\browser\__init__.py` | 28 | 包入口，导出所有公共符号 |
| `D:\llm\marketing-agent\marketing-agent\browser\engine.py` | 191 | 引擎抽象层 + 工厂 + 离线测试桩 |
| `D:\llm\marketing-agent\marketing-agent\browser\humanize.py` | 196 | 真人行为模拟器 4 函数 |
| `D:\llm\marketing-agent\marketing-agent\browser\tests\__init__.py` | 1 | 测试包初始化 |
| `D:\llm\marketing-agent\marketing-agent\browser\tests\test_engine.py` | 148 | 引擎 11 个测试用例 |
| `D:\llm\marketing-agent\marketing-agent\browser\tests\test_humanize.py` | 170 | 行为 16 个测试用例 |

## 4. 自查证据 — 验收标准逐条标注

### engine.py

| 验收标准 | 结果 | 证据 |
|----------|------|------|
| `engine_factory("unittest")` 返回 UnittestEngine 实例 | **PASS** | `test_factory_unittest` |
| `engine_factory("playwright")` 返回 PlaywrightEngine 实例 | **PASS** | `test_factory_playwright` |
| `engine_factory("unknown")` 抛出 ValueError | **PASS** | `test_factory_unknown_raises` |
| UnittestEngine 所有 8 个方法调用后 ops 记录正确操作名 | **PASS** | `test_all_8_methods_record_ops` — ops 顺序 = initialize/navigate/fill_form/click/screenshot/save_storage_state/load_storage_state/close |
| PlaywrightEngine 实例化不抛异常（不 import playwright） | **PASS** | `test_can_instantiate_without_playwright` — 无 import 错误 |
| BrowserConfig 默认值正确 | **PASS** | `test_default_values` — headless=True, locale="zh-CN", timezone="Asia/Shanghai" |

### humanize.py

| 验收标准 | 结果 | 证据 |
|----------|------|------|
| `generate_bezier_path((0,0), (100,100), 30)` 返回 30 对坐标 | **PASS** | `test_returns_correct_number_of_steps` |
| 贝塞尔路径首尾精确匹配 | **PASS** | `test_first_and_last_points_match` — 小数精度 5 位 |
| 贝塞尔路径不包含直线段（控制点随机偏移产生弯曲） | **PASS** | `test_path_is_not_straight_line` — 中间点 y ≠ 0 |
| `human_type("hello", wpm=60, error_rate=0)` 返回 list of dict，每键有 char/delay_ms/corrected | **PASS** | `test_returns_list_of_dicts_with_required_keys` + `test_zero_error_rate_no_corrected_keys` |
| `human_type("hello", wpm=60, error_rate=1.0)` 每键都标记 corrected=True | **PASS** | `test_high_error_rate_has_corrected_keys` — 50 字符全 corrected=True |
| `random_pause(200, 3000)` 返回 float 在 [200, 3000] 范围内 | **PASS** | `test_within_range` (100 次采样) + `test_returns_float` |
| `mouse_jitter((100, 100), 2)` 偏移在 [-2, 2] 范围内 | **PASS** | `test_offset_within_amplitude` (100 次采样) |

**结论**: 全部 13 条验收标准 **PASS**。

### 坑

1. **random_pause 返回 int 边界值**：`random_pause(200, 3000)` 在对数正态采样钳制后恰好等于 `min_ms` 时返回 `200` (int) 而非 `200.0` (float)，导致 `assertIsInstance(pause, float)` 报错。修复：`float(round(...))` 显式包装。

2. **sibling lane 文件冲突**：执行期间 Lane B 的 `test_cookie_store.py` 被写入我的测试目录，引用未创建的 `browser.cookie_store` 导致 `pytest browser/tests/` 全量运行失败。已通过只跑 `test_engine.py test_humanize.py` 规避，且 **commit 时未 staging 该文件**。

3. **Windows PYTHONIOENCODING**：`__init__.py` 和 `engine.py`/`humanize.py` 都含有 `_inject_utf8_stdout()` 兜底函数，确保 `reconfigure` 可用时设 UTF-8。

RISK: 贝塞尔弯曲路径的 `test_path_is_not_straight_line` 断言依赖随机性 — 理论上存在极小概率（控制点偏移恰好抵消为 0）导致假失败。如需消抖可设固定 `random.seed`，但当前测试 100% 稳定通过。