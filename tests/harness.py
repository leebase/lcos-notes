"""Shared test harness: build, private X server with xfwm4, app driver."""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_VAULT = ROOT / "tests" / "fixtures" / "vault"
EM = "—"
_work = None


def work_dir() -> Path:
    global _work
    if _work is None:
        _work = Path(tempfile.mkdtemp(prefix="lcos-notes-tests-"))
    return _work


def build() -> Path:
    """meson setup + compile once per process; returns the build dir."""
    out = work_dir() / "build"
    if not (out / "build.ninja").exists():
        subprocess.run(["meson", "setup", str(out)], cwd=ROOT, check=True,
                       stdout=subprocess.DEVNULL)
    subprocess.run(["meson", "compile", "-C", str(out)], cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL)
    return out


def xdrive_bin() -> Path:
    out = work_dir() / "xdrive"
    if not out.exists():
        subprocess.run(["cc", "-O2", "-o", str(out), str(ROOT / "tests" / "xdrive.c"),
                        "-lX11", "-lXtst"], check=True)
    return out


def copy_vault(dest: Path) -> Path:
    """Copy the fixture and add the symlink note (symlinks are not stored in the
    repository because snapshot copies may dereference them)."""
    shutil.copytree(FIXTURE_VAULT, dest, symlinks=True)
    for current, _dirs, files in os.walk(dest):      # the source tree may be read-only
        os.chmod(current, 0o755)
        for name in files:
            os.chmod(os.path.join(current, name), 0o644)
    os.symlink("Home.md", dest / "Link.md")
    return dest


_shared_vault = None


def shared_vault() -> Path:
    """One read-only-by-convention copy of the fixture for tests that never write."""
    global _shared_vault
    if _shared_vault is None:
        _shared_vault = copy_vault(work_dir() / "shared-vault")
    return _shared_vault


def tree_digest(root: Path) -> dict:
    """Every entry under root: path -> ('dir'|'link:<target>'|sha256 of bytes)."""
    out = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            out[rel] = "link:" + os.readlink(path)
        elif path.is_dir():
            out[rel] = "dir"
        else:
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def cli(*args, check=True):
    exe = build() / "lcos-notes-cli"
    proc = subprocess.run([str(exe), *map(str, args)], capture_output=True, timeout=30)
    if check and proc.returncode != 0:
        raise AssertionError(f"cli {args} exit {proc.returncode}: {proc.stderr.decode()}")
    return proc


def cli_json(*args):
    proc = cli(*args)
    return json.loads(proc.stdout.decode("utf-8"))


