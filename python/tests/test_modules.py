"""Modules: `use maths (fbm) from "//lib/maths.bn"`, and the groups already in the file."""

from pathlib import Path

import pytest

from base_node_blender import BnError, compile_source, parse
from base_node.format import format_source
from base_node.printer import to_source
from base_node_blender.schema import GroupSpec

MATHS = """\
geometry graph double(x: Float) -> Float {
  return x * 2.0
}

geometry graph quadruple(x: Float) -> Float {
  return double(double(x))
}

geometry graph moitié(x: Float) -> Float {
  return x / 2.0
}
"""

MAIN = """\
use maths

geometry graph g(geometry: Geometry) -> Geometry {
  return SetPosition(geometry, offset: CombineXYZ(z: quadruple(1.0)))
}
"""


def loader(modules):
    """A load(name, source) over {(name, source): text}, recording what it was asked."""
    asked = []

    def load(name, source):
        asked.append((name, source))
        if (name, source) not in modules:
            raise LookupError(f"no text '{name}.bn'")
        return modules[(name, source)], source or f"{name}.bn"
    load.asked = asked
    return load


def errors(source, schema, load=None):
    with pytest.raises(BnError) as err:
        compile_source(source, schema, "t.bn", load)
    return [d.message for d in err.value.diagnostics]


def test_uses_print_back_sorted_at_the_head():
    src = ('use b from "//lib/b.bn"\nuse a (f, g)\n\n'
           "geometry graph g() -> Float {\n  return 1.0\n}\n")
    assert to_source(parse(src)) == ('use a (f, g)\nuse b from "//lib/b.bn"\n\n'
                                     "geometry graph g() -> Float {\n  return 1.0\n}\n")


def test_format_sorts_the_uses_and_keeps_their_comments():
    src = ("// Les fonctions\nuse maths\nuse bruits  // le fbm\n"
           "geometry graph g() -> Float {\n  return 1.0\n}\n")
    assert format_source(src) == ("// Les fonctions\nuse bruits  // le fbm\nuse maths\n\n"
                                  "geometry graph g() -> Float {\n  return 1.0\n}\n")


def test_a_long_list_takes_one_name_per_line():
    names = [f"fonction_numéro_{i}" for i in range(6)]
    src = "use maths (\n" + "".join(f"  {n},\n" for n in names) + ')\n\ngeometry graph g() -> Float {\n  return 1.0\n}\n'
    assert to_source(parse(src)) == src


def test_use_is_a_name_like_any_other_outside_the_head(schema):
    src = "geometry graph g(use: Float) -> Float {\n  from = use * 2.0\n  return from\n}\n"
    assert to_source(parse(src)) == src
    compile_source(src, schema)


def test_a_use_after_a_graph_fails():
    with pytest.raises(BnError, match="at the top of the file"):
        parse("geometry graph g() -> Float {\n  return 1.0\n}\nuse maths\n")


def test_the_module_comes_first_marked_with_its_name(schema):
    load = loader({("maths", None): MATHS})
    graphs = compile_source(MAIN, schema, "t.bn", load)
    assert [(g.name, g.module) for g in graphs] == [
        ("double", ("maths", None)), ("quadruple", ("maths", None)), ("moitié", ("maths", None)), ("g", None)]
    assert load.asked == [("maths", None)]


def test_a_list_brings_those_graphs_and_what_they_call(schema):
    src = MAIN.replace("use maths", "use maths (quadruple)")
    graphs = compile_source(src, schema, "t.bn", loader({("maths", None): MATHS}))
    assert [g.name for g in graphs] == ["double", "quadruple", "g"]


def test_a_graph_left_out_of_the_list_is_unknown(schema):
    src = MAIN.replace("use maths", "use maths (moitié)")
    assert any("quadruple" in m and "unknown" in m for m in errors(src, schema, loader({("maths", None): MATHS})))


def test_the_source_reaches_the_loader(schema):
    src = MAIN.replace("use maths", 'use maths from "//lib/maths.bn"')
    load = loader({("maths", "//lib/maths.bn"): MATHS})
    graphs = compile_source(src, schema, "t.bn", load)
    assert graphs[0].module == ("maths", "//lib/maths.bn")


def test_a_missing_module_points_at_its_use(schema):
    with pytest.raises(BnError) as err:
        compile_source(MAIN, schema, "t.bn", loader({}))
    (d,) = err.value.diagnostics
    assert (d.line, d.col) == (1, 1) and d.message == "module 'maths': no text 'maths.bn'"


def test_without_a_loader_use_fails(schema):
    assert errors(MAIN, schema) == ["use: no module loader configured"]


