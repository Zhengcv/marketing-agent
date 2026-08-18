"""browser 积木 ⑤ · 反检测底座 —— 真人行为模拟器。

纯算法实现，零第三方依赖，仅使用 Python 3.9+ 标准库。所有函数可离线
验证，不触发真实浏览器操作。

函数清单（契约同 .day/packets/DAY2-A-PACKET.md §2.2）：
    - generate_bezier_path(start, end, steps, jitter) → 贝塞尔鼠标路径
    - human_type(text, wpm, error_rate) → 逐字键盘输入记录
    - random_pause(min_ms, max_ms) → 对数正态分布随机停留
    - mouse_jitter(position, amplitude) → 位置微小抖动
"""

from __future__ import annotations

import math
import random
import sys
from typing import Dict, List, Optional, Tuple


def _inject_utf8_stdout() -> None:
    """确保 stdout/stderr 使用 UTF-8（Windows 控制台 GBK 兜底）。"""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001 - 兜底
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            pass


_inject_utf8_stdout()


# ── 贝塞尔鼠标路径 ────────────────────────────────────────────────────────────


def _random_control_point(
    start: Tuple[float, float],
    end: Tuple[float, float],
) -> Tuple[float, float]:
    """生成三次贝塞尔曲线的两个控制点，产生自然弯曲偏向。

    控制点位置在起点-终点连线的垂直方向随机偏移，偏移量正比于
    两点距离的 1/3 到 2/3 之间的随机比例，确保弯曲自然。
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dist = math.hypot(dx, dy)

    # 垂直方向单位向量
    if dist < 1e-6:
        # 零距离：随机偏移
        angle = random.uniform(0, 2 * math.pi)
        perp = (math.cos(angle), math.sin(angle))
    else:
        perp = (-dy / dist, dx / dist)

    # 控制点偏移量：距离的 10%~40%，随机方向
    offset = random.uniform(0.1, 0.4) * dist * random.choice([-1, 1])

    # 第一个控制点偏向前 1/3 段，第二个偏向 2/3 段
    cp1 = (
        start[0] + dx * 0.33 + perp[0] * offset * random.uniform(0.5, 1.5),
        start[1] + dy * 0.33 + perp[1] * offset * random.uniform(0.5, 1.5),
    )
    cp2 = (
        start[0] + dx * 0.66 + perp[0] * offset * random.uniform(0.5, 1.5) * -1,
        start[1] + dy * 0.66 + perp[1] * offset * random.uniform(0.5, 1.5) * -1,
    )

    return cp1, cp2


def _cubic_bezier(
    t: float,
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    p3: Tuple[float, float],
) -> Tuple[float, float]:
    """三次贝塞尔曲线插值，t ∈ [0, 1]。"""
    u = 1 - t
    x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
    y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
    return (x, y)


def generate_bezier_path(
    start: Tuple[int, int],
    end: Tuple[int, int],
    steps: int = 30,
    jitter: float = 3.0,
) -> List[Tuple[float, float]]:
    """生成贝塞尔曲线鼠标移动路径。

    使用三次贝塞尔曲线插值，控制点随机偏移产生自然弯曲。
    最后在每个点上附加微小抖动（jitter 振幅），模拟人手震颤。

    Args:
        start: 起点坐标 (x, y)。
        end: 终点坐标 (x, y)。
        steps: 路径采样点数（含起点和终点）。
        jitter: 每个点附加的高斯抖动振幅（像素）。

    Returns:
        steps 个 (x, y) 坐标列表，首尾精确匹配 start/end。
    """
    if steps < 2:
        steps = 2

    p0 = (float(start[0]), float(start[1]))
    p3 = (float(end[0]), float(end[1]))

    cp1, cp2 = _random_control_point(p0, p3)

    path: List[Tuple[float, float]] = []
    for i in range(steps):
        t = i / (steps - 1)
        x, y = _cubic_bezier(t, p0, cp1, cp2, p3)

        # 抖动：除首尾外附加高斯噪声
        if 0 < i < steps - 1 and jitter > 0:
            x += random.gauss(0, jitter / 3)
            y += random.gauss(0, jitter / 3)

        path.append((x, y))

    # 强制首尾精确匹配输入
    path[0] = (float(start[0]), float(start[1]))
    path[-1] = (float(end[0]), float(end[1]))

    return path


# ── 真人键盘输入 ──────────────────────────────────────────────────────────────


def human_type(
    text: str,
    wpm: int = 60,
    error_rate: float = 0.02,
) -> List[Dict]:
    """模拟真人逐字键盘输入。

    每键记录 ``char``、``delay_ms``（距上一键的延迟）、``corrected``
    （是否因纠正重打）。以 error_rate 概率模拟打错 → 退格 → 修正。

    ``wpm`` 控制平均打字速度（words per minute，1 word = 5 chars），
    延迟按对数正态分布随机化。

    Args:
        text: 要输入的文本。
        wpm: 打字速度（词/分钟，1 词 = 5 字符）。默认 60。
        error_rate: 每一键打错的概率 [0, 1]。默认 0.02（2%）。

    Returns:
        list of dict，每键一条：{char, delay_ms, corrected}。
    """
    if wpm < 1:
        wpm = 1
    error_rate = max(0.0, min(1.0, error_rate))

    # 平均每键延迟（毫秒）：1 word = 5 chars, wpm 词/分钟
    avg_delay_ms = 60000.0 / (wpm * 5.0)

    keys: List[Dict] = []
    i = 0
    while i < len(text):
        char = text[i]

        # 决定是否打错（error_rate 概率，但不包括空格、回车等）
        should_err = False
        if error_rate > 0 and char not in (" ", "\n", "\t"):
            should_err = random.random() < error_rate

        if should_err:
            # 选一个和原字符不同的随机字符
            wrong_char = _random_typo(char)
            delay = _lognormal_delay(avg_delay_ms)
            keys.append({"char": wrong_char, "delay_ms": delay, "corrected": False})

            # 退格（删除错误字符）
            backspace_delay = _lognormal_delay(avg_delay_ms * 0.6)
            keys.append({"char": "[BACKSPACE]", "delay_ms": backspace_delay, "corrected": False})

            # 重新输入正确字符
            corrected_delay = _lognormal_delay(avg_delay_ms * 1.2)
            keys.append({"char": char, "delay_ms": corrected_delay, "corrected": True})
        else:
            delay = _lognormal_delay(avg_delay_ms)
            keys.append({"char": char, "delay_ms": delay, "corrected": False})

        i += 1

    return keys


def _random_typo(char: str) -> str:
    """生成一个与 char 不同的随机字符（同键盘行或 ASCII 邻近）。"""
    # 常见 QWERTY 键盘行
    rows = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
    for row in rows:
        if char.lower() in row:
            idx = row.index(char.lower())
            # 从前后邻居中选一个，确保不同
            candidates = [c for c in row[max(0, idx - 1) : idx + 2] if c != char.lower()]
            if candidates:
                typo = random.choice(candidates)
                return typo.upper() if char.isupper() else typo
    # 回退：ASCII 偏移
    return chr(ord(char) + random.choice([-1, 1]))


def _lognormal_delay(mean_ms: float, sigma: float = 0.4) -> float:
    """生成对数正态分布的延迟（毫秒）。

    Args:
        mean_ms: 目标均值（毫秒）。
        sigma: 对数正态分布的标准差参数（默认 0.4，经验值）。

    Returns:
        延迟值（毫秒，float），最小 10ms。
    """
    # 对数正态分布：mu = ln(mean^2 / sqrt(var + mean^2))，sigma 直接给定
    # 这里简化：用均值 * exp(N(0, sigma) - sigma^2/2) 得到均值为 mean_ms 的采样
    raw = mean_ms * math.exp(random.gauss(0, sigma) - sigma**2 / 2)
    return max(10.0, round(raw, 1))


# ── 随机停留 ─────────────────────────────────────────────────────────────────


def random_pause(min_ms: int = 200, max_ms: int = 3000) -> float:
    """生成随机停留时间（毫秒）。

    使用对数正态分布，偏向短停留（人类浏览行为特征：少量长停顿，
    大量短停顿）。

    Args:
        min_ms: 最小停留时间（毫秒）。
        max_ms: 最大停留时间（毫秒）。

    Returns:
        [min_ms, max_ms] 范围内的浮点数（毫秒）。
    """
    min_ms = max(1, min_ms)
    if max_ms <= min_ms:
        return float(min_ms)

    # 对数正态采样：设定 mu 偏向低值
    mean = min_ms + (max_ms - min_ms) * 0.25
    sigma = 1.2

    # 反转：从对数正态采样，钳制到 [min_ms, max_ms]
    # 对数正态的 mu = ln(mean) - sigma^2/2
    mu = math.log(mean) - sigma**2 / 2
    value = math.exp(random.gauss(mu, sigma))

    # 用 float 包裹确保即使钳制后等于整数边界也返回 float
    return float(round(max(float(min_ms), min(float(max_ms), value)), 1))


# ── 鼠标抖动 ─────────────────────────────────────────────────────────────────


def mouse_jitter(
    position: Tuple[int, int],
    amplitude: int = 2,
) -> Tuple[int, int]:
    """在给定位置附近添加微小抖动，模拟真人手部微颤。

    Args:
        position: 原始坐标 (x, y)。
        amplitude: 最大偏移像素数（正负区间）。

    Returns:
        抖动后坐标 (x, y)，偏移在 [-amplitude, amplitude] 范围内。
    """
    dx = random.randint(-amplitude, amplitude)
    dy = random.randint(-amplitude, amplitude)
    return (position[0] + dx, position[1] + dy)


__all__ = [
    "generate_bezier_path",
    "human_type",
    "random_pause",
    "mouse_jitter",
]