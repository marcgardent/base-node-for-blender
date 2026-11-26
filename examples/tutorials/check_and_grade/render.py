"""Render the plate of the check and grade tutorial once, then composite each step from it.

  blender -b --factory-startup --python-exit-code 1 --python examples/tutorials/check_and_grade/render.py
  blender -b --factory-startup --python-exit-code 1 --python examples/tutorials/check_and_grade/render.py -- --only step3
  blender -b --factory-startup --python-exit-code 1 --python examples/tutorials/check_and_grade/render.py -- --fresh

The plate is a still life on a shadow catcher: a terracotta ball, a chrome ring, a crate and a glowing
bulb, lit by a cool sun, a little under. Its film is transparent: the objects and their shadow are in
its alpha, there is no background. Cycles renders it once, 960 × 720, to an EXR kept in the temp
folder; it is rendered again when this script is newer than it, or with --fresh.

Every step*.bn of this folder is then built, check_and_grade as the compositor. Its Render Layers
nodes are swapped for Image nodes of the EXR, whose Image and Alpha are the same, and an empty scene
renders the composite to site/images/tutorials/check-and-grade-<step>.png, at the size of what the
step delivers: no step renders the 3D scene again. A step that does not build stops the script.
Step 7 also renders its soft_clip_heat, check-and-grade-step7-heat.png.

The numbers the page gives are checked on float renders of the steps (EXR, before the view
transform): the bars of step 1 are 0 and 0.75; the plate has values above 1, on under 1 % of its
pixels; the delivery of steps 6 and 7 is between 0 and 1; the soft clip of step 7 changes under 2 %
of the pixels. Last, the graphs of the last step read back to their text, and those that do not
read the render go through the regression tests' round trip (tests/test_libraries.py).
"""

import math
import re
import sys
import tempfile
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "site" / "images" / "tutorials"
STDLIB = ROOT / "stdlib"
TEMP = Path(tempfile.gettempdir()) / "base-node-check-and-grade"
PLATE = TEMP / "plate.exr"
sys.path.insert(0, str(ROOT / "addon" / "tests"))
import test_libraries  # noqa: E402  (loads the extension as `base_node`)

from base_node.host import build_source, export_tree  # noqa: E402

SAMPLES = 64
WIDTH, HEIGHT = 960, 720
DELIVERY = (960, 540)  # what steps 5 on deliver: the plate reformatted to 16:9
GRAPH = "check_and_grade"


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    return only, "--fresh" in argv


def loader(name, _caller):
    path = STDLIB / f"{name}.bn"
    return path.read_text(encoding="utf-8"), str(path)


def use_gpu(scene):
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            for device in prefs.devices:
                device.use = True
            scene.cycles.device = "GPU"
            return
        except TypeError:
            continue


def material(name, color, roughness, metallic=0.0, emission=None, strength=0.0):
    m = bpy.data.materials.new(name)
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        bsdf.inputs["Emission Strength"].default_value = strength
    return m


def primitive(op, mat, location, scale=(1.0, 1.0, 1.0), rotation=(0.0, 0.0, 0.0), smooth=False, **kw):
    """An object of one of bpy.ops.mesh's primitives, with its material."""
    op(location=location, rotation=rotation, **kw)
    obj = bpy.context.active_object
    obj.scale = scale
    obj.data.materials.append(mat)
    if smooth:
        for poly in obj.data.polygons:
            poly.use_smooth = True
    return obj


