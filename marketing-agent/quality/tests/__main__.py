"""支持 ``python quality/tests/`` 直接运行测试。"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest


if __name__ == "__main__":
    # 直接执行目录时，unittest 不会自动把包名解析成可导入路径。
    quality_root = Path(__file__).resolve().parents[1]
    project_root = quality_root.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(Path(__file__).resolve().parent), pattern="test*.py"
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
