"""U9 core: date formats, daily notes, templates, timestamp names, quick capture
(CONTRACT.md: U9). The clock is fixed with LCOS_NOTES_NOW."""
import datetime as dt
import json
import os
import random
import subprocess
from pathlib import Path

import pytest

from harness import build, tree_digest
from reference_u9 import TOKENS, capture_text, dailies as ref_dailies, daily_path as ref_daily_path
from reference_u9 import expand as ref_expand, fmt_time, supported
from test_u3_core import _vault

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-11-03T09:30:05"                                       # a Tuesday, day 307
WHEN = dt.datetime(2026, 11, 3, 9, 30, 5)


def run(*args, now=NOW):
    env = {k: v for k, v in os.environ.items() if k != "LCOS_NOTES_NOW"}
    if now is not None:
        env["LCOS_NOTES_NOW"] = now
    return subprocess.run([str(build() / "lcos-notes-cli"), *map(str, args)], capture_output=True,
                          timeout=60, env=env)


def j(*args, now=NOW):
    p = run(*args, now=now)
    assert p.returncode == 0, (args, p.returncode, p.stderr.decode())
    return json.loads(p.stdout.decode())


def refused(*args, now=NOW):
    p = run(*args, now=now)
    assert p.returncode == 2 and p.stderr.decode().startswith("refused: "), (args, p.returncode, p.stderr)
    return p


def _obsidian(v, name, data):
    (v / ".obsidian").mkdir(exist_ok=True)
    (v / ".obsidian" / name).write_bytes(data if isinstance(data, bytes) else data.encode())


# ---------------------------------------------------------------- the clock and formats

FORMATS = [                                                       # at 2026-11-03 09:30:05
    ("YYYY-MM-DD", "2026-11-03"),
    ("YY/M/D", "26/11/3"),
    ("MMMM MMM dddd ddd", "November Nov Tuesday Tue"),
    ("DDDD", "307"),
    ("DDDDD", "3073"),                                            # DDDD then D
    ("MMMMM", "November11"),                                      # MMMM then M
    ("HH:mm:ss H", "09:30:05 9"),
    ("[Week of] YYYY", "Week of 2026"),
    ("HH[h]mm", "09h30"),
    ("dddd, D MMMM", "Tuesday, 3 November"),
    ("YYYYMMDDHHmm", "202611030930"),
    ("é YYYY", "é 2026"),                                         # only ASCII letters are tokens
    ("[]YYYY[]", "2026"),
]
UNSUPPORTED = ["YYY", "Do", "T", "[unclosed YYYY", "YYYY-[W]ww", "h:mm a", "Q"]


@pytest.mark.parametrize("fmt,out", FORMATS)
def test_format_tokens_exact(tmp_path, fmt, out):
    v = _vault(tmp_path, {"T.md": "{{date:" + fmt + "}}"})
    assert j("template", v, "T.md", "x") == {"text": out}


@pytest.mark.parametrize("fmt", UNSUPPORTED)
def test_unsupported_format_is_left_as_written(tmp_path, fmt):
    v = _vault(tmp_path, {"T.md": "a {{date:" + fmt + "}} b"})
    assert j("template", v, "T.md", "x") == {"text": "a {{date:" + fmt + "}} b"}


@pytest.mark.parametrize("now,fmt,out", [
    ("2024-12-31T23:59:59", "DDDD dddd HH:mm:ss", "366 Tuesday 23:59:59"),
    ("2024-02-29T00:00:00", "dddd D MMM YY", "Thursday 29 Feb 24"),
    ("1900-03-01T07:05:09", "DDDD dddd H:mm:ss", "060 Thursday 7:05:09"),
    ("2099-12-31T12:00:00", "YYYY DDDD ddd", "2099 365 Thu"),
])
def test_format_edges(tmp_path, now, fmt, out):
    v = _vault(tmp_path, {"T.md": "{{date:" + fmt + "}}"})
    assert j("template", v, "T.md", "x", now=now) == {"text": out}


