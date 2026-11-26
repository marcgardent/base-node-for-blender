"""Build each step of the shaping motion tutorial in Blender and render its picture.

  blender -b --factory-startup --python-exit-code 1 --python examples/tutorials/shaping_motion/render.py
  blender -b --factory-startup --python-exit-code 1 --python examples/tutorials/shaping_motion/render.py -- --only step4

Every step*.bn of this folder is built from scratch in an empty scene, its shaping_motion on an
object, with the module math of this repository's stdlib/, and rendered with EEVEE to
site/images/tutorials/shaping-motion-<step>.png. The page shows these files' text: a step that does
not build stops the script.

Step 4 is checked column by column: the height Blender gives each column is the curve of
curves.py, the formulas of stdlib/math.bn the page's plots are drawn from. Step 5 moves: one loop
of it, PERIOD seconds, is rendered frame by frame to the looping animated WebP
shaping-motion-step5.webp, the hero of the page; its PNG is frame STILL of the loop. The loop is
checked to join up: at its last frame the ripples have died away. Then the groups and the material
of the last step go through the regression tests' round trip (tests/test_libraries.py).
"""

import math
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "site" / "images" / "tutorials"
STDLIB = ROOT / "stdlib"
sys.path.insert(0, str(ROOT / "addon" / "tests"))
sys.path.insert(0, str(HERE))
import test_libraries  # noqa: E402  (loads the extension as `base_node`)
import curves  # noqa: E402

from base_node.host import build_source, export_tree  # noqa: E402

SIZE = (800, 560)  # the stills
MOVIE = (640, 448)  # the animation, the same shape
SAMPLES = 32
FPS = 24
PERIOD = 2.5  # seconds: the default period of step 5
STILL = 30  # the frame of step 5's PNG: halfway through the loop, the ripples halfway out
# location, target, lens
GRID = ((4.7, -5.5, 3.9), (0.0, 0.1, 0.1), 46)
GALLERY = ((-0.3, -10.0, 8.8), (-0.3, -0.2, 0.0), 56)
CAMERAS = {"step4": GALLERY}


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return argv[argv.index("--only") + 1] if "--only" in argv else None


def loader(name, _caller):
    path = STDLIB / f"{name}.bn"
    return path.read_text(encoding="utf-8"), str(path)


def empty_scene(camera, size=SIZE):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = SAMPLES
    scene.eevee.use_shadows = True
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
    scene.render.fps = FPS
    world = bpy.data.worlds.new("Sky")
    world.use_nodes = True
    background = world.node_tree.nodes["Background"]
    background.inputs["Color"].default_value = (0.09, 0.1, 0.13, 1.0)
    background.inputs["Strength"].default_value = 1.0
    scene.world = world
    # A dark floor under everything, to catch the shadows
    bpy.ops.mesh.primitive_plane_add(size=40.0, location=(0.0, 0.0, -0.001))
    floor = bpy.context.object
    material = bpy.data.materials.new("Floor")
    material.use_nodes = True
    bsdf = material.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.05, 0.055, 0.07, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.9
    floor.data.materials.append(material)
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3.5
    sun.data.angle = math.radians(3.0)
    sun.rotation_euler = Vector((-0.55, 0.7, -0.45)).normalized().to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(sun)
    location, aim, lens = camera
    target = bpy.data.objects.new("Target", None)
    target.location = aim
    scene.collection.objects.link(target)
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    cam.data.lens = lens
    cam.location = location
    cam.constraints.new("TRACK_TO").target = target
    scene.collection.objects.link(cam)
    scene.camera = cam
    return scene


def build(path):
    source = path.read_text(encoding="utf-8")
    groups = {g.name: g for g in build_source(source, filename=path.name, load=loader)}
    obj = bpy.data.objects.new("Shaping motion", bpy.data.meshes.new("Shaping motion"))
    bpy.context.scene.collection.objects.link(obj)
    obj.modifiers.new("Shaping motion", "NODES").node_group = groups["shaping_motion"]
    return obj


