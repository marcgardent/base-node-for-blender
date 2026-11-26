"""Build each step of the sci-fi HUD tutorial in Blender and render its picture.

  blender -b --factory-startup --python-exit-code 1 --python examples/tutorials/sci_fi_hud/render.py
  blender -b --factory-startup --python-exit-code 1 --python examples/tutorials/sci_fi_hud/render.py -- --only step3

Every step*.bn of this folder is built from scratch in an empty scene, its sci_fi_hud on an object
seen from straight above by an orthographic camera that frames the screen exactly, and rendered with
EEVEE to site/images/tutorials/sci-fi-hud-<step>.png. A step whose graph has a `phase` input is
rendered at PHASE. The page shows these files' text: a step that does not build stops the script.

The hero, sci-fi-hud.webp, is the last step over FRAMES frames of its phase, from 0 to 1, a loop
encoded by examples/encode_webp.py with the system Python (Blender's has no Pillow). Then the groups
and the material of the last step go through the regression tests' round trip
(tests/test_libraries.py): all read back but the two of KNOWN, which must fail as it says.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "site" / "images" / "tutorials"
sys.path.insert(0, str(ROOT / "addon" / "tests"))
import test_libraries  # noqa: E402  (loads the extension as `base_node`)

from base_node.host import build_source, export_tree  # noqa: E402

STDLIB = ROOT / "stdlib"
SCREEN = 3.6  # metres: the default size of sci_fi_hud's screen, which the camera frames
SIZE = 800  # pixels, square
PHASE = 0.4  # the phase of the stills
FRAMES = 48  # of the hero loop, at 24 frames a second
HERO_SIZE = 480

# The trees that do not read back yet, and the error they give. In a shader tree, a module's graph
# with an input that takes a field from the context (sdf_circle's `p: Vector = Position()`) is built
# again as `sdf circle (Shader)`: Tree -> Text writes that group out in the text, under that name,
# but its calls still say `sdf_circle(…)`, which the text built again does not know. The files
# themselves build: only the trees written back to text fail.
KNOWN = {
    "dial": "unknown node 'sdf_circle' in a shader tree",
    "material:Hud": "unknown node 'sdf_circle' in a shader tree",
}


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return argv[argv.index("--only") + 1] if "--only" in argv else None


def loader(name, _caller):
    path = STDLIB / f"{name}.bn"
    return path.read_text(encoding="utf-8"), str(path)


def empty_scene(size=SIZE):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 16
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("Night")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    scene.world = world
    data = bpy.data.cameras.new("Camera")
    data.type = "ORTHO"
    data.ortho_scale = SCREEN
    cam = bpy.data.objects.new("Camera", data)
    cam.location = (0.0, 0.0, 5.0)  # looking straight down -Z, +Y up in the picture
    scene.collection.objects.link(cam)
    scene.camera = cam
    return scene


def build(path):
    """An object carrying sci_fi_hud of the file, its material Hud built with it."""
    source = path.read_text(encoding="utf-8")
    groups = {g.name: g for g in build_source(source, filename=path.name, load=loader)}
    obj = bpy.data.objects.new("HUD", bpy.data.meshes.new("HUD"))
    bpy.context.scene.collection.objects.link(obj)
    mod = obj.modifiers.new("HUD", "NODES")
    mod.node_group = groups["sci_fi_hud"]
    return mod


def set_phase(mod, value):
    """The modifier's `phase` input, if its graph has one; True when it has."""
    for item in mod.node_group.interface.items_tree:
        if item.item_type == "SOCKET" and item.in_out == "INPUT" and item.name == "phase":
            getattr(mod.properties.inputs, item.identifier).value = float(value)
            mod.id_data.update_tag()
            return True
    return False


def render(filepath):
    OUT.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.filepath = str(filepath)
    bpy.ops.render.render(write_still=True)
    print(f"rendered {filepath}")


def hero(path):
    """The last step over FRAMES frames of its phase, a looping WebP."""
    empty_scene(HERO_SIZE)
    mod = build(path)
    frames = Path(tempfile.mkdtemp())
    for i in range(FRAMES):
        assert set_phase(mod, i / FRAMES), "the last step has no phase"
        render(frames / f"frame_{i:04d}.png")
    out = OUT / "sci-fi-hud.webp"
    subprocess.run(["python3", "-I", str(ROOT / "examples" / "encode_webp.py"), str(frames), str(out), "24", "80"],
                   check=True)


def check_round_trip(path):
    """The regression tests' round trip, for the groups and the material of the last step.

    It builds the Geometry Nodes groups again before the materials, so sci_fi_hud, which sets the
    material Hud of the same text, cannot build there: its text is checked here instead.
    """
    empty_scene()
    build(path)
    text, _ = export_tree(bpy.data.node_groups["sci_fi_hud"])
    again, _ = export_tree(build_source(text, filename="sci_fi_hud.bn", load=loader)[-1])
    assert again == text, "sci_fi_hud does not read back the same"
    print("round trip sci_fi_hud: ok (with its material)")

    blend = Path(tempfile.mkdtemp()) / "sci_fi_hud.blend"
    bpy.data.libraries.write(str(blend), set(bpy.data.node_groups) | set(bpy.data.materials))
    records, _ = test_libraries.round_trip(blend, trees=("geometry", "shader", "material"))
    records.pop("sci_fi_hud")
    for name, record in sorted(records.items()):
        print(f"round trip {name}: {record['status']}")
        if name in KNOWN and record["status"] != "ok":
            assert KNOWN[name] in record.get("error", ""), (name, record)
            print(f"  known: {record['error']}")
            continue
        assert record["status"] == "ok", (name, record)
    assert records


def main():
    only = args()
    steps = sorted(HERE.glob("step*.bn"))
    for path in steps:
        step = path.stem.split("_")[0]
        if only and only != step:
            continue
        empty_scene()
        mod = build(path)
        set_phase(mod, PHASE)
        render(OUT / f"sci-fi-hud-{step}.png")
    if not only or only == "hero":
        hero(steps[-1])
    if not only or only == "round-trip":
        check_round_trip(steps[-1])


main()
