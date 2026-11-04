"""U3 install and package (CONTRACT.md: U3 > Install and package)."""
import gzip
import hashlib
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from harness import XSession, copy_vault, title, work_dir

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.9.0"                                          # CONTRACT.md U4-U9
APP = "com.leebase.LcosNotes"
INSTALLED = {
    "usr/bin/lcos-notes", "usr/bin/lcos-notes-cli",
    f"usr/share/applications/{APP}.desktop",
    f"usr/share/metainfo/{APP}.metainfo.xml",
    f"usr/share/icons/hicolor/scalable/apps/{APP}.svg",
    "usr/share/man/man1/lcos-notes.1", "usr/share/man/man1/lcos-notes-cli.1",
}
PACKAGED = {p + ".gz" if p.startswith("usr/share/man/") else p for p in INSTALLED} | {
    "usr/share/doc/lcos-notes/copyright"}


def _source_digest():
    out = {}
    for path in sorted(ROOT.rglob("*")):
        rel = path.relative_to(ROOT).as_posix()
        if rel.split("/")[0] == ".git" or "__pycache__" in rel.split("/") or ".pytest_cache" in rel:
            continue
        out[rel] = "dir" if path.is_dir() else hashlib.sha256(path.read_bytes()).hexdigest()
    return out


@pytest.fixture(scope="module")
def deb():
    out = Path(tempfile.mkdtemp(prefix="deb-", dir=work_dir()))
    before = _source_digest()
    proc = subprocess.run(["bash", "packaging/build-deb.sh", str(out)], cwd=ROOT,
                          capture_output=True, timeout=900)
    assert proc.returncode == 0, proc.stderr.decode()[-4000:]
    assert _source_digest() == before, "build-deb.sh must not write inside the source tree"
    arch = subprocess.run(["dpkg", "--print-architecture"], capture_output=True, text=True,
                          check=True).stdout.strip()
    assert sorted(p.name for p in out.iterdir()) == [f"lcos-notes_{VERSION}_{arch}.deb"]
    path = out / f"lcos-notes_{VERSION}_{arch}.deb"
    root = out / "x"
    subprocess.run(["dpkg-deb", "-x", str(path), str(root)], check=True)
    return {"path": path, "arch": arch, "root": root}


def _field(deb, name):
    return subprocess.run(["dpkg-deb", "-f", str(deb["path"]), name], capture_output=True, text=True,
                          check=True).stdout.rstrip("\n")


def test_control_fields(deb):
    assert _field(deb, "Package") == "lcos-notes"
    assert _field(deb, "Version") == VERSION
    assert _field(deb, "Architecture") == deb["arch"]
    assert _field(deb, "Maintainer") == "Lee Harrington <lee@leebase.com>"
    assert _field(deb, "Section") == "editors"
    assert _field(deb, "Priority") == "optional"
    assert int(_field(deb, "Installed-Size")) > 0
    desc = _field(deb, "Description").split("\n")
    assert desc[0].strip() and len(desc) >= 2 and all(line.startswith(" ") for line in desc[1:])
    depends = [d.strip().split(" ")[0] for d in _field(deb, "Depends").split(",")]
    # CONTRACT.md U7: cmark-gfm and its extensions replace cmark.
    for prefix in ("libc6", "libgtkmm-3.0-1", "libgtksourceviewmm-3.0-0", "libcmark-gfm0.29.0",
                   "libcmark-gfm-extensions0.29.0"):
        assert any(d.startswith(prefix) for d in depends), (prefix, depends)
    assert not any(d.startswith("libcmark0") for d in depends), depends


def test_contents_owners_and_modes(deb):
    listing = subprocess.run(["dpkg-deb", "-c", str(deb["path"])], capture_output=True, text=True,
                             check=True).stdout.splitlines()
    files = set()
    for line in listing:
        mode, owner, _size, _date, _time, name = line.split(None, 5)
        assert owner == "root/root", line
        name = name.removeprefix("./").rstrip("/")
        if mode.startswith("d"):
            assert mode == "drwxr-xr-x", line
            continue
        expected = "-rwxr-xr-x" if name.startswith("usr/bin/") else "-rw-r--r--"
        assert mode == expected, line
        files.add(name)
    assert files == PACKAGED


