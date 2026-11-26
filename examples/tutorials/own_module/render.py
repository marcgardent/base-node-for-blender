"""Build each step of the tutorial Write your own module in Blender and render its picture.

  blender -b --factory-startup --python-exit-code 1 --python examples/tutorials/own_module/render.py
  blender -b --factory-startup --python-exit-code 1 --python examples/tutorials/own_module/render.py -- --only step3

Each step is a folder of .bn files, imported together from scratch in an empty scene by the add-on's
own File > Import (base_node.import_bn), all but the module waves.bn: a `use waves` finds it next to
the file that names it,
and a file that sets the material another file defines goes again after it. Then an object carries
the graph dunes, as Instantiate the Example does, and Cycles renders it to
site/images/tutorials/own-module-<step>.png. A step that does not build, or builds without its
module or its material, stops the script.

Step 6 has no waves.bn: the waves.bn of step 5 is installed first into a Module Folder, as the drop
dialog's Install as Library does (base_node.drop_bn, action LIBRARY), and `use waves` finds it there.

Steps 2 to 4 move code between files and must not change the picture: each is checked against step
1. Then the groups and materials of the last steps go through the regression tests' round trip
(tests/test_libraries.py), and dunes reads back as a `use` of the module.
"""

import math
import shutil
import sys
import tempfile
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "site" / "images" / "tutorials"
sys.path.insert(0, str(ROOT / "addon" / "tests"))
import test_libraries  # noqa: E402  (loads the extension as `base_node`)

import base_node  # noqa: E402
from base_node.host import build_source, export_tree, modules  # noqa: E402
from base_node.ui import prefs  # noqa: E402

SAMPLES = 64
SIZE = (960, 540)
# The steps that only move code between files: the picture of step 1, to the pixel
SAME_AS_STEP1 = ("step2", "step3", "step4")
# The module each step's dunes calls, and where it comes from
MODULE = {"step1": None, "step2": "waves", "step3": "waves", "step4": "waves", "step5": "waves", "step6": "waves"}


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return argv[argv.index("--only") + 1] if "--only" in argv else None


def empty_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    cycles = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA"):
        try:
            cycles.compute_device_type = kind
            cycles.get_devices()
            for device in cycles.devices:
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
    world = bpy.data.worlds.new("Sky")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.68, 0.9, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35
    scene.world = world
    # A low sun from the west: the slopes facing it lit, the others in shade
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 5.0
    sun.data.angle = math.radians(1.0)
    sun.data.color = (1.0, 0.92, 0.8)
    sun.rotation_euler = Vector((0.9, -0.3, -0.3)).normalized().to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(sun)
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    cam.data.lens = 38
    cam.location = (-5.0, -8.0, 4.6)
    aim = bpy.data.objects.new("Aim", None)
    aim.location = (0.5, 0.4, -0.3)
    scene.collection.objects.link(aim)
    cam.constraints.new("TRACK_TO").target = aim
    scene.collection.objects.link(cam)
    scene.camera = cam
    return scene


def import_folder(folder):
    """The .bn files of the folder but waves.bn, imported together as File > Import does with several
    files chosen. waves.bn is not imported: the `use waves` of the others finds it next to them."""
    names = sorted(p.name for p in folder.glob("*.bn") if p.name != "waves.bn")
    result = bpy.ops.base_node.import_bn(directory=str(folder) + "/", files=[{"name": n} for n in names])
    assert result == {"FINISHED"}, f"{folder.name}: import {result}"


def check_built(step):
    """dunes is built, its material set to Sand, its waves a group of the module that step names."""
    dunes = bpy.data.node_groups["dunes"]
    sand = bpy.data.materials.get("Sand")
    assert sand is not None, f"{step}: no material Sand"
    set_material = next(n for n in dunes.nodes if n.bl_idname == "GeometryNodeSetMaterial")
    assert set_material.inputs["Material"].default_value == sand, f"{step}: dunes does not set Sand"
    called = [n.node_tree for n in dunes.nodes if n.bl_idname == "GeometryNodeGroup"]
    assert called, f"{step}: dunes calls no group"
    for tree in called:
        assert tree.get(modules.MODULE) == MODULE[step], \
            f"{step}: {tree.name} comes from {tree.get(modules.MODULE)!r}, not {MODULE[step]!r}"
    print(f"{step}: dunes calls {', '.join(t.name for t in called)}, module {MODULE[step]}, material Sand")