def plate_scene():
    """The 3D scene: a still life on a shadow catcher, under a cool sun, its film transparent."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "Scene"
    scene.render.engine = "CYCLES"
    use_gpu(scene)
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = WIDTH, HEIGHT
    scene.render.film_transparent = True
    scene.view_settings.view_transform = "Standard"

    ground = primitive(bpy.ops.mesh.primitive_plane_add, material("Ground", (0.5, 0.5, 0.5), 0.8),
                       (0.0, 0.0, 0.0), size=40.0)
    ground.is_shadow_catcher = True
    primitive(bpy.ops.mesh.primitive_uv_sphere_add, material("Terracotta", (0.6, 0.22, 0.1), 0.45),
              (-1.35, 0.35, 0.6), scale=(0.6, 0.6, 0.6), smooth=True, segments=96, ring_count=48)
    primitive(bpy.ops.mesh.primitive_torus_add, material("Chrome", (0.9, 0.9, 0.92), 0.08, metallic=1.0),
              (0.05, 0.8, 0.72), rotation=(math.radians(90.0), 0.0, math.radians(15.0)), smooth=True,
              major_radius=0.55, minor_radius=0.17, major_segments=128, minor_segments=48)
    primitive(bpy.ops.mesh.primitive_cube_add, material("Wood", (0.45, 0.28, 0.14), 0.6),
              (1.35, 0.1, 0.4), rotation=(0.0, 0.0, math.radians(25.0)), size=0.8)
    primitive(bpy.ops.mesh.primitive_uv_sphere_add,
              material("Bulb", (1.0, 0.8, 0.5), 0.3, emission=(1.0, 0.7, 0.4), strength=12.0),
              (1.35, 0.1, 0.95), scale=(0.15, 0.15, 0.15), smooth=True, segments=48, ring_count=24)

    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy, sun.color, sun.angle = 0.6, (0.75, 0.87, 1.0), math.radians(3.0)
    sun_obj = bpy.data.objects.new("Sun", sun)
    towards = Vector((-0.7, -0.45, 0.6)).normalized()  # from the objects to the sun: left, front, up
    sun_obj.rotation_euler = Vector((0.0, 0.0, 1.0)).rotation_difference(towards).to_euler()
    scene.collection.objects.link(sun_obj)
    world = bpy.data.worlds.new("Sky")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.3, 0.36, 0.45, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.15
    scene.world = world

    data = bpy.data.cameras.new("Camera")
    data.lens = 45
    cam = bpy.data.objects.new("Camera", data)
    cam.location = (0.0, -6.0, 1.4)
    aim = bpy.data.objects.new("Aim", None)
    aim.location = (0.0, 0.35, 0.55)
    scene.collection.objects.link(aim)
    cam.constraints.new("TRACK_TO").target = aim
    scene.collection.objects.link(cam)
    scene.camera = cam
    return scene


def render_plate(scene, fresh):
    if PLATE.exists() and not fresh and PLATE.stat().st_mtime > Path(__file__).stat().st_mtime:
        print(f"plate: {PLATE}, kept")
        return
    TEMP.mkdir(parents=True, exist_ok=True)
    settings = scene.render.image_settings
    settings.file_format = "OPEN_EXR"
    settings.color_mode = "RGBA"
    settings.color_depth = "32"
    scene.render.filepath = str(PLATE)
    bpy.ops.render.render(write_still=True)
    print(f"plate: {PLATE}, rendered")


def from_plate(groups):
    """Every Render Layers of the groups swapped for the plate: an Image node, whose Image and Alpha
    are the render's."""
    image = bpy.data.images.get(PLATE.name) or bpy.data.images.load(str(PLATE))
    for tree in groups:
        for node in [n for n in tree.nodes if n.bl_idname == "CompositorNodeRLayers"]:
            plate = tree.nodes.new("CompositorNodeImage")
            plate.image = image
            plate.location = node.location
            outputs = {o.name: o for o in plate.outputs}
            for link in [l for l in tree.links if l.from_node == node]:
                tree.links.new(outputs[link.from_socket.name], link.to_socket)
            tree.nodes.remove(node)


def build(path):
    """The step's groups, built in the plate's scene; check_and_grade among them."""
    source = path.read_text(encoding="utf-8")
    return {g.name: g for g in build_source(source, filename=path.name, load=loader)}


def composite(tree, size, filepath, exr=False):
    """Render the tree on the plate, in a scene with nothing to render, at the size it delivers."""
    comp = bpy.data.scenes.get("Composite")
    if comp is None:
        comp = bpy.data.scenes.new("Composite")
        comp.camera = bpy.data.objects.new("Composite camera", bpy.data.cameras.new("Composite camera"))
        comp.collection.objects.link(comp.camera)
    comp.render.engine = "CYCLES"
    comp.cycles.samples = 1
    comp.cycles.device = "CPU"
    comp.render.resolution_x, comp.render.resolution_y = size
    comp.render.resolution_percentage = 100
    settings = comp.render.image_settings
    if exr:
        settings.file_format, settings.color_mode, settings.color_depth = "OPEN_EXR", "RGBA", "32"
    else:
        settings.file_format, settings.color_mode, settings.color_depth = "PNG", "RGB", "8"
    comp.view_settings.view_transform = "Standard"
    comp.compositing_node_group = tree
    comp.render.filepath = str(filepath)
    bpy.ops.render.render(write_still=True, scene=comp.name)
    print(f"rendered {filepath}")


def pixels(tree, size, name):
    """The float pixels of the tree, RGBA by RGBA, before any view transform."""
    path = TEMP / f"{name}.exr"
    composite(tree, size, path, exr=True)
    image = bpy.data.images.load(str(path), check_existing=False)
    values = list(image.pixels[:])
    bpy.data.images.remove(image)
    return [values[i:i + 4] for i in range(0, len(values), 4)]


def called(group):
    """A tree that calls the group with its inputs at their defaults: the scene's compositor, given the
    group itself, would not take the defaults of its inputs other than images."""
    tree = bpy.data.node_groups.new(f"{group.name} called", "CompositorNodeTree")
    tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    node = tree.nodes.new("CompositorNodeGroup")
    node.node_tree = group
    tree.links.new(node.outputs[0], tree.nodes.new("NodeGroupOutput").inputs[0])
    return tree


