"""What the checker makes of a node's settings in brackets (spec/reference.md, Expressions).

A setting by position is an enum value: it goes to the one enum setting of the node that holds it,
whatever their order; a value two settings hold is named. Every other setting is named. An argument
in parentheses is an input, always.
"""

import itertools
import json
import random

import pytest

from base_node_blender import BnError, compile_source
from base_node_blender.backend import BackendSchema, versions
from base_node_blender.schema import NodeSpec, Prop, by_position, enum_settings, holders, is_word
from fake_schema import S, FakeSchema


def compile_one(source, schema):
    return compile_source(source, schema, "t.bn")[-1]


def errors(source, schema):
    with pytest.raises(BnError) as err:
        compile_source(source, schema, "t.bn")
    return [str(d) for d in err.value.diagnostics]


def graph(body, sig="geometry graph g(geometry: Geometry, t: Float) -> Geometry"):
    return f"{sig} {{\n{body}\n}}"


class Axes(FakeSchema):
    """A node with two enum settings that share their values, as Align Euler to Vector has."""

    def node(self, kind, name):
        if name == "AlignEulerToVector" and kind == "geometry":
            return NodeSpec("AlignEulerToVector", "FunctionNodeAlignEulerToVector", {
                "axis": Prop("axis", "ENUM", ("X", "Y", "Z")),
                "pivot_axis": Prop("pivot_axis", "ENUM", ("AUTO", "X", "Y", "Z")),
            })
        return super().node(kind, name)

    def sockets(self, kind, spec, props):
        if spec.name == "AlignEulerToVector":
            return [S("Rotation", "Vector"), S("Factor", "Float"), S("Vector", "Vector")], [S("Rotation", "Vector")]
        return super().sockets(kind, spec, props)


def node(src, schema, bl_idname):
    return next(n for n in compile_one(src, schema).nodes if n.bl_idname == bl_idname)


def test_an_enum_value_by_position_goes_to_the_setting_that_holds_it(schema):
    n = node(graph("  c = Compare[INT, EQUAL](a: 1, b: 2)\n  return geometry"), schema, "FunctionNodeCompare")
    assert n.props == {"data_type": "INT", "operation": "EQUAL"}
    # In any order: each value finds its own setting
    n = node(graph("  c = Compare[EQUAL, INT](a: 1, b: 2)\n  return geometry"), schema, "FunctionNodeCompare")
    assert n.props == {"data_type": "INT", "operation": "EQUAL"}


def test_a_value_two_settings_hold_is_named():
    schema = Axes()
    # X is a value of axis and of pivot_axis: by position, Blender's order would decide
    for written in ("X", "X, pivot_axis: Z"):
        assert errors(graph(f"  r = AlignEulerToVector[{written}](vector: (1.0, 0.0, 0.0))\n  return geometry"),
                      schema) == [f"t.bn:2:{26 + written.index('X')}  AlignEulerToVector: X is a value of axis and "
                                  "of pivot_axis; name it, AlignEulerToVector[axis: X]"]
    n = node(graph("  r = AlignEulerToVector[axis: X, pivot_axis: Z](vector: (1.0, 0.0, 0.0))\n  return geometry"),
             schema, "FunctionNodeAlignEulerToVector")
    assert n.props == {"axis": "X", "pivot_axis": "Z"}
    # A value one of them holds alone goes by position
    n = node(graph("  r = AlignEulerToVector[AUTO, axis: Y](vector: (1.0, 0.0, 0.0))\n  return geometry"),
             schema, "FunctionNodeAlignEulerToVector")
    assert n.props == {"pivot_axis": "AUTO", "axis": "Y"}


def test_two_values_by_position_for_one_setting_are_given_twice(schema):
    assert errors(graph("  c = Compare[INT, FLOAT](a: 1, b: 2)\n  return geometry"), schema) == [
        "t.bn:2:20  setting 'data_type' given twice"]


BACKENDS = versions()


@pytest.mark.parametrize("written", list(itertools.permutations(["VECTOR", "DOT_PRODUCT", "GREATER_THAN"])))
def test_the_order_of_the_values_by_position_does_not_matter(written):
    schema = BackendSchema(BACKENDS[-1])
    n = node(graph(f"  c = Compare[{', '.join(written)}](a: (0.0, 0.0, 1.0), b: (0.0, 1.0, 0.0))\n  return geometry"),
             schema, "FunctionNodeCompare")
    assert n.props == {"data_type": "VECTOR", "mode": "DOT_PRODUCT", "operation": "GREATER_THAN"}


