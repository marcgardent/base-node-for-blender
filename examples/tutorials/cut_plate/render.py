"""Build each step of the cut plate tutorial in Blender and render its picture.

  blender -b --factory-startup --python-exit-code 1 --python examples/tutorials/cut_plate/render.py
  blender -b --factory-startup --python-exit-code 1 --python examples/tutorials/cut_plate/render.py -- --only step3

Every step*.bn of this folder is built from scratch in an empty scene, its cut_plate on an object
lying on a dark table, under the same camera and lights, and rendered with Cycles to
site/images/tutorials/cut-plate-<step>.png. The page shows these files' text: a step that does not
build stops the script.

Each step's plate is measured too, and the numbers the page gives are checked against it: the
corners of step 2, the centres of the holes of step 3, the pieces the pick of step 4 drops, the
heights of the layers of step 5. Then the groups (geometry and shader) and the materials of the last
step go through the regression tests' round trip (tests/test_libraries.py).
"""

import math
import sys
import tempfile
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "site" / "images" / "tutorials"
STDLIB = ROOT / "stdlib"
sys.path.insert(0, str(ROOT / "addon" / "tests"))
import test_libraries  # noqa: E402  (loads the extension as `base_node`)

from base_node.host import build_source, export_tree  # noqa: E402

SAMPLES = 64
SIZE = (1000, 500)
# The tip of the outline is at x = 2.2, its neighbours at (1.1, ±0.65): an angle of 61.2 degrees.
# The centre of an arc of radius 0.3 there is 0.3 / sin(30.6 degrees) = 0.59 in from the tip
TIP_CENTRE = 2.2 - 0.3 / math.sin(math.atan2(0.65, 1.1))


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return argv[argv.index("--only") + 1] if "--only" in argv else None


def loader(name, _caller):
    """`use planar2d` and `use fillet2d` read the modules of this repository's stdlib/."""
    path = STDLIB / f"{name}.bn"
    return path.read_text(encoding="utf-8"), str(path)


def empty_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            for device in prefs.devices:
                device.use = True
            scene.cycles.device = "GPU"
            break
        except TypeError:
            continue
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = SIZE
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("Room")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.04, 0.04, 0.045, 1.0)
    scene.world = world

    # The table: a dark, matt square the plate lies on, seen through its holes
    table = bpy.data.meshes.new("Table")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=12.0)
    bm.to_mesh(table)
    bm.free()
    felt = bpy.data.materials.new("Felt")
    felt.use_nodes = True
    bsdf = felt.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.035, 0.04, 0.045, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.9
    table.materials.append(felt)
    scene.collection.objects.link(bpy.data.objects.new("Table", table))

    aim = bpy.data.objects.new("Aim", None)
    aim.location = (0.0, 0.0, 0.0)
    scene.collection.objects.link(aim)
    # A large soft light behind the plate, where its top mirrors it to the camera, and a key light
    # in front, on the left, that draws the walls of the cuts
    for name, location, size, energy in (
        ("Back", (2.0, 5.0, 4.0), 2.5, 300.0),
        ("Key", (-4.5, -3.5, 5.0), 2.0, 450.0),
    ):
        light = bpy.data.objects.new(name, bpy.data.lights.new(name, "AREA"))
        light.data.size = size
        light.data.energy = energy
        light.location = location
        light.constraints.new("TRACK_TO").target = aim
        scene.collection.objects.link(light)

    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    cam.data.lens = 55
    cam.location = (0.0, -5.6, 6.2)
    cam.constraints.new("TRACK_TO").target = aim
    scene.collection.objects.link(cam)
    scene.camera = cam
    return scene


def build(path):
    source = path.read_text(encoding="utf-8")
    groups = {g.name: g for g in build_source(source, filename=path.name, load=loader)}
    obj = bpy.data.objects.new("Cut plate", bpy.data.meshes.new("Cut plate"))
    bpy.context.scene.collection.objects.link(obj)
    obj.modifiers.new("Cut plate", "NODES").node_group = groups["cut_plate"]
    return obj


def set_input(obj, name, value):
    """Give the modifier's input `name` a value, as its panel would."""
    modifier = obj.modifiers[0]
    item = next(i for i in modifier.node_group.interface.items_tree if getattr(i, "in_out", "") == "INPUT"
                and i.name == name)
    getattr(modifier.properties.inputs, item.identifier).value = value
    obj.update_tag()