def size_of(step):
    return (WIDTH, HEIGHT) if step < "step5" else DELIVERY


def check_numbers(step, groups):
    """The numbers the page gives, read on a float render of the step."""
    if step == "step1":
        # The bars, the top third: each channel 0 or 0.75; rows count from the bottom
        width, height = size_of(step)
        found = pixels(groups[GRAPH], size_of(step), step)
        bars = {round(c, 4) for p in found[(height * 2 // 3 + 2) * width:] for c in p[:3]}
        assert bars == {0.0, 0.75}, f"step 1: the bars hold {sorted(bars)}, not 0 and 0.75"
        print("step 1: the bars are 0 and 0.75")
    if step == "step2":
        plate = bpy.data.images.get(PLATE.name) or bpy.data.images.load(str(PLATE))
        values = plate.pixels[:]
        top = max(max(values[i:i + 3]) for i in range(0, len(values), 4))
        over = sum(1 for i in range(0, len(values), 4) if max(values[i:i + 3]) > 1.0)
        print(f"plate: largest value {top:.2f}, {over} pixels above 1")
        assert top > 1.0 and over < len(values) // 4 // 100, (top, over)
    if step in ("step6", "step7"):
        shot = pixels(called(groups["delivery"]), size_of(step), f"{step} delivery")
        low = min(min(p[:3]) for p in shot)
        high = max(max(p[:3]) for p in shot)
        print(f"{step}: the delivery is between {low:.4f} and {high:.4f}")
        assert low >= 0.0 and high <= 1.0, (step, low, high)
    if step == "step7":
        # The soft clip changes the highlights alone: a few pixels of the frame by more than a
        # thousandth (below its start it gives the value back to the rounding of a float); the heat's
        # red is 3 × 4 × the difference
        heat = pixels(called(groups["soft_clip_heat"]), size_of(step), f"{step} heat")
        touched = sum(1 for p in heat if p[0] > 0.012) / len(heat)
        print(f"step 7: the soft clip changes {touched:.2%} of the pixels")
        assert 0.0 < touched < 0.02, touched


def own_graphs(path):
    """The names of the graphs the file writes itself, not those of the modules it uses."""
    names = re.findall(r'^compositor graph (?:"([^"]+)"|(\w+))\(', path.read_text(encoding="utf-8"), re.M)
    return [quoted or plain for quoted, plain in names]


def reads_render(tree):
    """Whether the tree reads the Render Layers, itself or through a group it calls."""
    return any(n.bl_idname == "CompositorNodeRLayers"
               or (n.bl_idname == "CompositorNodeGroup" and n.node_tree and reads_render(n.node_tree))
               for n in tree.nodes)


def check_round_trip(path):
    """Each graph of the last step reads back to a text that builds the same group again. Those that
    do not read the render go through the regression tests' round trip too: saved to a .blend, read
    as text, built back and applied to a render beside the original. A graph that reads the Render
    Layers would show the render of whichever scene its node points to: its text alone is compared."""
    groups = build(path)
    own = own_graphs(path)
    for name in own:
        text, warnings = export_tree(groups[name])
        assert not warnings, (name, warnings)
        again, _ = export_tree(build_source(text, filename=f"{name}.bn", load=loader)[-1])
        assert again == text, f"{name} does not read back the same"
        print(f"round trip {name}: ok (text)")
    evaluated = [n for n in own if not reads_render(groups[n])]
    blend = Path(tempfile.mkdtemp()) / "check_and_grade.blend"
    bpy.data.libraries.write(str(blend), {groups[n] for n in evaluated})
    records, _ = test_libraries.round_trip(blend, trees=("compositor",))
    for name in evaluated:
        print(f"round trip {name}: {records[name]['status']} (applied to a render)")
    assert all(records[n]["status"] == "ok" for n in evaluated), {n: records[n] for n in evaluated}


def main():
    only, fresh = args()
    steps = sorted(HERE.glob("step*.bn"))
    render_plate(plate_scene(), fresh)
    OUT.mkdir(parents=True, exist_ok=True)
    for path in steps:
        step = path.stem.split("_")[0]
        if only and only != step:
            continue
        groups = build(path)
        from_plate([g for g in groups.values() if g.bl_idname == "CompositorNodeTree"])
        composite(groups[GRAPH], size_of(step), OUT / f"check-and-grade-{step}.png")
        if "soft_clip_heat" in groups:
            composite(called(groups["soft_clip_heat"]), size_of(step), OUT / f"check-and-grade-{step}-heat.png")
        check_numbers(step, groups)
    if not only or only == "round-trip":
        plate_scene()
        check_round_trip(steps[-1])


main()