def render(name):
    OUT.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.filepath = str(OUT / f"shaping-motion-{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"rendered {scene.render.filepath}")


def vertices(obj):
    mesh = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    return [v.co.copy() for v in mesh.vertices]


def check_gallery(obj):
    """Each row of step 4 is its curve: the top of column i is f(t) × 0.4 + 0.05, t = i / 39."""
    points = [p for p in vertices(obj) if p.x > -2.1]  # not the names, at the left
    rows = defaultdict(list)
    for p in points:
        rows[round(p.y / 0.7 + 4.5)].append(p)
    worst = 0.0
    assert sorted(rows) == list(range(len(curves.GALLERY))), sorted(rows)
    for index, (name, f) in enumerate(curves.GALLERY):
        columns = defaultdict(list)
        for p in rows[index]:
            columns[round((p.x + 2.0) / (4.0 / 39.0))].append(p)
        assert sorted(columns) == list(range(40)), (name, sorted(columns))
        for i, corners in sorted(columns.items()):
            # t as Blender computes it, from the column's own x: at the right end, x is a hair short of 2 m
            # in single precision, t a hair short of 1, and square, 1 on [0, 0.5), is already 0 there
            x = sum(p.x for p in corners) / len(corners)
            top = max(p.z for p in corners)
            want = f(x / 4.0 + 0.5) * 0.4 + 0.05
            worst = max(worst, abs(top - want))
            assert abs(top - want) < 1e-3, f"{name}: column {i} is {top:.4f} high, the curve says {want:.4f}"
    print(f"step 4 follows curves.py: ok ({len(curves.GALLERY)} rows of 40 columns, largest difference {worst:.1e} m)")


def check_loop(obj):
    """The loop joins up: frame 0 is flat water, and so, nearly, is the last frame before it again."""
    scene = bpy.context.scene
    frames = round(PERIOD * FPS)
    for frame, tolerance in ((0, 1e-4), (frames - 1, 0.01)):
        scene.frame_set(frame)
        tops = [p.z for p in vertices(obj) if 0.01 < p.z < 1.0]  # not the bottoms, nor the drop above
        off = max(abs(z - 0.45) for z in tops)
        assert off < tolerance, f"frame {frame}: a column is {off:.4f} m off the water"
        print(f"frame {frame}: the columns are within {off:.4f} m of the water")


def animate(obj, step):
    """One loop of step 5, frame by frame, as a looping animated WebP; frame STILL as the PNG."""
    scene = bpy.context.scene
    frames = Path(tempfile.mkdtemp(prefix="shaping_motion_"))
    count = round(PERIOD * FPS)
    for i in range(count):
        scene.frame_set(i)
        scene.render.filepath = str(frames / f"frame_{i:04d}.png")
        bpy.ops.render.render(write_still=True)
    OUT.mkdir(parents=True, exist_ok=True)
    webp = OUT / f"shaping-motion-{step}.webp"
    subprocess.run(["python3", "-I", str(ROOT / "examples" / "encode_webp.py"), str(frames), str(webp), str(FPS), "80"],
                   check=True)
    shutil.rmtree(frames)
    print(f"rendered {webp}, {webp.stat().st_size} bytes")


def check_round_trip(path):
    """The regression tests' round trip, for the groups and the material of the last step.

    It builds the Geometry Nodes groups again before the materials, so the groups that set the
    material Painted of the same text cannot build there: their text is checked here instead.
    """
    empty_scene(GRID)
    build(path)
    setting = sorted(g.name for g in bpy.data.node_groups
                     if any(n.bl_idname == "GeometryNodeSetMaterial" for n in g.nodes))
    for name in setting:
        text, warnings = export_tree(bpy.data.node_groups[name])
        assert not warnings, warnings
        again, _ = export_tree(build_source(text, filename=f"{name}.bn")[-1])
        assert again == text, f"{name} does not read back the same"
        print(f"round trip {name}: ok (with its material)")

    blend = Path(tempfile.mkdtemp()) / "shaping_motion.blend"
    bpy.data.libraries.write(str(blend), set(bpy.data.node_groups) | {bpy.data.materials["Painted"]})
    records, _ = test_libraries.round_trip(blend, trees=("geometry", "shader", "material"))
    for name in setting:
        records.pop(name)
    for name, record in sorted(records.items()):
        print(f"round trip {name}: {record['status']}")
    assert records and all(r["status"] == "ok" for r in records.values()), records


def main():
    only = args()
    steps = sorted(HERE.glob("step*.bn"))
    for path in steps:
        step = path.stem.split("_")[0]
        if only and only != step:
            continue
        camera = CAMERAS.get(step, GRID)
        if step == "step5":
            empty_scene(camera, MOVIE)
            obj = build(path)
            check_loop(obj)
            animate(obj, step)
            empty_scene(camera)
            build(path)
            bpy.context.scene.frame_set(STILL)
            render(step)
            continue
        empty_scene(camera)
        obj = build(path)
        if step == "step4":
            check_gallery(obj)
        render(step)
    if not only or only == "round-trip":
        check_round_trip(steps[-1])


main()