def measure(obj):
    """The evaluated plate: its vertices and faces, and its separate pieces."""
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    verts = [v.co.copy() for v in bm.verts]
    seen, pieces = set(), 0
    for v in bm.verts:
        if v.index in seen:
            continue
        pieces += 1
        todo = [v]
        while todo:
            w = todo.pop()
            if w.index in seen:
                continue
            seen.add(w.index)
            todo += [e.other_vert(w) for e in w.link_edges]
    faces = len(bm.faces)
    bm.free()
    ev.to_mesh_clear()
    return {"verts": verts, "faces": faces, "pieces": pieces}


def render(name):
    OUT.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.filepath = str(OUT / f"cut-plate-{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"rendered {scene.render.filepath}")


def check_round_trip(path):
    """The regression tests' round trip, for the groups and the materials of the last step.

    It builds the Geometry Nodes groups again before the materials, so `cut_plate`, which sets the
    materials Brass and Enamel of the same text, cannot build there: its text is checked here instead.
    """
    empty_scene()
    build(path)
    text, _ = export_tree(bpy.data.node_groups["cut_plate"])
    again, _ = export_tree(build_source(text, filename="cut_plate.bn")[-1])
    assert again == text, "cut_plate does not read back the same"
    print("round trip cut_plate: ok (with its materials)")

    blend = Path(tempfile.mkdtemp()) / "cut_plate.blend"
    materials = {bpy.data.materials["Brass"], bpy.data.materials["Enamel"]}
    bpy.data.libraries.write(str(blend), set(bpy.data.node_groups) | materials)
    records, _ = test_libraries.round_trip(blend, trees=("geometry", "shader", "material"))
    records.pop("cut_plate")
    for name, record in sorted(records.items()):
        print(f"round trip {name}: {record['status']}")
    assert records and all(r["status"] == "ok" for r in records.values()), records


def close(a, b, tolerance=0.002):
    return abs(a - b) <= tolerance


def check(step, found):
    """The numbers the page gives for this step, measured on its plate."""
    xs = [v.x for v in found["verts"]]
    ys = [v.y for v in found["verts"]]
    zs = [v.z for v in found["verts"]]
    if step == "step1":
        # The outline: 4.4 long, 1.3 wide; the plate 0.08 thick
        assert close(max(xs), 2.2) and close(min(xs), -2.2), (min(xs), max(xs))
        assert close(max(ys), 0.65) and close(min(ys), -0.65), (min(ys), max(ys))
        assert close(max(zs), 0.08) and close(min(zs), 0.0), (min(zs), max(zs))
    if step == "step2":
        # A round tip of radius 0.3 ends 0.3 past its centre, 0.59 in from the corner: at 1.91
        assert close(max(xs), TIP_CENTRE + 0.3, 0.003), max(xs)
    if step == "step3":
        # Each hole: 32 points at 0.1 from the centre of its tip's arc, on the top and underneath
        for sign in (1.0, -1.0):
            ring = [v for v in found["verts"] if close((v - Vector((sign * TIP_CENTRE, 0.0, v.z))).length, 0.1)]
            assert len(ring) >= 64, (sign, len(ring))
    if step == "step4":
        # The plate in one piece, its top and its underside: the pick dropped everything else
        assert found["pieces"] == 2, found["pieces"]
    if step == "step5":
        # Under the panel the body, its underside, the raised frame, and 8 raised letters
        assert found["pieces"] == 3 + 8, found["pieces"]
        levels = sorted({round(z, 4) for z in zs})
        assert levels == [0.0, 0.055, 0.08], levels
    if step == "step6":
        # Step 5's 11 pieces, and the enamel: the panel's ground and the 5 counters
        assert found["pieces"] == 11 + 6, found["pieces"]
        levels = sorted({round(z, 4) for z in zs})
        assert levels == [0.0, 0.055, 0.07, 0.08], levels
    print(f"{step}: the page's numbers hold")


def main():
    only = args()
    steps = sorted(HERE.glob("step*.bn"))
    for path in steps:
        step = path.stem.split("_")[0]
        if only and only != step:
            continue
        empty_scene()
        obj = build(path)
        found = measure(obj)
        print(f"{step}: {found['faces']} faces, {found['pieces']} pieces")
        check(step, found)
        render(step)
        if step == "step4":
            # The same stencil, the pieces inside the letters kept: what planar_faces alone gives
            set_input(obj, "drop", False)
            kept = measure(obj)
            print(f"{step}, drop off: {kept['faces']} faces, {kept['pieces']} pieces")
            # The 5 counters, of B (2), A, O and D, each a top and an underside
            assert kept["pieces"] == 2 + 5 * 2, kept["pieces"]
            render("step4-kept")
    if not only or only == "round-trip":
        check_round_trip(steps[-1])


main()
