"""Oracle entry point: python3 tests/oracle.py <suite> (see SUITES)."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITES = {
    "selftest": ["tests/test_selftest.py"],
    "core": ["tests/test_core.py"],
    "gui": ["tests/test_gui.py"],
    "u1": ["tests/test_core.py", "tests/test_gui.py"],
    "u2core": ["tests/test_u2_core.py"],
    "u2gui": ["tests/test_u2_gui.py"],
    "u2": ["tests/test_u2_core.py", "tests/test_u2_gui.py"],
    "u3core": ["tests/test_u3_core.py"],
    "u3gui": ["tests/test_u3_gui.py"],
    "u3pkg": ["tests/test_u3_pkg.py"],
    "u3": ["tests/test_u3_core.py", "tests/test_u3_gui.py", "tests/test_u3_pkg.py"],
    "u3keep": ["tests/test_u3_core.py", "tests/test_u3_gui.py"],
    "u4core": ["tests/test_u4_core.py"],
    "u4gui": ["tests/test_u4_gui.py"],
    "u4pkg": ["tests/test_u4_pkg.py"],
    "guikeep": ["tests/test_u3_gui.py", "tests/test_u4_gui.py"],
    "u5core": ["tests/test_u5_core.py"],
    "u5gui": ["tests/test_u5_gui.py"],
    "guikeep2": ["tests/test_u3_gui.py", "tests/test_u4_gui.py", "tests/test_u5_gui.py"],
    "u6core": ["tests/test_u6_core.py"],
    "u6gui": ["tests/test_u6_gui.py"],
    "guikeep3": ["tests/test_u3_gui.py", "tests/test_u4_gui.py", "tests/test_u5_gui.py", "tests/test_u6_gui.py"],
    "u7core": ["tests/test_u7_core.py"],
    "u7gui": ["tests/test_u7_gui.py"],
    "guikeep4": ["tests/test_u3_gui.py", "tests/test_u4_gui.py", "tests/test_u5_gui.py", "tests/test_u6_gui.py",
                 "tests/test_u7_gui.py"],
    "corekeep": ["tests/test_core.py", "tests/test_u2_core.py", "tests/test_u6_core.py"],
    "refkeep": ["tests/test_u3_core.py", "tests/test_u4_core.py", "tests/test_u5_core.py", "tests/test_u7_core.py"],
    "u8core": ["tests/test_u8_core.py"],
    "u8gui": ["tests/test_u8_gui.py"],
    "acceptance": ["tests/test_core.py", "tests/test_gui.py", "tests/test_u2_core.py", "tests/test_u2_gui.py",
                   "tests/test_u3_core.py", "tests/test_u3_gui.py", "tests/test_u3_pkg.py",
                   "tests/test_u4_core.py", "tests/test_u4_gui.py", "tests/test_u4_pkg.py",
                   "tests/test_u5_core.py", "tests/test_u5_gui.py", "tests/test_u6_core.py", "tests/test_u6_gui.py",
                   "tests/test_u7_core.py", "tests/test_u7_gui.py", "tests/test_u8_core.py", "tests/test_u8_gui.py"],
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in SUITES:
        sys.exit("usage: oracle.py " + "|".join(SUITES))
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "DISPLAY")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    argv = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "--rootdir", str(ROOT), *SUITES[sys.argv[1]]]
    sys.exit(subprocess.run(argv, cwd=ROOT, env={**env, "PYTHONPATH": str(ROOT / "tests")}).returncode)
