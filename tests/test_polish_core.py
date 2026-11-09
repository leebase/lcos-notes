"""D534 outcome cases: literal expectations, not renderer-derived claims."""
import pytest
from harness import cli_json
from test_u3_core import _vault
from reference_render import render as reference
from reference_links import markdown_links


CASES = [
    ("==a **b** c==", "a b c", [(0,5)], [(2,3,"strong")]),
    ("==a *b* c==", "a b c", [(0,5)], [(2,3,"em")]),
    ("==a `b` c==", "a b c", [(0,5)], [(2,3,"code")]),
    ("==a ~~b~~ c==", "a b c", [(0,5)], [(2,3,"strike")]),
    ("==**bold**==", "bold", [(0,4)], [(0,4,"strong")]),
    ("**==bold==**", "bold", [(0,4)], [(0,4,"strong")]),
    ("==é **猫** Ω==", "é 猫 Ω", [(0,5)], [(2,3,"strong")]),
    ("==a *b **c** d* e==", "a b c d e", [(0,9)], [(2,7,"em"),(4,5,"strong")]),
    ("==a **b**== x ==c `d`==", "a b x c d", [(0,3),(6,9)], [(2,3,"strong"),(8,9,"code")]),
    ("`==no==`", "==no==", [], [(0,6,"code")]),
    ("==a `==literal==` b==", "a ==literal== b", [(0,15)], [(2,13,"code")]),
    ("==a\nb==", "==a b==", [], []),
    ("==a  \nb==", "==a\nb==", [], []),
    ("==a\n\nb==", "==a\n\nb==", [], []),
    ("== a **b**==", "== a b==", [], [(5,6,"strong")]),
    ("==a **b** ==", "==a b ==", [], [(4,5,"strong")]),
    ("=**=a**==", "==a==", [], [(1,3,"strong")]),
    ("==a <i>b</i> c==", "==a <i>b</i> c==", [], []),
    ("```\n==a **b**==\n```", "==a **b**==", [], [(0,11,"codeblock")]),
    ("# ==a **b**==", "a b", [(0,3)], [(0,3,"h1"),(2,3,"strong")]),
    ("> [!tip] ==a **b**==\n> body", "a b\nbody", [(0,3)], [(0,3,"callout-title"),(2,3,"strong")]),
    ("- ==a **b**==", "• a b", [(2,5)], [(4,5,"strong")]),
]


@pytest.mark.parametrize("source,text,highlight,styles", CASES)
def test_formatted_highlight_exact(tmp_path,source,text,highlight,styles):
    v=_vault(tmp_path,{"H.md":source})
    got=cli_json("render",v,"H.md")
    assert got["text"]==text
    assert [(s["start"],s["end"]) for s in got["spans"] if s["style"]=="highlight"]==highlight
    spans={(s["start"],s["end"],s["style"]) for s in got["spans"]}
    assert set(styles)<=spans
    assert cli_json("highlights",v,"H.md")==[{"start":a,"end":b,"text":text[a:b]} for a,b in highlight]
    # Literal outcomes above also constrain the independently updated reference.
    assert reference(source,[],"H.md")["text"]==text
    assert [(s["start"],s["end"]) for s in reference(source,[],"H.md")["spans"] if s["style"]=="highlight"]==highlight


def test_highlighted_links_preserve_destination_and_offsets(tmp_path):
    source="==a **[[Target|go]]** c=="
    v=_vault(tmp_path,{"H.md":source,"Target.md":"target"})
    r=cli_json("render",v,"H.md")
    assert r["text"]=="a go c"
    assert [(s["start"],s["end"]) for s in r["spans"] if s["style"]=="highlight"]==[(0,6)]
    assert len(r["links"])==1 and r["links"][0]["resolved"]=="Target.md"
    assert (r["links"][0]["start"],r["links"][0]["end"])==(2,4)


def test_opaque_link_display_does_not_manufacture_highlights(tmp_path):
    v=_vault(tmp_path,{"H.md":"[[Target|==alias==]]","Target.md":"target"})
    r=cli_json("render",v,"H.md")
    assert r["text"]=="==alias=="
    assert not any(s["style"]=="highlight" for s in r["spans"])


def test_embedded_formatted_highlight_has_host_offsets(tmp_path):
    v=_vault(tmp_path,{"H.md":"before\n\n![[E]]\n\nafter","E.md":"==a **b** c=="})
    r=cli_json("render",v,"H.md")
    assert r["text"]=="before\n\na b c\n\nafter"
    assert cli_json("highlights",v,"H.md")==[{"start":8,"end":13,"text":"a b c"}]
