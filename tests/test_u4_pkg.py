"""U4 packaging: version and build directory (CONTRACT.md: U4)."""
import json
import os
import stat
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from harness import work_dir

ROOT = Path(__file__).resolve().parents[1]
APP = "com.leebase.LcosNotes"


def test_project_version(tmp_path):
    out = subprocess.run(["meson", "introspect", "--projectinfo", str(ROOT / "meson.build")],
                         capture_output=True, text=True, check=True, cwd=ROOT).stdout
    assert json.loads(out)["version"] == "1.1.0"                   # CONTRACT.md U10
    releases = [r.get("version") for r in ET.parse(ROOT / "data" / f"{APP}.metainfo.xml").getroot().iter("release")]
    assert {"1.1.0", "1.0.0", "0.10.0", "0.9.0", "0.8.0", "0.7.0", "0.6.0", "0.5.0", "0.4.0", "0.3.0"} <= set(releases)


def _setup_dir(tmp_path, tmpdir):
    """Run build-deb.sh with a meson that records its arguments and stops the build."""
    shim = tmp_path / "shim"
    shim.mkdir()
    log = tmp_path / "meson.log"
    (shim / "meson").write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{log}"\nexit 1\n')
    (shim / "meson").chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k != "TMPDIR"}
    env["PATH"] = f"{shim}:{env.get('PATH', '/usr/bin:/bin')}"
    if tmpdir is not None:
        env["TMPDIR"] = str(tmpdir)
    proc = subprocess.run(["bash", "packaging/build-deb.sh", str(tmp_path / "out")], cwd=ROOT, env=env,
                          capture_output=True, timeout=120)
    assert proc.returncode != 0
    first = log.read_text().splitlines()[0].split()
    assert first[0] == "setup", first
    return Path(first[1])


def _under(path, parent):
    return os.path.realpath(path).startswith(os.path.realpath(parent) + os.sep)


def test_build_dir_under_callers_tmpdir(tmp_path):
    t = Path(work_dir()) / "callers-tmp"
    t.mkdir(exist_ok=True)
    build = _setup_dir(tmp_path, t)
    assert _under(build, t), build
    assert list(t.iterdir()) == [], "the temporary directory is removed"


@pytest.mark.parametrize("case", ["unset", "empty", "missing", "inside"])
def test_build_dir_falls_back_to_tmp(tmp_path, case):
    value = {"unset": None, "empty": "", "missing": tmp_path / "nope", "inside": ROOT / "tests"}[case]
    before = sorted(p.name for p in (ROOT / "tests").iterdir())
    build = _setup_dir(tmp_path, value)
    assert _under(build, "/tmp"), build
    assert not _under(build, ROOT)
    assert sorted(p.name for p in (ROOT / "tests").iterdir()) == before
