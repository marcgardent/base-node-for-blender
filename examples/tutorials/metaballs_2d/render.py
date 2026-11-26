"""Build each step of the 2D metaballs tutorial in Blender and render its picture.

  blender -b --factory-startup --python-exit-code 1 --python examples/tutorials/metaballs_2d/render.py
  blender -b --factory-startup --python-exit-code 1 --python examples/tutorials/metaballs_2d/render.py -- --only step3

Every step*.bn of this folder is built from scratch in an empty scene, under the same orthographic
camera, straight down on the 3 m canvas, at frame FRAME, and rendered with EEVEE to
site/images/tutorials/metaballs-2d-<step>.png. The page shows these files' text: a step that does not
build stops the script.

The curves step plots the shaping functions of the module math the last step uses, as the module
computes them, to metaballs-2d-curves.svg. The loop step renders the last step over its whole loop,
LOOP frames, and encodes them as the animated metaballs-2d.webp (examples/encode_webp.py, with the
system Python, which has Pillow). Then the groups and the material of the last step go through the
regression tests' round trip (tests/test_libraries.py).
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

SIZE = 800  # px, of the square stills
LOOP = 96  # frames of the last step's loop, its `beat`
FRAME = 30  # the frame of the stills
WEBP = 400  # px, of the animated loop


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return argv[argv.index("--only") + 1] if "--only" in argv else None


def empty_scene(size=SIZE):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 16
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    # The canvas emits the colours the graph computes: shown as they are, with no tone curve
    scene.view_settings.view_transform = "Standard"
    scene.render.dither_intensity = 0.0
    data = bpy.data.cameras.new("Camera")
    data.type = "ORTHO"
    data.ortho_scale = 3.0  # the canvas, edge to edge
    cam = bpy.data.objects.new("Camera", data)
    cam.location = (0.0, 0.0, 5.0)
    scene.collection.objects.link(cam)
    scene.camera = cam
    scene.frame_set(FRAME)
    return scene


def build(path):
    source = path.read_text(encoding="utf-8")
    groups = {g.name: g for g in build_source(source, filename=path.name)}
    obj = bpy.data.objects.new("Metaballs", bpy.data.meshes.new("Metaballs"))
    bpy.context.scene.collection.objects.link(obj)
    obj.modifiers.new("Metaballs", "NODES").node_group = groups["metaballs"]
    return obj


def render(name):
    OUT.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.filepath = str(OUT / f"metaballs-2d-{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"rendered {scene.render.filepath}")


PLOT = """
use math (bounce, elastic, impulse, recoil)

geometry graph curve(kind: Int) -> Geometry {
  x = Position().x
  y = IndexSwitch(kind, bounce(x), elastic(x), recoil(x), impulse(x, stiffness: 8.0)).output
  return MeshLine(count: 201, offset: (0.005, 0.0, 0.0))
    |> SetPosition(position: CombineXYZ(x: x, y: y, z: kind))
}

geometry graph plot() -> Geometry {
  return JoinGeometry(curve(0), curve(1), curve(2), curve(3))
}