class XSession:
    """Xvfb + xfwm4 on a private display, inside a private D-Bus session."""

    def __init__(self, screen="1024x768"):
        self.screen = screen
        self.home = Path(tempfile.mkdtemp(prefix="home-", dir=work_dir()))
        self.procs = []
        self.display = None

    def __enter__(self):
        for n in range(90, 140):
            if not Path(f"/tmp/.X11-unix/X{n}").exists() and not Path(f"/tmp/.X{n}-lock").exists():
                self.display = f":{n}"
                break
        xvfb = subprocess.Popen(["Xvfb", self.display, "-screen", "0", f"{self.screen}x24", "-nolisten", "tcp"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.procs.append(xvfb)
        deadline = time.monotonic() + 20
        while not Path(f"/tmp/.X11-unix/X{self.display[1:]}").exists():
            if time.monotonic() > deadline or xvfb.poll() is not None:
                raise RuntimeError("Xvfb did not start")
            time.sleep(0.05)
        self.env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "DISPLAY": self.display,
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_DATA_HOME": str(self.home / ".local" / "share"),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "LANG": "C.UTF-8",
            "GTK_THEME": "Adwaita",
            "NO_AT_BRIDGE": "1",
            "GSETTINGS_BACKEND": "memory",
        }
        # A private session bus keeps xfwm4/GTK from reaching any real desktop.
        bus = subprocess.run(["dbus-daemon", "--session", "--fork", "--print-address=1", "--print-pid=1",
                              "--nopidfile"], capture_output=True, text=True, env=self.env, check=True)
        address, pid = bus.stdout.split()[:2]
        self.bus_pid = int(pid)
        self.env["DBUS_SESSION_BUS_ADDRESS"] = address
        wm = subprocess.Popen(["xfwm4", "--compositor=off"], env=self.env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.procs.append(wm)
        time.sleep(1.0)
        if wm.poll() is not None:
            raise RuntimeError("xfwm4 did not start")
        return self

    def __exit__(self, *exc):
        for proc in reversed(self.procs):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        try:
            os.kill(self.bus_pid, 15)
        except OSError:
            pass

    def xdrive(self, *args) -> str:
        proc = subprocess.run([str(xdrive_bin()), *map(str, args)], env=self.env,
                              capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            raise AssertionError(f"xdrive {args}: {proc.stderr}")
        return proc.stdout

    def launch(self, argv):
        proc = subprocess.Popen(argv, env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.procs.append(proc)
        return App(self, proc)


class App:
    def __init__(self, session: XSession, proc):
        self.s = session
        self.proc = proc

    def windows(self):
        rows = []
        for line in self.s.xdrive("windows", self.proc.pid).splitlines():
            wid, frame, csd, title = line.split("\t", 3)
            rows.append({"id": wid, "frame": frame == "1", "csd": csd == "1", "title": title})
        return rows

    def wait_title(self, title: str, timeout=15.0) -> dict:
        """Wait until some window of the app has exactly this title; return it."""
        deadline = time.monotonic() + timeout
        seen = []
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise AssertionError(f"app exited {self.proc.returncode} waiting for {title!r}; "
                                     f"stderr: {self.proc.stderr.read().decode(errors='replace')[-2000:]}")
            seen = self.windows()
            for row in seen:
                if row["title"] == title:
                    return row
            time.sleep(0.1)
        raise AssertionError(f"no window titled {title!r}; saw {[r['title'] for r in seen]}")

    def focus(self, title: str) -> dict:
        row = self.wait_title(title)
        self.s.xdrive("activate", row["id"])
        time.sleep(0.4)
        return row

    def key(self, *combos):
        self.s.xdrive("key", *combos)
        time.sleep(0.15)

    def type(self, text: str):
        self.s.xdrive("type", text)
        time.sleep(0.15)

    def geometry(self, title: str) -> dict:
        """Client area and outer frame of the window with this title, in root coordinates."""
        row = self.wait_title(title)
        x, y, w, h, fx, fy, fw, fh = map(int, self.s.xdrive("geometry", row["id"]).split())
        return {"client": (x, y, w, h), "frame": (fx, fy, fw, fh)}

    def shot(self, title: str) -> "Shot":
        row = self.wait_title(title)
        proc = subprocess.run([str(xdrive_bin()), "shot", row["id"]], env=self.s.env,
                              capture_output=True, timeout=30)
        if proc.returncode != 0:
            raise AssertionError(f"xdrive shot: {proc.stderr.decode()}")
        return Shot(proc.stdout)

    def click(self, title: str, x: int, y: int, mods: str = ""):
        """Left click at client coordinates of the window with this title."""
        row = self.wait_title(title)
        self.s.xdrive("click", row["id"], x, y, *([mods] if mods else []))
        time.sleep(0.3)

    def close(self, title: str, timeout=15.0):
        row = self.wait_title(title)
        self.s.xdrive("close", row["id"])
        self.proc.wait(timeout)


class Shot:
    """An RGB image of a window's client area (from xdrive shot)."""

    def __init__(self, ppm: bytes):
        magic, size, maxval, data = ppm.split(b"\n", 3)
        assert magic == b"P6" and maxval == b"255", ppm[:20]
        self.w, self.h = map(int, size.split())
        self.data = data

    def pixel(self, x: int, y: int) -> tuple:
        i = 3 * (y * self.w + x)
        return tuple(self.data[i:i + 3])

    def find(self, color: tuple, tolerance=0) -> list:
        """All (x, y) whose pixel is within tolerance of color on every channel."""
        out = []
        for y in range(self.h):
            row = self.data[3 * y * self.w:3 * (y + 1) * self.w]
            for x in range(self.w):
                r, g, b = row[3 * x:3 * x + 3]
                if abs(r - color[0]) <= tolerance and abs(g - color[1]) <= tolerance and abs(b - color[2]) <= tolerance:
                    out.append((x, y))
        return out


def wait_for(predicate, timeout=10.0, what="condition"):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError(f"timed out waiting for {what}")


def title(name: str, modified=False) -> str:
    return f"{name}{' *' if modified else ''} {EM} Notes"