@pytest.mark.parametrize("bad", ["2026-11-03 09:30:05", "2026-13-01T00:00:00", "2026-02-29T00:00:00",
                                 "1899-12-31T23:59:59", "2100-01-01T00:00:00", "2026-11-03T24:00:00", "now"])
def test_invalid_clock_is_refused(tmp_path, bad):
    v = _vault(tmp_path, {"T.md": "x"})
    refused("template", v, "T.md", "x", now=bad)
    refused("daily", v, now=bad)
    refused("unique", v, now=bad)
    refused("capture", v, "hi", "--inbox", now=bad)
    assert not (v / "Inbox.md").exists()


def test_random_formats_match_reference(tmp_path):
    rng = random.Random(9001)
    pool = TOKENS + ["-", "/", " ", ".", "[at]", "é", "_", "[Q]", "q", "w"]
    for i in range(120):
        fmt = "".join(rng.choice(pool) for _ in range(rng.randint(1, 6)))
        y, doy = rng.randint(1900, 2099), rng.randint(0, 364)
        when = dt.datetime(y, 1, 1, rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59)) + dt.timedelta(days=doy)
        d = tmp_path / str(i)
        d.mkdir()
        v = _vault(d, {"T.md": "<{{date:" + fmt + "}}>"})
        want = "<" + (fmt_time(fmt, when) if supported(fmt) else "{{date:" + fmt + "}}") + ">"
        assert j("template", v, "T.md", "x", now=when.isoformat()) == {"text": want}, fmt


# ---------------------------------------------------------------- templates

VARIABLES = [
    ("{{title}}", "My Note"),
    ("{{ Title }}", "My Note"),
    ("{{TITLE:YYYY}}", "{{TITLE:YYYY}}"),                         # title takes no format
    ("{{date}} {{time}}", "2026-11-03 09:30"),
    ("{{date:dddd}} {{time:HH}}", "Tuesday 09"),
    ("{{ date :YYYY}}", "2026"),
    ("{{date: YYYY}}", " 2026"),                                  # the format is not trimmed
    ("{{date:}}", "2026-11-03"),                                  # empty format: dateFormat
    ("{{date:YYYY}}}", "2026}"),
    ("{{{title}}}", "{My Note}"),
    ("{{title}}{{title}}", "My NoteMy Note"),
    ("{{foo}} {{dates}} {{title", "{{foo}} {{dates}} {{title"),
    ("{{date:Q}}", "{{date:Q}}"),
    ("{{date:{{title}}}}", "{{date:{{title}}}}"),                 # no rescanning, format can't hold }
    ("{{\tdate\t}}", "2026-11-03"),
    ("{{date\n}}", "{{date\n}}"),
    ("a\r\n{{title}}\r\nb", "a\r\nMy Note\r\nb"),
]


@pytest.mark.parametrize("text,out", VARIABLES)
def test_template_variables_exact(tmp_path, text, out):
    v = _vault(tmp_path, {"T.md": text})
    assert j("template", v, "T.md", "My Note") == {"text": out}
    assert ref_expand(v, text, "My Note", WHEN) == out


def test_template_settings_formats(tmp_path):
    v = _vault(tmp_path, {"T.md": "{{date}}|{{time}}|{{date:YYYY}}"})
    _obsidian(v, "templates.json", json.dumps({"dateFormat": "DD.MM.YYYY", "timeFormat": "H[h]mm"}))
    assert j("template", v, "T.md", "x") == {"text": "03.11.2026|9h30|2026"}
    _obsidian(v, "templates.json", json.dumps({"dateFormat": "", "timeFormat": "h:mm a"}))
    assert j("template", v, "T.md", "x") == {"text": "2026-11-03|09:30|2026"}


def test_templates_list(tmp_path):
    v = _vault(tmp_path, {"Templates/B.md": "", "Templates/sub/C.md": "", "templates/A.md": "",
                          "Templates.md": "", "TemplatesX/D.md": "", "Tpl/E.md": "", "Templates/x.txt": ""})
    assert j("templates", v) == ["Templates/B.md", "Templates/sub/C.md", "templates/A.md"]
    _obsidian(v, "templates.json", '{"folder": " /Tpl/ "}')
    assert j("templates", v) == ["Tpl/E.md"]
    _obsidian(v, "templates.json", '{"folder": "/"}')                 # empty means Templates
    assert j("templates", v) == ["Templates/B.md", "Templates/sub/C.md", "templates/A.md"]


