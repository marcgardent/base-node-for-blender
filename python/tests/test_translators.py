"""Translators and bridges: a target of another destination, added to this library's, that a text of
`blender` reaches through its translator and its bridge (spec/targets.md, A target of another
destination). The target is a fixture of the tests, conformance/targets/pixels.json, not shipped. The
same cases as rust/tests/translators.rs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from base_node.printer import to_source
from base_node_blender import (check_target, check_targets, header, infer, load_target, parse, promise_names,
                               target_names, translate)
from base_node_blender import targets
from base_node_blender.targets import _bridge, accepted, catalog, translation_issues

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "conformance" / "targets"


@pytest.fixture(autouse=True)
def pixels(monkeypatch):
    """The target `pixels` known to this library for one test, and forgotten after it."""
    monkeypatch.setattr(targets, "_added", [])
    targets.add_targets(FIXTURE)


def test_an_added_target_is_a_target_of_its_own():
    assert "pixels" in target_names() and "pixels" in promise_names()
    assert accepted("pixels", "node") == set(load_target("pixels").nodes)
    for name in ("pixels@1.0", "pixels gltf"):
        with pytest.raises(ValueError, match="unknown target"):
            load_target(name)


def test_what_it_translates_from_is_the_compositor_s():
    compositor = {n["name"] for n in catalog(ROOT)["kinds"]["compositor"]}
    assert set(load_target("pixels").translators["blender"]["nodes"]) <= compositor


def test_the_translator_leads_to_nodes_of_the_target():
    t = load_target("pixels")
    for source, tr in t.translators.items():
        assert source in target_names()
        for dst in tr.get("nodes", {}).values():
            node = dst if isinstance(dst, str) else dst["node"]
            if "::" in node:
                assert _bridge(t, node) is not None, f"{node} is not a graph of its bridges"
            else:
                assert node in t.nodes, f"{node} is not one of its nodes"
        assert set(tr.get("kinds", {}).values()) <= set(t.kinds)


ONE_TARGET_PER_GRAPH = """// @target blender gltf, pixels

shader graph tint(c: Color) -> Shader {
  return Emission(color: c)
}

pixel graph soft(image: Color) -> Color {
  return Blur(image, radius: 2.0)
}
"""


def test_a_text_may_promise_one_target_per_graph():
    f = parse(ONE_TARGET_PER_GRAPH)
    assert infer(f).fits == {}  # neither target takes every graph
    assert check_targets(f, ["blender gltf", "pixels"]) == []
    assert check_targets(f, ["blender gltf"]) != [] != check_targets(f, ["pixels"])
    assert header(ONE_TARGET_PER_GRAPH).target == ["blender gltf", "pixels"]


COMPOSITE = """compositor graph soften(image: Color, size: Float = 4.0) -> Color {
  blurred = Blur(image, size: size)
  return Mix(factor: 0.5, a: image, b: blurred)
}
"""


def test_a_text_reaches_the_target_through_its_translator():
    f = parse(COMPOSITE)
    fits = infer(f).fits
    assert fits["blender"] is None
    assert fits["pixels"] == "blender"
    out = translate(f, "blender", "pixels")
    assert out.graphs[0].kind == "pixel"
    assert "pixel graph soften" in to_source(out)
    assert f.graphs[0].kind == "compositor"  # the text itself is left as it was


def test_a_node_the_translator_does_not_list_stays_out():
    f = parse(COMPOSITE.replace("Blur(image, size: size)", "Pixelate(image)"))
    assert "pixels" in infer(f).outside
    with pytest.raises(ValueError, match="Pixelate"):
        translate(f, "blender", "pixels")


PAINT = """compositor graph paint(image: Color) -> Color {
  soft = Kuwahara(image, size: 8.0)
  return Mix(factor: 0.5, a: image, b: Kuwahara(soft))
}
"""

PAINTED = """use interop

pixel graph paint(image: Color) -> Color {
  soft = interop::kuwahara(image, size: 8.0)
  return Mix(factor: 0.5, a: image, b: interop::kuwahara(soft))
}
"""


def test_a_bridge_carries_a_node_the_target_has_not():
    f = parse(PAINT)
    assert infer(f).fits["pixels"] == "blender"
    text = to_source(translate(f, "blender", "pixels"))
    assert text == PAINTED  # the call is the bridge's, the text uses its module once
    assert check_target(parse(text), "pixels") == []
    assert infer(parse(text)).fits == {"pixels": None}


def test_the_bridge_module_fits_its_target():
    assert load_target("pixels").bridges == ["pixels/interop.bn"]
    path = FIXTURE / "pixels" / "interop.bn"
    assert check_target(parse(path.read_text(encoding="utf-8")), "pixels") == []


def test_a_bridge_graph_outside_its_target_is_refused(tmp_path):
    pixels = json.loads((FIXTURE / "pixels.json").read_text(encoding="utf-8"))
    pixels["nodes"].remove("Median")
    pixels["bridges"] = [str(FIXTURE / "pixels" / "interop.bn")]
    path = tmp_path / "narrow.json"
    path.write_text(json.dumps(pixels), encoding="utf-8")
    issues = translation_issues(parse(PAINT), "blender", str(path))
    assert [(i.what, i.name, i.line) for i in issues] == [
        ("graph", "interop::kuwahara (node Median)", 2),
        ("graph", "interop::kuwahara (node Median)", 3)]


def test_what_inference_holds():
    inf = infer(parse(COMPOSITE))
    assert list(inf.fits.items()) == [("blender", None), ("pixels", "blender")]
    assert inf.graphs == [("soften", ["blender"])]
    assert inf.lines() == ["Compatible: blender, pixels (translated from blender)"]


def test_a_translator_renames_a_node():
    f = parse("compositor graph g(image: Color) -> Color {\n  return RGBCurves(image)\n}\n")
    assert translate(f, "blender", "pixels").graphs[0].body[0].value.name == "Curves"


def test_a_translator_renames_inputs_and_settings():
    f = parse(
        "compositor graph g(image: Color) -> Color {\n"
        "  blurred = Blur(image, size: 4.0)\n"
        "  mixed = MixLegacy[MULTIPLY](color1: image, color2: blurred)\n"
        "  return ColorRamp[color_ramp: Ramp((0.0, (0.0, 0.0, 0.0, 1.0)), (1.0, (1.0, 1.0, 1.0, 1.0)))](factor: mixed)\n"
        "}\n"
    )
    text = to_source(translate(f, "blender", "pixels"))
    assert "Blur(image, radius: 4.0)" in text
    # A setting by position stays as it is written, one by name takes its new name
    assert "Mix[MULTIPLY](a: image, b: blurred)" in text
    assert "ColorRamp[ramp: Ramp((0.0, (0.0, 0.0, 0.0, 1.0)), (1.0, (1.0, 1.0, 1.0, 1.0)))](" in text
    assert "image: mixed)" in text


def test_a_target_there_is_already_is_not_added_again(tmp_path):
    (tmp_path / "pixels.json").write_text((FIXTURE / "pixels.json").read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="'pixels'"):
        targets.add_targets(tmp_path)
    (tmp_path / "pixels.json").rename(tmp_path / "blender.json")
    with pytest.raises(ValueError, match="'blender'"):
        targets.add_targets(tmp_path)