def test_an_error_in_the_module_is_reported_at_the_use(schema):
    broken = MATHS.replace("x * 2.0", "y * 2.0")
    (message,) = errors(MAIN, schema, loader({("maths", None): broken}))
    assert message.startswith("module 'maths': maths.bn:2:10") and "y" in message


def test_a_name_both_defined_and_imported_fails(schema):
    src = MAIN + "\ngeometry graph double(x: Float) -> Float {\n  return x\n}\n"
    assert "'double' is defined here and imported from maths" in errors(src, schema, loader({("maths", None): MATHS}))


def test_a_name_in_two_modules_fails(schema):
    src = "use maths\nuse autres\n\n" + MAIN.split("\n\n", 1)[1]
    load = loader({("maths", None): MATHS, ("autres", None): MATHS.split("\n\n")[0] + "\n"})
    assert any("'double' is in maths and in autres" in m for m in errors(src, schema, load))


def test_the_same_module_twice_fails(schema):
    src = "use maths\nuse maths (double)\n\n" + MAIN.split("\n\n", 1)[1]
    assert "only one use per module" in errors(src, schema, loader({("maths", None): MATHS}))[0]


def test_modules_may_use_modules_each_loaded_once(schema):
    base = "geometry graph un() -> Float {\n  return 1.0\n}\n"
    mid = "use base\n\ngeometry graph deux() -> Float {\n  return un() + un()\n}\n"
    src = "use base\nuse mid\n\ngeometry graph g() -> Float {\n  return deux() + un()\n}\n"
    load = loader({("base", None): base, ("mid", None): mid})
    graphs = compile_source(src, schema, "t.bn", load)
    assert [(g.name, g.module and g.module[0]) for g in graphs] == [("un", "base"), ("deux", "mid"), ("g", None)]
    assert load.asked == [("base", None), ("mid", None)]


def test_a_cycle_of_modules_fails(schema):
    a = "use b\n\ngeometry graph fa() -> Float {\n  return 1.0\n}\n"
    b = "use a\n\ngeometry graph fb() -> Float {\n  return 1.0\n}\n"
    src = "use a\n\ngeometry graph g() -> Float {\n  return fa()\n}\n"
    (message,) = errors(src, schema, loader({("a", None): a, ("b", None): b}))
    assert "circular import: a -> b -> a" in message


def test_a_group_of_the_file_is_called_by_its_key(schema):
    schema.existing = {"smooth_by_angle": GroupSpec("Smooth by Angle", (("Mesh", "Geometry"), ("Angle", "Float")),
                                                    (("Mesh", "Geometry"),))}
    src = "geometry graph g(mesh: Geometry) -> Geometry {\n  return smooth_by_angle(mesh, angle: 0.5)\n}\n"
    (g,) = compile_source(src, schema)
    (node,) = [n for n in g.nodes if n.group]
    assert node.group == "Smooth by Angle" and node.bl_idname == "GeometryNodeGroup"
    assert node.values == {"Angle": 0.5}


def test_a_graph_of_the_text_wins_over_a_group_of_the_file(schema):
    schema.existing = {"double": GroupSpec("double", (("x", "Float"), ("y", "Float")), (("r", "Float"),))}
    graphs = compile_source(MATHS, schema)
    (node, _) = [n for n in graphs[1].nodes if n.group]
    assert graphs[1].name == "quadruple" and node.n_inputs == 1


def test_two_groups_with_one_key_are_ambiguous(schema):
    spec = (("x", "Float"),), (("r", "Float"),)
    schema.existing = {"ab": [GroupSpec("ab", *spec), GroupSpec("AB ", *spec)]}
    src = "geometry graph g() -> Float {\n  return ab(1.0)\n}\n"
    assert errors(src, schema) == ["'ab' refers to multiple groups in the file: ab, AB "]


def test_use_as_alias_and_namespaced_call(schema):
    lib = """\
geometry graph double(x: Float) -> Float {
  return x * 2.0
}
"""
    src = """\
use maths as m

geometry graph g(val: Float) -> Float {
  return m::double(val)
}
"""
    graphs = compile_source(src, schema, load=loader({("maths", None): lib}))
    assert len(graphs) == 2
    assert graphs[0].name == "double"
    assert graphs[1].name == "g"
    (node,) = [n for n in graphs[1].nodes if n.group]
    assert node.group == "double"

    # Test round-trip formatting
    file = parse(src)
    assert file.uses[0].alias == "m"
    printed = to_source(file)
    assert "use maths as m" in printed
    assert "m::double(val)" in printed



def test_a_use_brings_no_material(schema):
    lib = MATHS + "\nshader(material: true) graph clay() -> (thickness: Float) {\n  return (thickness: 0.5)\n}\n"
    graphs = compile_source(MAIN, schema, "t.bn", loader({("maths", None): lib}))
    assert "clay" not in [g.name for g in graphs]
    src = MAIN.replace("use maths", "use maths (clay)")
    assert errors(src, schema, loader({("maths", None): lib}))[0] == "'clay' is a material: a use brings node groups only"