geometry graph melt() -> Geometry {
  return MeshLine(count: 1, start_location: CombineXYZ(x: smooth_min(0.0, 0.0, 0.3)))
}
"""

CURVES = [  # kind of plot(), name, colour
    (0, "bounce(t)", "#79c0ff"),
    (1, "elastic(t)", "#f2cc60"),
    (2, "recoil(t)", "#ff7b72"),
    (3, "impulse(t, stiffness: 8.0)", "#7ee787"),
]


def evaluated(group):
    """The vertices of the mesh `group` makes, evaluated on an empty object."""
    obj = bpy.data.objects.new("Probe", bpy.data.meshes.new("Probe"))
    bpy.context.scene.collection.objects.link(obj)
    obj.modifiers.new("Probe", "NODES").node_group = group
    mesh = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    points = [tuple(v.co) for v in mesh.vertices]
    bpy.data.objects.remove(obj)
    return points


def plot_curves():
    """The shaping functions of the module math, as it computes them, in four small plots."""
    empty_scene()
    groups = {g.name: g for g in build_source(PLOT, filename="plot.bn")}
    # smooth_min(a, a, k) = a - k / 6: the most the blob lowers the field, where both balls are as near
    (low, _, _), = evaluated(groups["melt"])
    assert abs(low + 0.3 / 6.0) < 1e-6, low
    print(f"smooth_min(0, 0, 0.3) = {low:.4f}: 0.3 / 6 below the minimum")
    curves = evaluated(groups["plot"])
    w, h, pad, gap = 720, 400, 36, 24
    pw, ph = (w - 2 * pad - gap) / 2, (h - 2 * pad - gap) / 2
    lo, hi = -0.2, 1.45
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        'font-family="ui-monospace, Menlo, Consolas, monospace" font-size="12">',
        f'<rect width="{w}" height="{h}" rx="6" fill="#161920"/>',
    ]
    for n, (kind, name, colour) in enumerate(CURVES):
        x0 = pad + (n % 2) * (pw + gap)
        y0 = pad / 2 + (n // 2) * (ph + gap + pad / 2)

        def at(x, y):
            return x0 + x * pw, y0 + (hi - y) / (hi - lo) * ph

        for level in (0.0, 1.0):
            _, y = at(0.0, level)
            parts.append(f'<line x1="{x0:.1f}" x2="{x0 + pw:.1f}" y1="{y:.1f}" y2="{y:.1f}" stroke="#262b36"/>')
            parts.append(f'<text x="{x0 - 6:.1f}" y="{y + 4:.1f}" fill="#939ab0" text-anchor="end">{level:.0f}</text>')
        for t in (0.0, 0.5, 1.0):
            x, _ = at(t, lo)
            parts.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{y0:.1f}" y2="{y0 + ph:.1f}" stroke="#262b36"/>')
            parts.append(f'<text x="{x:.1f}" y="{y0 + ph + 14:.1f}" fill="#939ab0" text-anchor="middle">{t:g}</text>')
        points = sorted((x, y, z) for x, y, z in curves if round(z) == kind)
        assert len(points) == 201, len(points)
        path = " ".join(("M" if i == 0 else "L") + "%.1f,%.1f" % at(x, y) for i, (x, y, _) in enumerate(points))
        parts.append(f'<path d="{path}" fill="none" stroke="{colour}" stroke-width="2"/>')
        parts.append(f'<text x="{x0 + pw * 0.75:.1f}" y="{y0 + 14:.1f}" fill="{colour}" text-anchor="middle">{name}</text>')
        top = max(points, key=lambda p: p[1])
        bottom = min(points, key=lambda p: p[1])
        print(f"{name}: highest {top[1]:.3f} at t = {top[0]:.3f}, lowest {bottom[1]:.3f} at t = {bottom[0]:.3f}")
    parts.append("</svg>")
    out = OUT / "metaballs-2d-curves.svg"
    out.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"wrote {out}")


def render_loop(path):
    """The last step over its whole loop, encoded as the animated metaballs-2d.webp."""
    scene = empty_scene(WEBP)
    build(path)
    with tempfile.TemporaryDirectory() as frames:
        # Frame LOOP + 1 is frame 1 again: the loop has no seam
        for frame in range(1, LOOP + 1):
            scene.frame_set(frame)
            scene.render.filepath = str(Path(frames) / f"frame_{frame:04d}.png")
            bpy.ops.render.render(write_still=True)
        subprocess.run(["python3", "-I", str(ROOT / "examples" / "encode_webp.py"), frames,
                        str(OUT / "metaballs-2d.webp"), "24", "70"], check=True)


def check_round_trip(path):
    """The regression tests' round trip, for the groups and the material of the last step.

    It builds the Geometry Nodes groups again before the materials, so `canvas`, which sets the material
    Canvas of the same text, and `metaballs`, which calls it, cannot build there: their texts are checked
    here instead, with the material in the file.
    """
    empty_scene()
    build(path)
    for name in ("canvas", "metaballs"):
        text, warnings = export_tree(bpy.data.node_groups[name])
        assert not warnings, warnings
        again, _ = export_tree(build_source(text, filename=f"{name}.bn")[-1])
        assert again == text, f"{name} does not read back the same"
        print(f"round trip {name}: ok (with its material)")

    blend = Path(tempfile.mkdtemp()) / "metaballs_2d.blend"
    bpy.data.libraries.write(str(blend), set(bpy.data.node_groups) | set(bpy.data.materials))
    records, _ = test_libraries.round_trip(blend, trees=("geometry", "shader", "material"))
    records.pop("canvas")
    records.pop("metaballs")
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
        empty_scene()
        build(path)
        render(step)
    if not only or only == "curves":
        plot_curves()
    if not only or only == "loop":
        render_loop(steps[-1])
    if not only or only == "round-trip":
        check_round_trip(steps[-1])


main()
