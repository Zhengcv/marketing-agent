"""browser 积木 ⑤ · 反检测底座。

引擎抽象层 + 真人行为模拟器。零第三方依赖，仅 Python 3.9+ 标准库。
"""

from .engine import (
    AbstractBrowserEngine,
    BrowserConfig,
    PlaywrightEngine,
    UnittestEngine,
    engine_factory,
)
from .humanize import (
    generate_bezier_path,
    human_type,
    mouse_jitter,
    random_pause,
)

__all__ = [
    "AbstractBrowserEngine",
    "BrowserConfig",
    "UnittestEngine",
    "PlaywrightEngine",
    "engine_factory",
    "generate_bezier_path",
    "human_type",
    "random_pause",
    "mouse_jitter",
]