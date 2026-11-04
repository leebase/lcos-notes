"""Reference implementation of CONTRACT.md U9 (daily notes, templates, timestamp names,
quick capture) for the core tests. Pure Python, no app code. Vaults are directories."""
import datetime as dt
import json
import re
import unicodedata  # noqa: F401  (kept for parity with other references)
from pathlib import Path

FIRST, LAST = dt.date(1900, 1, 1), dt.date(2099, 12, 31)
TOKENS = ["YYYY", "YY", "MMMM", "MMM", "MM", "M", "DDDD", "DD", "D", "dddd", "ddd", "HH", "H", "mm", "ss"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
TIME_TOKENS = {"HH", "H", "mm", "ss"}


def fold(s):
    """Unicode case folding as g_utf8_casefold does for our purposes."""
    return s.casefold()


# ---------------------------------------------------------------- formats

def tokenize(fmt):
    """List of ('tok', name) / ('lit', text), or None when unsupported."""
    out, i = [], 0
    while i < len(fmt):
        c = fmt[i]
        if c == "[":
            j = fmt.find("]", i + 1)
            if j < 0:
                return None
            out.append(("lit", fmt[i + 1:j]))
            i = j + 1
            continue
        for t in TOKENS:
            if fmt.startswith(t, i):
                out.append(("tok", t))
                i += len(t)
                break
        else:
            if c.isascii() and c.isalpha():
                return None
            out.append(("lit", c))
            i += 1
    return out


def supported(fmt):
    return tokenize(fmt) is not None


def fmt_time(fmt, when):
    """when: datetime. fmt must be supported."""
    parts = []
    for kind, v in tokenize(fmt):
        if kind == "lit":
            parts.append(v)
            continue
        y, mo, d = when.year, when.month, when.day
        parts.append({
            "YYYY": f"{y:04d}", "YY": f"{y % 100:02d}", "MMMM": MONTHS[mo - 1], "MMM": MONTHS[mo - 1][:3],
            "MM": f"{mo:02d}", "M": str(mo), "DDDD": f"{when.timetuple().tm_yday:03d}", "DD": f"{d:02d}",
            "D": str(d), "dddd": DAYS[(when.weekday() + 1) % 7], "ddd": DAYS[(when.weekday() + 1) % 7][:3],
            "HH": f"{when.hour:02d}", "H": str(when.hour), "mm": f"{when.minute:02d}", "ss": f"{when.second:02d}",
        }[v])
    return "".join(parts)


# ---------------------------------------------------------------- settings

def settings(vault, name):
    """String-valued keys of .obsidian/NAME, or {} when the file is unusable."""
    p = Path(vault) / ".obsidian" / name
    if p.is_symlink() or not p.is_file():
        return {}
    try:
        obj = json.loads(p.read_bytes().decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}
    if not isinstance(obj, dict):
        return {}
    return {k: v for k, v in obj.items() if isinstance(v, str)}


def folder_value(v):
    return v.strip(" /")


def notes(vault):
    """Vault notes (U1): .md files, hidden entries and symlinks skipped, sorted byte order."""
    root = Path(vault)
    out = []

    def walk(d, rel):
        for e in d.iterdir():
            if e.name.startswith(".") or e.is_symlink():
                continue
            r = f"{rel}/{e.name}" if rel else e.name
            if e.is_dir():
                walk(e, r)
            elif e.is_file() and e.name.endswith(".md"):
                out.append(r)
    walk(root, "")
    return sorted(out, key=lambda s: s.encode())


def find_exact(vault, path):
    """The first note (byte order) whose path equals PATH after case folding."""
    f = fold(path)
    for n in notes(vault):
        if fold(n) == f:
            return n
    return None


BAD = set('*"\\<>:|?#^')


def creation_refusal(target):
    """U1 creation rules on a target without .md; None when allowed."""
    if target == "" or target.startswith("/"):
        return "invalid"
    for seg in target.split("/"):
        if seg in ("", ".", "..") or seg.startswith("."):
            return "invalid"
    if any(c in BAD or ord(c) < 32 or ord(c) == 127 for c in target):
        return "invalid"
    return None


# ---------------------------------------------------------------- daily notes

def daily_settings(vault):
    s = settings(vault, "daily-notes.json")
    fmt = s.get("format", "")
    toks = tokenize(fmt) if fmt else None
    if not fmt or toks is None or any(k == "tok" and v in TIME_TOKENS for k, v in toks):
        fmt = "YYYY-MM-DD"
    return folder_value(s.get("folder", "")), fmt, s.get("template", "").strip(" ")


def daily_path(vault, date):
    folder, fmt, _ = daily_settings(vault)
    name = fmt_time(fmt, dt.datetime(date.year, date.month, date.day))
    return (folder + "/" if folder else "") + name + ".md"


def dailies(vault):
    folder, fmt, _ = daily_settings(vault)
    by_path = {}
    d = FIRST
    one = dt.timedelta(days=1)
    while d <= LAST:
        p = (folder + "/" if folder else "") + fmt_time(fmt, dt.datetime(d.year, d.month, d.day)) + ".md"
        by_path.setdefault(fold(p), []).append(d)
        d += one
    out = []
    for n in notes(vault):
        ds = by_path.get(fold(n), [])
        if len(ds) == 1:
            out.append({"path": n, "date": ds[0].isoformat()})
    return sorted(out, key=lambda e: (e["date"], e["path"].encode()))


def parse_date(arg, now):
    today = now.date()
    if arg in (None, "today"):
        d = today
    elif arg == "yesterday":
        d = today - dt.timedelta(days=1)
    elif arg == "tomorrow":
        d = today + dt.timedelta(days=1)
    elif re.fullmatch(r"[+-][0-9]{1,5}", arg):
        try:
            d = today + dt.timedelta(days=int(arg))
        except OverflowError:
            return None
    elif re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", arg):
        try:
            d = dt.date.fromisoformat(arg)
        except ValueError:
            return None
    else:
        return None
    return d if FIRST <= d <= LAST else None


# ---------------------------------------------------------------- templates

TEMPLATE_RE = re.compile(r"\{\{[ \t]*(title|date|time)[ \t]*(?::([^}\r\n]*))?\}\}", re.I | re.A)


def template_settings(vault):
    s = settings(vault, "templates.json")
    folder = folder_value(s.get("folder", "")) or "Templates"
    df = s.get("dateFormat", "")
    tf = s.get("timeFormat", "")
    df = df if df and supported(df) else "YYYY-MM-DD"
    tf = tf if tf and supported(tf) else "HH:mm"
    return folder, df, tf


def templates(vault):
    folder, _, _ = template_settings(vault)
    pre = fold(folder + "/")
    return [n for n in notes(vault) if fold(n).startswith(pre)]


def expand(vault, text, title, when):
    _, df, tf = template_settings(vault)

    def sub(m):
        name, f = m.group(1).lower(), m.group(2)
        if name == "title":
            return title if f is None else m.group(0)
        if not f:
            return fmt_time(df if name == "date" else tf, when)
        return fmt_time(f, when) if supported(f) else m.group(0)
    return TEMPLATE_RE.sub(sub, text)


# ---------------------------------------------------------------- timestamp names

def unique_target(vault, now):
    s = settings(vault, "zk-prefixer.json")
    folder = folder_value(s.get("folder", ""))
    fmt = s.get("format", "")
    fmt = fmt if fmt and supported(fmt) else "YYYYMMDDHHmm"
    base = (folder + "/" if folder else "") + fmt_time(fmt, now)
    t, n = base, 0
    while find_exact(vault, t + ".md"):
        n += 1
        t = f"{base}-{n}"
    return t


# ---------------------------------------------------------------- capture

def capture_text(c, x, when):
    """New text and the block's first line number, or None when nothing to capture."""
    x = x.replace("\r\n", "\n").replace("\r", "").strip(" \t\n")
    if not x:
        return None
    i = c.find("\n")
    e = "\r\n" if i > 0 and c[i - 1] == "\r" else "\n"
    lines = x.split("\n")
    block = f"- {when.hour:02d}:{when.minute:02d} {lines[0]}{e}" + "".join(
        ("  " + ln if ln else "") + e for ln in lines[1:])
    prefix = c + (e if c and not c.endswith("\n") else "")
    return prefix + block, prefix.count("\n") + 1
