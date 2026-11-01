"""The test rig itself works: toolchain, Xvfb + xfwm4, window discovery, XTest input."""
import subprocess
from pathlib import Path

from harness import XSession, work_dir


def test_rig_window_frame_and_input():
    exe = work_dir() / "selftest_window"
    flags = subprocess.run(["pkg-config", "--cflags", "--libs", "gtkmm-3.0", "gtksourceviewmm-3.0"],
                           capture_output=True, text=True, check=True).stdout.split()
    source = Path(__file__).with_name("selftest_window.cpp")
    subprocess.run(["c++", "-std=c++17", "-w", "-o", str(exe), str(source), *flags], check=True)
    with XSession() as x:
        app = x.launch([str(exe)])
        row = app.focus("rig ready")
        assert row["frame"] is True and row["csd"] is False
        app.key("ctrl+o")
        app.wait_title("typed o")
        app.type("Q")
        app.wait_title("typed Q")
        app.key("alt+Return")
        app.wait_title("typed Return")
        app.close("typed Return")