def test_the_function_reads_no_order():
    for enums in ({"axis": ("X", "Y"), "pivot_axis": ("AUTO", "X")}, {"pivot_axis": ("X", "AUTO"), "axis": ("Y", "X")}):
        assert holders(enums, "X") == ["axis", "pivot_axis"]
        assert by_position(enums, "X") is None
        assert by_position(enums, "AUTO") == "pivot_axis"
        assert by_position(enums, "NOPE") is None
        # Several values that mean the same, a type's
        assert by_position(enums, ("Y", "Z")) == "axis"


def shuffled(schema, seed):
    """`schema` with the settings of every node in another order, and each setting's values."""
    rng = random.Random(seed)
    for nodes in schema.entries.values():
        for entry in nodes.values():
            rng.shuffle(entry["settings"])
            for s in entry["settings"]:
                if s.get("items"):
                    rng.shuffle(s["items"])
    schema.specs.clear()
    return schema


def every_value_by_position(schema):
    """{(kind, node, value): the error at the value, or the setting it went to} of every enum value
    of every node of `schema`, each written alone by position."""
    found = {}
    for kind in ("geometry", "shader", "compositor"):
        for name in schema.node_names(kind):
            values = sorted({x for items in enum_settings(schema.node(kind, name)).values() for x in items})
            if not values:
                continue
            lines = [f"  x{i} = {name}[{v if is_word(v) else json.dumps(v)}]()" for i, v in enumerate(values)]
            src = f"{kind} graph g(x: Float) -> Float {{\n" + "\n".join(lines) + "\n  return x\n}\n"
            at = len(name) + 8  # the column of the value, past `  x<i> = Name[`
            try:
                ir = compile_source(src, schema, "t.bn")[-1]
            except BnError as e:
                errs = {d.line: d.message for d in e.diagnostics if d.col == at + len(str(d.line - 2))}
                ir = None
            else:
                errs = {}
            for i, v in enumerate(values):
                found[(kind, name, v)] = errs.get(i + 2)
            if ir is not None:
                made = [n for n in ir.nodes if n.bl_idname == schema.node(kind, name).bl_idname]
                for n, v in zip(made, values):
                    found[(kind, name, v)] = next(k for k, x in n.props.items() if x == v)
    return found


@pytest.mark.parametrize("version", BACKENDS)
def test_a_value_by_position_is_accepted_iff_one_setting_holds_it(version):
    schema = BackendSchema(version)
    found = every_value_by_position(schema)
    assert len(found) > 1000
    for (kind, name, v), got in found.items():
        held = holders(enum_settings(schema.node(kind, name)), v)
        if len(held) == 1:
            assert got in (None, held[0]), (kind, name, v, got)
        else:
            shown = v if is_word(v) else json.dumps(v)
            assert got == (f"{name}: {shown} is a value of {' and of '.join(held)}; name it, "
                           f"{name}[{held[0]}: {shown}]"), (kind, name, v)
    # Blender's order of the settings, and of their values, changes nothing
    for seed in (1, 2):
        assert every_value_by_position(shuffled(BackendSchema(version), seed)) == found


def test_named_settings_of_every_kind(schema):
    n = node(graph("  x = Math[ADD, use_clamp: true](Value: t, Value_001: 1.0)\n  return geometry"), schema, "ShaderNodeMath")
    assert n.props == {"operation": "ADD", "use_clamp": True}


@pytest.mark.parametrize("call, message", [
    ("Math[ADDD](Value: t, Value_001: 1.0)", "2:12  no setting of Math takes ADDD; did you mean ADD?; settings: operation"),
    ("Math[clamp: true](Value: t, Value_001: 1.0)", "2:12  Math has no setting 'clamp'; did you mean use_clamp?; "
                                  "settings: operation, use_clamp"),
    ("Math[ADD, operation: SUBTRACT](Value: t, Value_001: 1.0)", "2:17  setting 'operation' given twice"),
    ("Math[true](Value: t, Value_001: 1.0)", "2:12  Math: a setting by position is an enum value; name the others, "
                           "Math[operation: …]"),
    ("Math[use_clamp: 1.0](Value: t, Value_001: 1.0)", "2:12  use_clamp expects a boolean value"),
    ("Math[operation: 2](Value: t, Value_001: 1.0)", "2:12  operation expects a value like ADD"),
    ("Position[POINT]()", "2:16  no setting of Position takes POINT"),
    ("Position[name: 1]()", "2:16  Position has no setting 'name': it has none"),
])
def test_a_setting_says_what_is_wrong(schema, call, message):
    assert errors(graph(f"  x = {call}\n  return geometry"), schema) == [f"t.bn:{message}"]