def instantiate():
    """An object carrying dunes, as the drop dialog's Instantiate the Example makes it."""
    obj = bpy.data.objects.new("Dunes", bpy.data.meshes.new("Dunes"))
    bpy.context.scene.collection.objects.link(obj)
    obj.modifiers.new("Dunes", "NODES").node_group = bpy.data.node_groups["dunes"]
    return obj


def render(step):
    OUT.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.filepath = str(OUT / f"own-module-{step}.png")
    bpy.ops.render.render(write_still=True)
    print(f"rendered {scene.render.filepath}")
    return scene.render.filepath


def same_picture(step, a, b):
    first, second = bpy.data.images.load(a), bpy.data.images.load(b)
    worst = max(abs(x - y) for x, y in zip(first.pixels[:], second.pixels[:]))
    assert worst < 2 / 255, f"{step} differs from step 1 by {worst * 255:.1f} levels"
    print(f"{step} renders step 1: ok (largest difference {worst * 255:.1f} levels)")


def install(module_folder):
    """waves.bn of step 5 into the Module Folder, by the drop dialog's Install as Library."""
    prefs.DEFAULTS.module_folder = str(module_folder)
    prefs.apply_folders()
    result = bpy.ops.base_node.drop_bn(filepath=str(HERE / "step5" / "waves.bn"), action="LIBRARY")
    assert result == {"FINISHED"}, result
    installed = module_folder / "waves.bn"
    assert installed.read_text(encoding="utf-8") == (HERE / "step5" / "waves.bn").read_text(encoding="utf-8")
    print(f"installed {installed}")


def build_step(step, module_folder):
    empty_scene()
    if step == "step6":
        install(module_folder)
        assert not (HERE / step / "waves.bn").exists(), "step 6 must find waves in the Module Folder"
    import_folder(HERE / step)
    check_built(step)
    instantiate()


def check_round_trip(step, module_folder):
    """dunes reads back as a use of waves, and builds back to the same text; the other groups and
    materials go through the regression tests' round trip."""
    build_step(step, module_folder)
    text, warnings = export_tree(bpy.data.node_groups["dunes"])
    assert not warnings, warnings
    assert "\nuse waves" in text, f"dunes does not read back as a use of waves:\n{text}"
    use = " ".join(text[text.index("\nuse waves") + 1:].split("\ngeometry graph")[0].split())
    again, _ = export_tree(build_source(text, filename="dunes.bn")[-1])
    assert again == text, "dunes does not read back the same"
    print(f"round trip dunes of {step}: ok, read back as {use!r}")

    # dunes sets the material Sand of another text: it cannot build where the materials are built
    # after the groups, so it is checked above, and the others here
    blend = Path(tempfile.mkdtemp()) / f"own_module_{step}.blend"
    bpy.data.libraries.write(str(blend), set(bpy.data.node_groups) | set(bpy.data.materials))
    records, _ = test_libraries.round_trip(blend, trees=("geometry", "shader", "material"))
    records.pop("dunes")
    for name, record in sorted(records.items()):
        print(f"round trip {name}: {record['status']}")
    assert records and all(r["status"] == "ok" for r in records.values()), records


def main():
    only = args()
    base_node.register()
    module_folder = Path(tempfile.mkdtemp(prefix="module_folder_"))
    pictures = {}
    try:
        for folder in sorted(p for p in HERE.glob("step*") if p.is_dir()):
            step = folder.name
            if only and only != step:
                continue
            build_step(step, module_folder)
            pictures[step] = render(step)
        for step in SAME_AS_STEP1:
            if step in pictures and "step1" in pictures:
                same_picture(step, pictures["step1"], pictures[step])
        if not only or only == "round-trip":
            check_round_trip("step5", module_folder)
            check_round_trip("step6", module_folder)
    finally:
        prefs.DEFAULTS.module_folder = ""
        prefs.apply_folders()
        shutil.rmtree(module_folder)


main()
