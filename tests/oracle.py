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
    "acceptance": ["tests/test_core.py", "tests/test_gui.py", "tests/test_u2_core.py", "tests/test_u2_gui.py",
                   "tests/test_u3_core.py", "tests/test_u3_gui.py", "tests/test_u3_pkg.py",
                   "tests/test_u4_core.py", "tests/test_u4_gui.py", "tests/test_u4_pkg.py"],
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in SUITES:
        sys.exit("usage: oracle.py " + "|".join(SUITES))
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "DISPLAY")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    argv = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "--rootdir", str(ROOT), *SUITES[sys.argv[1]]]
    sys.exit(subprocess.run(argv, cwd=ROOT, env={**env, "PYTHONPATH": str(ROOT / "tests")}).returncode)
