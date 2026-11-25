"""Build each step of the toon lights tutorial in Blender 5.3 and render its picture.

  blender -b --factory-startup --python-exit-code 1 --python examples/tutorials/toon_lights/render.py
  blender -b --factory-startup --python-exit-code 1 --python examples/tutorials/toon_lights/render.py -- --only step3

Every step*.bn of this folder is built from scratch in an empty scene, its still_life on an object,
and rendered with EEVEE to site/images/tutorials/toon-lights-<step>.png. The lights are the
scene's, not the files': the steps add them one by one, as the page says, with their custom
properties (toon_threshold, toon_rim). The page shows these files' text: a step that does not build
stops the script. Then the material Toon of step 4 is read back to its text and built again, and
step 5, the module toon, is checked to render step 4's picture.
"""

import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "site" / "images" / "tutorials"
sys.path.insert(0, str(ROOT / "addon" / "tests"))
import test_libraries  # noqa: E402,F401  (loads the extension as `base_node`)

from base_node.host import build_source, export_tree  # noqa: E402

STDLIB = ROOT / "stdlib"
SIZE = (1000, 750)

# name: (colour, the way its light travels, custom properties)
KEY = ("Key", (1.0, 0.93, 0.82), (0.55, 0.75, -0.6), {})
FILL = ("Fill", (0.45, 0.6, 1.0), (-0.9, 0.15, -0.4), {"toon_threshold": 0.6})
RIM = ("Rim", (1.0, 0.5, 0.25), (-0.7, -0.68, -0.15), {"toon_threshold": 0.25, "toon_rim": 1.0})
LIGHTS = {
    "step1": [KEY],
    "step2": [KEY],
    "step3": [KEY, FILL],
    "step4": [KEY, FILL, RIM],
    "step5": [KEY, FILL, RIM],
}


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return argv[argv.index("--only") + 1] if "--only" in argv else None


def loader(name, _caller):
    path = STDLIB / f"{name}.bn"
    return path.read_text(encoding="utf-8"), str(path)


def empty_scene(lights):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 32
    scene.render.resolution_x, scene.render.resolution_y = SIZE
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    # Flat colours stay the colours the material gives: no tone curve
    scene.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("Sky")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.03, 0.03, 0.04, 1.0)
    scene.world = world
    for name, color, way, properties in lights:
        sun = bpy.data.objects.new(name, bpy.data.lights.new(name, "SUN"))
        sun.data.color = color
        sun.data.angle = math.radians(1.0)
        sun.rotation_euler = Vector(way).normalized().to_track_quat("-Z", "Y").to_euler()
        for key, value in properties.items():
            sun[key] = value
        scene.collection.objects.link(sun)
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    cam.data.lens = 50
    cam.location = (3.3, -4.1, 2.3)
    aim = bpy.data.objects.new("Aim", None)
    aim.location = (0.0, 0.1, 0.45)
    scene.collection.objects.link(aim)
    cam.constraints.new("TRACK_TO").target = aim
    scene.collection.objects.link(cam)
    scene.camera = cam
    return scene


def build(path):
    """An object carrying still_life of the file, its material Toon built with it."""
    groups = {g.name: g for g in build_source(path.read_text(encoding="utf-8"), filename=path.name, load=loader)}
    obj = bpy.data.objects.new("Still life", bpy.data.meshes.new("Still life"))
    bpy.context.scene.collection.objects.link(obj)
    obj.modifiers.new("Still life", "NODES").node_group = groups["still_life"]
    return obj


def render(step):
    OUT.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.filepath = str(OUT / f"toon-lights-{step}.png")
    bpy.ops.render.render(write_still=True)
    print(f"rendered {scene.render.filepath}")
    return scene.render.filepath


def check_round_trip(path):
    """The material Toon of step 4 reads back to a text that builds the same material again."""
    empty_scene(LIGHTS["step4"])
    build(path)
    text, warnings = export_tree(bpy.data.materials["Toon"].node_tree)
    assert not warnings, warnings
    again, _ = export_tree(build_source(text, filename="toon_material.bn")[-1])
    assert again == text, "Toon does not read back the same"
    print("round trip Toon: ok")


def same_picture(a, b):
    """Step 5 calls the module where step 4 wrote it out: the two pictures match."""
    first, second = bpy.data.images.load(a), bpy.data.images.load(b)
    worst = max(abs(x - y) for x, y in zip(first.pixels[:], second.pixels[:]))
    assert worst < 2 / 255, f"step 5 differs from step 4 by {worst * 255:.1f} levels"
    print(f"step 5 renders step 4: ok (largest difference {worst * 255:.1f} levels)")


def main():
    only = args()
    pictures = {}
    steps = sorted(HERE.glob("step*.bn"))
    for path in steps:
        step = path.stem.split("_")[0]
        if only and only != step:
            continue
        empty_scene(LIGHTS[step])
        build(path)
        pictures[step] = render(step)
    if "step4" in pictures and "step5" in pictures:
        same_picture(pictures["step4"], pictures["step5"])
    if not only or only == "round-trip":
        check_round_trip(steps[3])


main()
