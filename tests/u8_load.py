"""U8: the reference renderer expands embeds, so it reads embedded notes from the vault."""
from harness import cli_json
from reference_links import markdown_links
from reference_render import loader


def LOAD(vault):
    return loader(vault, cli_json, markdown_links)