def test_template_refusals(tmp_path):
    v = _vault(tmp_path, {"Bad.md": b"\xff\n", "T.md": "x"})
    refused("template", v, "Bad.md", "t")
    refused("template", v, "Nope.md", "t")


def test_create_with_template(tmp_path):
    v = _vault(tmp_path, {"Templates/Meeting.md": "## {{title}}\r\nWhen: {{date}} {{time}}\r\n", "Old.md": "keep"})
    assert j("create", v, "Projects/Plan", "--template", "Templates/Meeting.md") == {"path": "Projects/Plan.md",
                                                                                   "created": True}
    assert (v / "Projects/Plan.md").read_bytes() == b"## Plan\r\nWhen: 2026-11-03 09:30\r\n"
    assert j("create", v, "old", "--template", "Templates/Meeting.md") == {"path": "Old.md", "created": False}
    assert (v / "Old.md").read_text() == "keep"
    before = tree_digest(v)
    refused("create", v, "New", "--template", "Templates/Missing.md")
    assert tree_digest(v) == before


# ---------------------------------------------------------------- daily notes

DAILY_SETTINGS = [
    (None, "2026-11-03.md"),
    ({"folder": "Journal"}, "Journal/2026-11-03.md"),
    ({"folder": " /Journal/Daily/ "}, "Journal/Daily/2026-11-03.md"),
    ({"format": "YYYY/MM/YYYY-MM-DD"}, "2026/11/2026-11-03.md"),
    ({"format": "dddd, MMMM D, YYYY"}, "Tuesday, November 3, 2026.md"),
    ({"format": "[Day] DDDD [of] YYYY"}, "Day 307 of 2026.md"),
    ({"format": "YYYY-MM-DD HH:mm"}, "2026-11-03.md"),            # time tokens: default
    ({"format": "YYYY-[W]ww"}, "2026-11-03.md"),                  # unsupported: default
    ({"format": ""}, "2026-11-03.md"),
    ({"format": 5, "folder": ["J"]}, "2026-11-03.md"),            # non-strings: defaults
    ('{"folder": "A", "folder": "B"}', "B/2026-11-03.md"),        # the last repeated key
    ('{"folder": "J"', "2026-11-03.md"),                          # not JSON
    ('["folder", "J"]', "2026-11-03.md"),                         # not an object
    (b'{"folder": "J\xff"}', "2026-11-03.md"),                    # not UTF-8
]


@pytest.mark.parametrize("settings,path", DAILY_SETTINGS)
def test_daily_path_from_settings(tmp_path, settings, path):
    v = _vault(tmp_path, {"Home.md": ""})
    if settings is not None:
        _obsidian(v, "daily-notes.json", settings if isinstance(settings, (str, bytes)) else json.dumps(settings))
    before = tree_digest(v)
    assert j("daily", v) == {"path": path, "date": "2026-11-03", "exists": False, "created": False}
    assert tree_digest(v) == before


def test_daily_settings_symlink_is_ignored(tmp_path):
    v = _vault(tmp_path, {"Home.md": ""})
    real = tmp_path / "real.json"
    real.write_text('{"folder": "J"}')
    (v / ".obsidian").mkdir()
    (v / ".obsidian" / "daily-notes.json").symlink_to(real)
    assert j("daily", v)["path"] == "2026-11-03.md"


@pytest.mark.parametrize("arg,date", [
    ("today", "2026-11-03"), ("yesterday", "2026-11-02"), ("tomorrow", "2026-11-04"), ("+30", "2026-12-03"),
    ("-307", "2025-12-31"), ("+00001", "2026-11-04"), ("2024-02-29", "2024-02-29"), ("1900-01-01", "1900-01-01"),
    ("2099-12-31", "2099-12-31"),
])
def test_daily_dates(tmp_path, arg, date):
    v = _vault(tmp_path, {"Home.md": ""})
    assert j("daily", v, arg) == {"path": date + ".md", "date": date, "exists": False, "created": False}