def test_binaries_are_stripped_and_work(deb, tmp_path):
    for exe in ("lcos-notes", "lcos-notes-cli"):
        sections = subprocess.run(["readelf", "-S", str(deb["root"] / "usr/bin" / exe)], capture_output=True,
                                  text=True, check=True).stdout
        assert ".debug_info" not in sections and ".symtab" not in sections, exe
    v = copy_vault(tmp_path / "v")
    proc = subprocess.run([str(deb["root"] / "usr/bin/lcos-notes-cli"), "notes", str(v)], capture_output=True,
                          text=True, check=True)
    assert proc.stdout.startswith('["Archive/2025/Deep.md","Caf')
    proc = subprocess.run([str(deb["root"] / "usr/bin/lcos-notes-cli"), "render", str(v), "Ideas.md"],
                          capture_output=True, text=True, check=True)
    assert proc.stdout.startswith('{"text":"Ideas')


def test_packaged_gui_runs_with_window_manager_frame(deb, tmp_path):
    v = copy_vault(tmp_path / "v")
    with XSession() as x:
        app = x.launch([str(deb["root"] / "usr/bin/lcos-notes"), "--vault", str(v), "Home.md"])
        row = app.focus(title("Home"))
        assert row["frame"] is True
        assert row["csd"] is False
        app.close(title("Home"))


def _keyfile(path):
    import gi
    gi.require_version("GLib", "2.0")
    from gi.repository import GLib
    kf = GLib.KeyFile()
    kf.load_from_file(str(path), GLib.KeyFileFlags.NONE)
    return kf


def test_desktop_entry(deb):
    kf = _keyfile(deb["root"] / f"usr/share/applications/{APP}.desktop")
    g = "Desktop Entry"
    assert kf.get_string(g, "Type") == "Application"
    assert kf.get_string(g, "Name") == "LCOS Notes"
    assert kf.get_string(g, "Comment").strip()
    assert kf.get_string(g, "Exec") == "lcos-notes"
    assert kf.get_string(g, "Icon") == APP
    assert kf.get_boolean(g, "Terminal") is False
    cats = kf.get_string_list(g, "Categories")
    assert "Office" in cats and "TextEditor" in cats


def test_metainfo_validates(deb):
    path = deb["root"] / f"usr/share/metainfo/{APP}.metainfo.xml"
    proc = subprocess.run(["appstreamcli", "validate", "--no-net", str(path)], capture_output=True, text=True,
                          env={**os.environ, "HOME": str(work_dir())})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    root = ET.parse(path).getroot()
    assert root.tag == "component" and root.get("type") == "desktop-application"
    assert root.findtext("id") == APP
    assert root.findtext("metadata_license") == "CC0-1.0"
    assert root.findtext("project_license") == "Apache-2.0"                  # D529
    launch = root.find("launchable")
    assert launch is not None and launch.get("type") == "desktop-id" and launch.text == f"{APP}.desktop"
    assert [u.text for u in root.findall("url") if u.get("type") == "homepage"] == ["https://leebase.com/"]
    assert root.find("content_rating").get("type") == "oars-1.1"
    assert VERSION in [r.get("version") for r in root.iter("release")]


def test_icon_is_vector_only(deb):
    svg = (deb["root"] / f"usr/share/icons/hicolor/scalable/apps/{APP}.svg").read_text()
    root = ET.fromstring(svg)
    assert root.tag in ("svg", "{http://www.w3.org/2000/svg}svg")
    tags = {el.tag.split("}")[-1] for el in root.iter()}
    assert not tags & {"image", "text", "tspan", "foreignObject"}, tags
    assert "data:" not in svg


def test_man_pages_and_copyright(deb):
    for page in ("lcos-notes.1.gz", "lcos-notes-cli.1.gz"):
        raw = (deb["root"] / "usr/share/man/man1" / page).read_bytes()
        assert raw[4:8] == b"\0\0\0\0", "gzip -n: no timestamp"
        assert gzip.decompress(raw).decode().lstrip().startswith((".TH", "'\\\"", ".\\\"")), page
        assert ".TH" in gzip.decompress(raw).decode()
    text = (deb["root"] / "usr/share/doc/lcos-notes/copyright").read_text()
    assert text.startswith("Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/")
    assert "Copyright: 2026 Lee Harrington" in text
    assert "License: Apache-2.0" in text                                    # D529


def test_meson_install_set(tmp_path):
    b, d = tmp_path / "b", tmp_path / "d"
    subprocess.run(["meson", "setup", str(b), str(ROOT), "--prefix=/usr"], check=True, capture_output=True)
    subprocess.run(["meson", "compile", "-C", str(b)], check=True, capture_output=True)
    subprocess.run(["meson", "install", "-C", str(b), "--destdir", str(d)], check=True, capture_output=True)
    files = {p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file()}
    assert files == INSTALLED