def test_a_setting_in_parentheses_is_an_input_like_any_other(schema):
    assert errors(graph("  x = Math(Value: t, Value_001: 1.0, operation: ADD)\n  return geometry"), schema) == [
        "t.bn:2:38  Math has no input 'operation'; inputs: Value, Value_001"]


def test_only_a_node_has_settings(schema):
    src = ("geometry graph f(x: Float) -> Float {\n  return x\n}\n\n"
           "geometry graph g(geometry: Geometry, t: Float) -> Geometry {\n"
           "  a = f[ADD](t)\n  b = sin[ADD](t)\n  return geometry\n}\n")
    assert errors(src, schema) == ["t.bn:6:9  f has no settings", "t.bn:7:11  sin has no settings"]


def test_a_name_the_zone_gives_holds_a_value(schema):
    src = graph("  r = repeat(3, s: 0.0) -> {\n    m = Math[iteration](Value: s, Value_001: 1.0)\n    return (s: m)\n  }\n"
                "  return geometry")
    assert errors(src, schema) == ["t.bn:3:14  'iteration' holds a value, and no wire feeds a setting: "
                                   "give it in the parentheses, Name[SETTING](input: value)"]


def test_the_domain_of_a_foreach_is_its_setting(schema):
    for written in ("FACE", "domain: FACE"):
        g = compile_one(graph(f"  e = foreach[{written}](geometry) -> {{\n    return (mesh: element)\n  }}\n"
                              "  return geometry"), schema)
        out = next(n for n in g.nodes if n.bl_idname == "GeometryNodeForeachGeometryElementOutput")
        assert out.props == {"domain": "FACE"}
    assert errors(graph("  e = foreach[size: 2](geometry) -> {\n    return (mesh: element)\n  }\n"
                        "  return geometry"), schema) == ["t.bn:2:15  foreach has no setting 'size'; settings: domain"]


@pytest.mark.parametrize("word", ["repeat", "simulate"])
def test_repeat_and_simulate_have_no_settings(schema, word):
    count = "3, " if word == "repeat" else ""
    src = graph(f"  r = {word}[FACE]({count}s: 0.0) -> {{\n    return (s: s)\n  }}\n  return geometry")
    assert errors(src, schema) == [f"t.bn:2:7  {word} has no settings"]


# A number Blender cannot keep: a warning where it is written, and the tree holds Blender's value

def warned(body, schema):
    warnings = []
    compile_source(graph(body), schema, "t.bn", warnings=warnings)
    return [str(w) for w in warnings]


@pytest.mark.parametrize("written", ["0.1", "1e-7", "3.141593", "0.5", "16777216.0", "-2.75"])
def test_a_number_a_float_keeps_is_not_warned_of(schema, written):
    assert warned(f"  x = Math[ADD](Value: t, Value_001: {written})\n  return geometry", schema) == []


@pytest.mark.parametrize("written, kept", [("16777217.0", "16777216.0"), ("0.123456789123", "0.12345679")])
def test_a_number_a_float_cannot_keep_is_warned_of_where_it_is_written(schema, written, kept):
    assert warned(f"  x = Math[ADD](Value: t, Value_001: {written})\n  return geometry", schema) == [
        f"t.bn:2:38  warning: precision lost: {written} is stored as {kept} (IEEE 754 single precision)"]


def test_every_place_a_float_lands_is_looked_at(schema):
    src = ("geometry graph g(geometry: Geometry, t: Float = 0.123456789123 in 0.0..16777217.0) -> Geometry {\n"
           "  v = CombineXYZ(x: 0.1, y: 16777217.0, z: 0.0)\n"
           "  return geometry |> SetPosition(offset: (1.0, 2.0, 0.123456789123))\n}\n")
    warnings = []
    compile_source(src, schema, "t.bn", warnings=warnings)
    assert [(w.line, w.col, w.severity) for w in warnings] == [
        (1, 49, "warning"), (1, 72, "warning"), (2, 29, "warning"), (3, 53, "warning")]


def test_the_command_line_warns_of_a_number_too(tmp_path, capsys):
    from base_node_blender.cli import main

    path = tmp_path / "p.bn"
    path.write_text("geometry graph g(t: Float) -> Float {\n  return t * 16777217.0\n}\n", encoding="utf-8")
    assert main(["check", "--target", "blender", str(path)]) == 0
    assert capsys.readouterr().err == (
        f"{path.name}:2:14  warning: precision lost: 16777217.0 is stored as 16777216.0 (IEEE 754 single precision)\n")