@pytest.mark.parametrize("arg", ["2026-02-30", "1899-12-31", "2100-01-01", "+100000", "+40000", "2026-1-5",
                                 "Today", "+", "now", "26-11-03"])
def test_daily_bad_dates_are_refused(tmp_path, arg):
    v = _vault(tmp_path, {"Home.md": ""})
    refused("daily", v, arg)
    refused("daily", v, arg, "--create")
    assert sorted(p.name for p in v.iterdir()) == ["Home.md"]


def test_daily_create_with_template(tmp_path):
    v = _vault(tmp_path, {"Templates/Day.md": "# {{title}}\n{{date:dddd}} {{time}} {{date}}\n"})
    _obsidian(v, "daily-notes.json", json.dumps({"folder": "Journal", "format": "YYYY/MM-DD",
                                                 "template": " Templates/Day.md "}))
    assert j("daily", v, "2026-11-05", "--create") == {"path": "Journal/2026/11-05.md", "date": "2026-11-05",
                                                       "exists": False, "created": True}
    assert (v / "Journal/2026/11-05.md").read_text() == "# 11-05\nThursday 09:30 2026-11-05\n"
    (v / "Journal/2026/11-05.md").write_text("mine")
    assert j("daily", v, "2026-11-05", "--create") == {"path": "Journal/2026/11-05.md", "date": "2026-11-05",
                                                       "exists": True, "created": False}
    assert (v / "Journal/2026/11-05.md").read_text() == "mine"


def test_daily_template_by_name_missing_and_invalid(tmp_path):
    v = _vault(tmp_path, {"T/Day.md": "{{title}}!", "Bad.md": b"\xfe"})
    _obsidian(v, "daily-notes.json", '{"template": "day"}')              # resolved like a link
    assert j("daily", v, "--create")["created"] is True
    assert (v / "2026-11-03.md").read_text() == "2026-11-03!"
    _obsidian(v, "daily-notes.json", '{"template": "Nowhere"}')          # unresolved: empty note
    j("daily", v, "tomorrow", "--create")
    assert (v / "2026-11-04.md").read_bytes() == b""
    _obsidian(v, "daily-notes.json", '{"template": "Bad"}')
    refused("daily", v, "+2", "--create")
    assert not (v / "2026-11-05.md").exists()


def test_daily_existing_note_matches_after_case_folding(tmp_path):
    v = _vault(tmp_path, {"journal/2026-11-03.md": "x", "Archive/2026-11-03.md": "y"})
    _obsidian(v, "daily-notes.json", '{"folder": "Journal"}')
    before = tree_digest(v)
    assert j("daily", v, "--create") == {"path": "journal/2026-11-03.md", "date": "2026-11-03", "exists": True,
                                         "created": False}
    assert tree_digest(v) == before


def test_daily_create_refused_by_creation_rules(tmp_path):
    v = _vault(tmp_path, {"Home.md": ""})
    _obsidian(v, "daily-notes.json", '{"format": "YYYY[:]MM"}')
    before = tree_digest(v)
    refused("daily", v, "--create")
    _obsidian(v, "daily-notes.json", '{"folder": ".hidden"}')
    refused("daily", v, "--create")
    assert {k: d for k, d in tree_digest(v).items() if not k.startswith(".obsidian")} == \
        {k: d for k, d in before.items() if not k.startswith(".obsidian")}


def test_dailies_exact(tmp_path):
    v = _vault(tmp_path, {"2026-11-03.md": "", "2026-11-01.md": "", "Archive/2026-11-02.md": "", "2026-1-1.md": "",
                          "2026-02-30.md": "", "1899-12-31.md": "", "2100-01-01.md": "", "Notes.md": "",
                          "2026-11-04.MD": "", "1900-01-01.md": ""})
    assert j("dailies", v) == [{"path": "1900-01-01.md", "date": "1900-01-01"},
                               {"path": "2026-11-01.md", "date": "2026-11-01"},
                               {"path": "2026-11-03.md", "date": "2026-11-03"}]
    _obsidian(v, "daily-notes.json", '{"folder": "archive"}')
    assert j("dailies", v) == [{"path": "Archive/2026-11-02.md", "date": "2026-11-02"}]


