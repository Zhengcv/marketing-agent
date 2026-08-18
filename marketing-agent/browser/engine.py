"""browser 积木 ⑤ · 反检测底座 —— 浏览器引擎抽象层。

只定义接口契约 + 可离线验证的实现，不做真实浏览器操作
（无账号 / 代理 / 密钥）。真实浏览器引擎（invisible_playwright /
patchright）后续在真机环境按其实现此接口即可接入。

接口契约（冻结，同 .day/packets/DAY2-A-PACKET.md §2.1）：
    - BrowserConfig        启动配置（headless/proxy/user_agent/viewport/locale/timezone）
    - AbstractBrowserEngine 8 个抽象方法（initialize/navigate/fill_form/click/
                             screenshot/save_storage_state/load_storage_state/close）
    - UnittestEngine        测试用空实现，记录 ops 日志，零外部依赖可离线跑
    - PlaywrightEngine      invisible_playwright 适配器（惰性初始化，不含真实逻辑）
    - engine_factory(name)  工厂方法

零第三方依赖，仅使用 Python 3.9+ 标准库。
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


def _inject_utf8_stdout() -> None:
    """确保 stdout/stderr 使用 UTF-8（Windows 控制台 GBK 兜底）。"""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001 - 兜底，失败不影响运行
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            pass


_inject_utf8_stdout()


# ── 配置 ──────────────────────────────────────────────────────────────────────


@dataclass
class BrowserConfig:
    """浏览器引擎启动配置。

    默认值即反检测底座要求的稳定指纹基线：
        headless=True, locale="zh-CN", timezone_id="Asia/Shanghai",
        viewport={"width": 1280, "height": 800}。
    """

    headless: bool = True
    proxy: Optional[str] = None
    user_agent: Optional[str] = None
    viewport: dict = field(default_factory=lambda: {"width": 1280, "height": 800})
    locale: str = "zh-CN"
    timezone_id: str = "Asia/Shanghai"
    extra_args: dict = field(default_factory=dict)


# ── 抽象接口 ──────────────────────────────────────────────────────────────────


class AbstractBrowserEngine(ABC):
    """浏览器引擎抽象接口。所有具体引擎（invisible_playwright / patchright）必须实现此接口。"""

    #: 实现层标识，供日志/工厂/审计使用（如 "invisible_playwright"）。
    name: str = "abstract"

    @abstractmethod
    def initialize(self, config: BrowserConfig) -> None:
        """启动浏览器实例，应用反指纹配置。"""
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def navigate(self, url: str) -> None:
        """导航到指定 URL。"""
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def fill_form(self, fields: dict) -> None:
        """按 selector → value 字典填入表单。"""
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def click(self, selector: str) -> None:
        """点击元素。"""
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def screenshot(self, path: str) -> None:
        """截取全页截图，保存到 path。"""
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def save_storage_state(self, path: str) -> None:
        """保存当前浏览器登录态（cookies + localStorage）到 JSON 文件。"""
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def load_storage_state(self, path: str) -> None:
        """从 JSON 文件恢复浏览器登录态。"""
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def close(self) -> None:
        """关闭浏览器实例。"""
        raise NotImplementedError  # pragma: no cover


# ── 通过抽象方法反向保证 8 个契约方法齐全 ──────────────────────────────────────
_ABSTRACT_METHODS = [m for m in vars(AbstractBrowserEngine) if getattr(getattr(AbstractBrowserEngine, m), "__isabstractmethod__", False)]
assert _ABSTRACT_METHODS == [
    "initialize",
    "navigate",
    "fill_form",
    "click",
    "screenshot",
    "save_storage_state",
    "load_storage_state",
    "close",
], f"AbstractBrowserEngine 抽象方法清单与冻结契约不一致: {_ABSTRACT_METHODS}"


def _record(op: str, **kwargs: Any) -> dict:
    """构造一条操作日志记录。"""
    return {"op": op, **kwargs}


# ── 离线测试桩 ────────────────────────────────────────────────────────────────


class UnittestEngine(AbstractBrowserEngine):
    """测试用空实现，所有方法记录操作日志但不启动真实浏览器。

    核心契约：不 import 任何第三方库，可完全离线运行；
    每次方法调用 append 一条 dict 到 ``ops``，供测试断言调用顺序/参数。
    """

    name = "unittest"

    def __init__(self) -> None:
        self.ops: list = []
        self._storage_state: Optional[dict] = None

    def initialize(self, config: BrowserConfig) -> None:
        self._config = config
        self.ops.append(_record("initialize", config=config))

    def navigate(self, url: str) -> None:
        self.ops.append(_record("navigate", url=url))

    def fill_form(self, fields: dict) -> None:
        self.ops.append(_record("fill_form", fields=fields))

    def click(self, selector: str) -> None:
        self.ops.append(_record("click", selector=selector))

    def screenshot(self, path: str) -> None:
        self.ops.append(_record("screenshot", path=path))

    def save_storage_state(self, path: str) -> None:
        if self._storage_state is None:
            self._storage_state = {"cookies": [], "localStorage": {}}
        self.ops.append(_record("save_storage_state", path=path))

    def load_storage_state(self, path: str) -> None:
        self._storage_state = {"cookies": [], "localStorage": {}, "source": path}
        self.ops.append(_record("load_storage_state", path=path))

    def close(self) -> None:
        self.ops.append(_record("close"))

    def reset(self) -> None:
        """清空 ops 与模拟登录态，便于用例间隔离。测试辅助方法。"""
        self.ops.clear()
        self._storage_state = None


# ── 真实引擎占位适配器 ─────────────────────────────────────────────────────────


class PlaywrightEngine(AbstractBrowserEngine):
    """invisible_playwright 适配器。TODO: 真机环境安装 playwright 后补全。

    惰性初始化：仅在 initialize() 时按需 import playwright，保证
    模块级/实例化不依赖第三方库，离线可导入。
    """

    name = "playwright"

    def __init__(self) -> None:
        self._browser = None
        self._page = None
        self._playwright = None

    def _ensure_playwright(self) -> Any:
        """在真机环境按需导入 playwright（惰性，本地离线不触发）。"""
        if self._playwright is None:
            import playwright.sync_api  # noqa: PLC0415 - 惰性导入

            self._playwright = playwright.sync_api
        return self._playwright

    def initialize(self, config: BrowserConfig) -> None:  # pragma: no cover - 真机 TODO
        pw = self._ensure_playwright()
        self._playwright_sync = pw.sync_playwright().start()
        launch_args = {"headless": config.headless}
        if config.proxy:
            launch_args["proxy"] = {"server": config.proxy}
        if config.user_agent:
            launch_args["user_agent"] = config.user_agent
        launch_args.update(config.extra_args if isinstance(config.extra_args, dict) else {})
        self._browser = self._playwright_sync.chromium.launch(**launch_args)
        context_args = {
            "viewport": config.viewport,
            "locale": config.locale,
            "timezone_id": config.timezone_id,
        }
        self._context = self._browser.new_context(**context_args)
        self._page = self._context.new_page()

    # TODO(patchright): 各方法真机环境补全，逻辑同 invisible_playwright 规范。
    def navigate(self, url: str) -> None:  # pragma: no cover
        self._page.goto(url)

    def fill_form(self, fields: dict) -> None:  # pragma: no cover
        for selector, value in fields.items():
            self._page.fill(selector, value)

    def click(self, selector: str) -> None:  # pragma: no cover
        self._page.click(selector)

    def screenshot(self, path: str) -> None:  # pragma: no cover
        self._page.screenshot(path=path, full_page=True)

    def save_storage_state(self, path: str) -> None:  # pragma: no cover
        state = self._context.storage_state()
        with open(path, "w", encoding="utf-8") as fh:
            import json

            json.dump(state, fh, ensure_ascii=False, indent=2)

    def load_storage_state(self, path: str) -> None:  # pragma: no cover
        # TODO(patchright): 用 _context.storage_state(path=path) 恢复完整登录态
        self._context.add_cookies([])

    def close(self) -> None:  # pragma: no cover
        if self._browser is not None:
            self._browser.close()
        if self._playwright_sync is not None:
            self._playwright_sync.stop()


# ── 工厂 ──────────────────────────────────────────────────────────────────────


def engine_factory(name: str = "unittest") -> AbstractBrowserEngine:
    """返回指定引擎实例。

    - ``"unittest"``    → UnittestEngine（离线测试默认，零第三方依赖）
    - ``"playwright"``  → PlaywrightEngine（需真机 playwright，惰性初始化）
    - ``"patchright"``  → 占位：TODO 真机环境接入后映射到 PlaywrightEngine
    - 其他              → 抛 ValueError

    >>> engine_factory("unknown")
    Traceback (most recent call last):
        ...
    ValueError: Unknown browser engine: unknown
    """
    if name == "unittest":
        return UnittestEngine()
    if name == "playwright":
        return PlaywrightEngine()
    if name == "patchright":
        # TODO: 补丁版 playwright 接入前先用占位适配器，避免暴露调用侧差异。
        return PlaywrightEngine()
    raise ValueError(f"Unknown browser engine: {name}")


__all__ = [
    "BrowserConfig",
    "AbstractBrowserEngine",
    "UnittestEngine",
    "PlaywrightEngine",
    "engine_factory",
]