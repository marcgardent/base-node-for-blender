"""The toon module: Blender 5.3's lighting nodes, EEVEE only."""

from __future__ import annotations

from pathlib import Path

from base_node_blender import format_source, infer, parse
from base_node_blender.targets import check_targets

TOON = Path(__file__).resolve().parents[2] / "stdlib" / "toon.bn"


def test_toon_fits_blender_53_eevee_alone():
    text = TOON.read_text(encoding="utf-8")
    ast = parse(text, TOON.name)
    assert [g.name for g in ast.graphs] == [
        "light setting", "light threshold", "light band", "light colour", "toon"]
    assert check_targets(ast, ["blender@5.3 eevee"]) == []
    # The lighting nodes are not in Blender 5.2 LTS, and Cycles does not run them
    outside = infer(ast).outside
    assert "blender@5.2-lts" in " ".join(map(str, outside["blender"]))
    assert outside["blender cycles"]


def test_toon_is_formatted():
    text = TOON.read_text(encoding="utf-8")
    assert format_source(text) == text