def test_dailies_skip_ambiguous_names(tmp_path):
    v = _vault(tmp_path, {"2026111.md": "", "20261231.md": "", "2026115.md": "", "202612.md": ""})
    _obsidian(v, "daily-notes.json", '{"format": "YYYYMD"}')
    assert j("dailies", v) == [{"path": "202612.md", "date": "2026-01-02"},     # only 2026-1-2 fits
                               {"path": "20261231.md", "date": "2026-12-31"}]
    _obsidian(v, "daily-notes.json", '{"format": "YY-MM-DD"}')        # 19xx and 20xx: never unique
    (v / "26-11-03.md").write_text("")
    assert j("dailies", v) == []
    _obsidian(v, "daily-notes.json", '{"format": "MMMM"}')
    (v / "November.md").write_text("")
    assert j("dailies", v) == []


def test_random_daily_vaults_match_reference(tmp_path):
    rng = random.Random(9002)
    parts = ["YYYY", "MM", "M", "DD", "D", "MMMM", "MMM", "DDDD", "dddd", "ddd", "-", "/", " ", "[x]", "."]
    for i in range(12):
        fmt = rng.choice(["YYYY-MM-DD", "YYYY/MM/DD", "DD.MM.YYYY", "YYYY-DDDD", "dddd D MMMM YYYY",
                          "".join(rng.choice(parts) for _ in range(rng.randint(2, 6)))])
        folder = rng.choice(["", "Daily", "a/b"])
        d = tmp_path / str(i)
        d.mkdir()
        v = _vault(d, {"Other.md": ""})
        _obsidian(v, "daily-notes.json", json.dumps({"folder": folder, "format": fmt}))
        for _ in range(8):
            date = dt.date(1900, 1, 1) + dt.timedelta(days=rng.randint(0, 73048))
            p = ref_daily_path(v, date)
            name = p if rng.random() < 0.8 else p.upper()[:-3] + ".md"
            if all(seg and not seg.startswith(".") for seg in name.split("/")):
                (v / name).parent.mkdir(parents=True, exist_ok=True)
                (v / name).write_text("")
        assert j("dailies", v) == ref_dailies(v), fmt
        date = dt.date(1900, 1, 1) + dt.timedelta(days=rng.randint(0, 73048))
        assert j("daily", v, date.isoformat())["date"] == date.isoformat()


# ---------------------------------------------------------------- timestamp names

def test_unique_targets(tmp_path):
    v = _vault(tmp_path, {"Home.md": ""})
    assert j("unique", v) == {"target": "202611030930"}
    (v / "202611030930.md").write_text("")
    (v / "202611030930-1.md").write_text("")
    assert j("unique", v) == {"target": "202611030930-2"}
    _obsidian(v, "zk-prefixer.json", '{"folder": "Zettel/", "format": "YYYYMMDDHHmmss"}')
    assert j("unique", v) == {"target": "Zettel/20261103093005"}
    _obsidian(v, "zk-prefixer.json", '{"format": "Do"}')
    assert j("unique", v) == {"target": "202611030930-2"}
    _obsidian(v, "zk-prefixer.json", '{"format": "HH:mm"}')
    refused("unique", v)
    assert sorted(p.name for p in v.iterdir() if p.name != ".obsidian") == \
        ["202611030930-1.md", "202611030930.md", "Home.md"]


# ---------------------------------------------------------------- quick capture

CAPTURES = [
    ("", "hello", "- 09:30 hello\n", 1),
    ("a", "hello", "a\n- 09:30 hello\n", 2),
    ("a\n", "hello", "a\n- 09:30 hello\n", 2),
    ("a\r\nb", "hello", "a\r\nb\r\n- 09:30 hello\r\n", 3),
    ("a\r\n\r\n", "x\ny", "a\r\n\r\n- 09:30 x\r\n  y\r\n", 3),
    ("a\nb\r\n", "hello", "a\nb\r\n- 09:30 hello\n", 3),                # the first line ending decides
    ("x\n", "  one\n\n two  \n", "x\n- 09:30 one\n\n   two\n", 2),
    ("", "x\r\ny\rz", "- 09:30 x\n  yz\n", 1),
    ("", "\t- [ ] task", "- 09:30 - [ ] task\n", 1),
]