BASE = "geometry graph sq(x: Float) -> Float {\n  return x * x\n}\n"
MID = "use base\n\ngeometry graph deux(x: Float) -> Float {\n  return sq(x) + 1.0\n}\n"


def calls(g):
    return [n.group for n in g.nodes if n.group]


def test_a_graph_named_like_one_a_used_module_uses_is_its_own(schema):
    """mid uses base, which has sq; the text uses mid alone and has a sq of its own: base's sq is not
    one of its names, so both are built, as two groups, each called where it is meant."""
    src = "use mid\n\ngeometry graph sq() -> Float {\n  return deux(2.0)\n}\n"
    graphs = compile_source(src, schema, "t.bn", loader({("base", None): BASE, ("mid", None): MID}))
    by_name = {g.name: g for g in graphs}
    assert len(by_name) == len(graphs) == 3, [g.name for g in graphs]
    own = by_name["sq"]
    assert own.module is None and calls(own) == ["deux"]
    (base_sq,) = [g for g in graphs if g.module == ("base", None)]
    assert base_sq.name != "sq" and base_sq.called_as == "sq"
    assert calls(by_name["deux"]) == [base_sq.name]


def test_a_text_s_graph_and_a_namespaced_one_of_one_name(schema):
    """`use base (…)` does not bring sq, but `base::sq` still calls it: the text's sq is another group."""
    other = BASE + "\ngeometry graph un() -> Float {\n  return 1.0\n}\n"
    src = ("use base (un)\n\ngeometry graph sq() -> Float {\n  return base::sq(3.0)\n}\n\n"
           "geometry graph g() -> Float {\n  return sq() + un()\n}\n")
    graphs = compile_source(src, schema, "t.bn", loader({("base", None): other}))
    by_name = {g.name: g for g in graphs}
    assert len(by_name) == len(graphs) == 4, [g.name for g in graphs]
    (base_sq,) = [g for g in graphs if g.module and g.called_as == "sq"]
    assert calls(by_name["sq"]) == [base_sq.name] and calls(by_name["g"]) == ["sq", "un"]


def test_two_modules_with_a_graph_of_one_name(schema):
    """Two modules that each use one with a graph of the same name (helper): each calls its own."""
    a = "geometry graph helper() -> Float {\n  return 1.0\n}\n"
    b = "geometry graph helper() -> Float {\n  return 2.0\n}\n"
    ua = "use a\n\ngeometry graph fa() -> Float {\n  return helper()\n}\n"
    ub = "use b\n\ngeometry graph fb() -> Float {\n  return helper()\n}\n"
    src = "use ua\nuse ub\n\ngeometry graph g() -> Float {\n  return fa() + fb()\n}\n"
    load = loader({("a", None): a, ("b", None): b, ("ua", None): ua, ("ub", None): ub})
    graphs = compile_source(src, schema, "t.bn", load)
    by_name = {g.name: g for g in graphs}
    assert len(by_name) == len(graphs) == 5, [g.name for g in graphs]
    (ha,) = calls(by_name["fa"])
    (hb,) = calls(by_name["fb"])
    assert ha != hb and by_name[ha].module[0] == "a" and by_name[hb].module[0] == "b"


def test_a_module_graph_is_called_by_its_quoted_name_or_its_key(schema):
    """`m::"Big Double"(…)`, the graph's name quoted after the module as the spec writes it
    (`c2::"parallel contour 2d"`), and `m::big_double(…)`, its key, call the same graph."""
    lib = 'geometry graph "Big Double"(x: Float) -> Float {\n  return x * 2.0\n}\n'
    src = ('use maths as m\n\ngeometry graph g(v: Float) -> Float {\n'
           '  return m::"Big Double"(v) + m::big_double(v) + maths::"Big Double"(v)\n}\n')
    graphs = compile_source(src, schema, "t.bn", loader({("maths", None): lib}))
    assert calls(graphs[-1]) == ["Big Double"] * 3


def test_no_example_takes_the_name_of_a_module():
    """`use name` finds the text name.bn of the .blend, then name.bn next to the imported file, before
    the stdlib: an example named like a module would stand for it, in its folder and once opened in
    the Text Editor, and `use name (…)` would find the example's graphs instead of the module's."""
    root = Path(__file__).resolve().parents[2]
    modules = {p.stem for p in (root / "stdlib").glob("*.bn")}
    clash = sorted(str(p.relative_to(root)) for p in (root / "examples").rglob("*.bn") if p.stem in modules)
    assert not clash, f"examples named like a stdlib module: {clash}"