@pytest.mark.parametrize("before,text,after,line", CAPTURES)
def test_capture_bytes(tmp_path, before, text, after, line):
    v = _vault(tmp_path, {"Inbox.md": before})
    assert j("capture", v, text, "--inbox") == {"path": "Inbox.md", "line": line, "created": False}
    assert (v / "Inbox.md").read_bytes() == after.encode()
    assert capture_text(before, text, WHEN) == (after, line)


def test_capture_targets(tmp_path):
    v = _vault(tmp_path, {"Templates/Day.md": "# {{title}}\n", "inbox.md": "i"})
    _obsidian(v, "daily-notes.json", '{"folder": "Daily", "template": "Templates/Day"}')
    assert j("capture", v, "first") == {"path": "Daily/2026-11-03.md", "line": 2, "created": True}
    assert j("capture", v, "second") == {"path": "Daily/2026-11-03.md", "line": 3, "created": False}
    assert (v / "Daily/2026-11-03.md").read_text() == "# 2026-11-03\n- 09:30 first\n- 09:30 second\n"
    assert j("capture", v, "in", "--inbox") == {"path": "inbox.md", "line": 2, "created": False}
    assert (v / "inbox.md").read_text() == "i\n- 09:30 in\n"


def test_capture_creates_inbox_and_refuses(tmp_path):
    v = _vault(tmp_path, {"Home.md": "", "Bad.md": b"\xff"})
    assert j("capture", v, "x", "--inbox") == {"path": "Inbox.md", "line": 1, "created": True}
    before = tree_digest(v)
    refused("capture", v, " \n\t ", "--inbox")
    refused("capture", v, "", "--inbox")
    (v / "Inbox.md").write_bytes(b"\xff\n")
    before = tree_digest(v)
    refused("capture", v, "x", "--inbox")
    assert tree_digest(v) == before


def test_u9_commands_never_write_settings(tmp_path):
    v = _vault(tmp_path, {"Templates/T.md": "{{title}}"})
    _obsidian(v, "daily-notes.json", '{"folder": "D"}')
    _obsidian(v, "templates.json", '{}')
    _obsidian(v, "zk-prefixer.json", '{}')
    before = {k: d for k, d in tree_digest(v).items()}
    j("daily", v, "--create")
    j("capture", v, "x")
    j("create", v, "N", "--template", "Templates/T.md")
    j("unique", v)
    j("templates", v)
    after = tree_digest(v)
    assert {k: d for k, d in after.items() if k.startswith(".obsidian")} == \
        {k: d for k, d in before.items() if k.startswith(".obsidian")}
    assert set(after) - set(before) == {"D", "D/2026-11-03.md", "N.md"}


# ---------------------------------------------------------------- documentation

def test_user_docs_cover_u9():
    readme = (ROOT / "README.md").read_text()
    assert "Version 1.1.0." in readme
    assert readme.find("sudo apt update\n") < readme.find("sudo apt install ./lcos-notes_1.1.0_amd64.deb")
    guide = (ROOT / "DOCUMENTATION.md").read_text()
    assert "This guide covers version 1.1.0." in guide
    for term in ("daily-notes.json", "Ctrl+D", "Alt+Left", "dailies", "templates.json", "{{title}}",
                 "{{date:", "Insert Template", "Timestamp Name", "zk-prefixer.json", "--capture", "Inbox",
                 "keyboard", "LCOS_NOTES_NOW", "lcos-notes-cli capture"):
        assert term.lower() in guide.lower(), term
    man = (ROOT / "data/lcos-notes.1").read_text() + (ROOT / "data/lcos-notes-cli.1").read_text()
    for term in ("--capture", "daily", "dailies", "templates", "template", "unique", "capture"):
        assert term in man, term
