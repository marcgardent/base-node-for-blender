"""The thumbnails of the standard library's assets: a picture of what a group makes, else a card.

Run in Blender on the .blend tools/stdlib_blend.py writes, in two steps around tools/stdlib_cards.py:

    blender --background --factory-startup <file.blend> --python tools/stdlib_previews.py -- render <dir>
    python3 tools/stdlib_cards.py <dir>
    blender --background --factory-startup <file.blend> --python tools/stdlib_previews.py -- apply <dir>

`render` writes <dir>/groups.json, what a card says of each asset group (its name, kind, module,
section, sockets), and renders into <dir>/render/ the groups that make a picture:

- a geometry group with a Geometry output: its geometry, its geometry inputs given a star curve,
  curves and edges drawn as tubes and points as spheres, seen from above when it is flat;
- a geometry group of one Float to one Float (a shaping curve of math): its curve, x from 0 to 1,
  unless it is a straight line;
- a geometry group of a Vector to one Float (a signed distance, a noise): its field on the plane;
- a compositor group with an image output (a Color, or a Float, a mask): applied to two test pictures
  of site/images, the first with a hole in its alpha;
- a shader group with a Shader output: a sphere under two lights, by EEVEE.

A picture nearly uniform (an empty geometry, a constant colour) is dropped: the card says more.
stdlib_cards.py writes <dir>/final/, a picture or a card for each group; `apply` puts them in the
previews of the groups and saves the .blend, from which `blender -c asset_listing generate` writes
the thumbnails of the remote library.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
SIZE = 256  # the side of a thumbnail
KINDS = {"GeometryNodeTree": "geometry", "ShaderNodeTree": "shader", "CompositorNodeTree": "compositor"}
COLOR = (0.05, 0.62, 0.52, 1.0)  # the geometry's colour
PICTURES = ("showcase-erosion.png", "showcase-tuple-tiles.png")  # the compositor's test pictures


def asset_groups():
    return [g for g in bpy.data.node_groups if g.asset_data is not None]


def sockets(g, io):
    return [(i.name, i.socket_type.removeprefix("NodeSocket")) for i in g.interface.items_tree
            if i.item_type == "SOCKET" and i.in_out == io]


def describe(groups, fonts: str) -> dict:
    catalogs = {}
    cats = Path(bpy.data.filepath).with_name("blender_assets.cats.txt")
    for line in cats.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith(("#", "VERSION")):
            cid, path, _ = line.split(":", 2)
            catalogs[cid] = path.split("/")
    out = []
    for i, g in enumerate(groups):
        path = catalogs.get(g.asset_data.catalog_id, [])
        out.append({
            "file": f"{i:03d}.png",
            "name": g.name,
            "kind": KINDS[g.bl_idname],
            "module": path[1] if len(path) > 1 else "",
            "section": path[2] if len(path) > 2 else "",
            "description": g.description,
            "inputs": sockets(g, "INPUT"),
            "outputs": sockets(g, "OUTPUT"),
        })
    return {"blender": bpy.app.version_string, "fonts": fonts, "groups": out}


# ---- The scene ----

def scene_setup():
    scene = bpy.context.scene
    for o in list(scene.collection.objects):
        o.hide_render = True
    r = scene.render
    r.resolution_x = r.resolution_y = SIZE
    r.resolution_percentage = 100
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    scene.cycles.device = "CPU"
    world = bpy.data.worlds.new("preview")
    world.color = (0.05, 0.05, 0.05)
    scene.world = world

    camera = bpy.data.objects.new("preview camera", bpy.data.cameras.new("preview camera"))
    scene.collection.objects.link(camera)
    scene.camera = camera
    sun = bpy.data.objects.new("preview sun", bpy.data.lights.new("preview sun", "SUN"))
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(35), math.radians(10), math.radians(30))
    scene.collection.objects.link(sun)
    fill = bpy.data.objects.new("preview fill", bpy.data.lights.new("preview fill", "POINT"))
    fill.data.energy = 400.0
    fill.location = (-3.0, -2.0, 2.5)
    scene.collection.objects.link(fill)
    return scene, camera


REFERENCES: list = []  # the pictures of the inputs alone: a group that gives one of them back shows nothing


def render_to(scene, path: Path, compositing: bool) -> Path | None:
    scene.render.use_compositing = compositing
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return path if worth_it(path) else None


def pixels(path: Path):
    img = bpy.data.images.load(str(path))
    try:
        return np.array(img.pixels[:], dtype=np.float32).reshape(-1, 4)
    finally:
        bpy.data.images.remove(img)


def reference(scene, path: Path, compositing: bool) -> None:
    scene.render.use_compositing = compositing
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    REFERENCES.append(pixels(path))
    path.unlink()


def worth_it(path: Path) -> bool:
    """Whether a picture shows something: not nearly one colour, not nearly empty, not an input as it is."""
    if not path.exists():
        return False
    px = pixels(path)
    if any(ref.shape == px.shape and np.abs(ref - px).mean() < 0.004 for ref in REFERENCES):
        path.unlink()
        return False
    shown = px[:, 3] > 0.02
    if shown.mean() < 0.01:
        path.unlink()
        return False
    luma = px[shown, :3] @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    if px[:, 3].std() < 0.01 and luma.std() < 0.01:
        path.unlink()
        return False
    return True


# ---- Geometry ----

def geometry_rig(scene):
    """An object whose modifier shows a group's geometry, and the nodes to set for each group."""
    mat = bpy.data.materials.new("preview geometry")
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = COLOR
    mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.45

    t = bpy.data.node_groups.new("preview geometry", "GeometryNodeTree")
    t.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n, link = t.nodes, t.links.new
    star = n.new("GeometryNodeCurveStar")
    star.inputs["Points"].default_value = 7
    group = n.new("GeometryNodeGroup")
    radius = n.new("ShaderNodeValue")
    realize = n.new("GeometryNodeRealizeInstances")
    parts = n.new("GeometryNodeSeparateComponents")
    join = n.new("GeometryNodeJoinGeometry")
    circle = n.new("GeometryNodeCurvePrimitiveCircle")
    circle.inputs["Resolution"].default_value = 8
    link(radius.outputs[0], circle.inputs["Radius"])
    edges = n.new("GeometryNodeMeshToCurve")
    tube_edges = n.new("GeometryNodeCurveToMesh")
    tube_curves = n.new("GeometryNodeCurveToMesh")
    ball = n.new("GeometryNodeMeshIcoSphere")
    ball.inputs["Subdivisions"].default_value = 2
    scale = n.new("ShaderNodeMath")
    scale.operation = "MULTIPLY"
    scale.inputs[1].default_value = 1.8
    link(radius.outputs[0], scale.inputs[0])
    link(scale.outputs[0], ball.inputs["Radius"])
    on_points = n.new("GeometryNodeInstanceOnPoints")
    realize_points = n.new("GeometryNodeRealizeInstances")
    set_mat = n.new("GeometryNodeSetMaterial")
    set_mat.inputs["Material"].default_value = mat
    out = n.new("NodeGroupOutput")

    link(realize.outputs[0], parts.inputs[0])
    link(parts.outputs["Mesh"], join.inputs[0])
    link(parts.outputs["Mesh"], edges.inputs[0])
    link(edges.outputs[0], tube_edges.inputs["Curve"])
    link(circle.outputs[0], tube_edges.inputs["Profile Curve"])
    link(tube_edges.outputs[0], join.inputs[0])
    link(parts.outputs["Curve"], tube_curves.inputs["Curve"])
    link(circle.outputs[0], tube_curves.inputs["Profile Curve"])
    link(tube_curves.outputs[0], join.inputs[0])
    link(parts.outputs["Point Cloud"], on_points.inputs["Points"])
    link(ball.outputs["Mesh"], on_points.inputs["Instance"])
    link(on_points.outputs[0], realize_points.inputs[0])
    link(realize_points.outputs[0], join.inputs[0])
    link(join.outputs[0], set_mat.inputs["Geometry"])
    link(set_mat.outputs[0], out.inputs[0])

    obj = bpy.data.objects.new("preview geometry", bpy.data.meshes.new("preview geometry"))
    scene.collection.objects.link(obj)
    obj.modifiers.new("preview", "NODES").node_group = t
    return obj, t, group, star, radius, realize


def bounds(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = obj.evaluated_get(dg)
    mesh = ev.to_mesh()
    try:
        if not len(mesh.vertices):
            return None
        co = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        return Vector(co.min(axis=0)), Vector(co.max(axis=0))
    finally:
        ev.to_mesh_clear()


def is_flat(lo, hi) -> bool:
    size = hi - lo
    return size.z < 0.02 * max(size.x, size.y, 1e-6)


def frame(camera, lo, hi, flat=None):
    """Frame the box: from above when it is flat (tubes and spheres drawn on it aside)."""
    size = hi - lo
    center = (lo + hi) / 2
    flat = is_flat(lo, hi) if flat is None else flat
    cam = camera.data
    if flat:
        cam.type = "ORTHO"
        cam.ortho_scale = max(size.x, size.y) * 1.15 or 1.0
        camera.location = (center.x, center.y, hi.z + 10.0)
        camera.rotation_euler = (0.0, 0.0, 0.0)
    else:
        cam.type = "PERSP"
        cam.lens = 50
        radius = max(size.length / 2, 1e-3)
        direction = Vector((1.0, -1.2, 0.9)).normalized()
        distance = radius / math.sin(cam.angle / 2) * 1.02
        camera.location = center + direction * distance
        camera.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    cam.clip_start = 0.001
    cam.clip_end = 1e5


def render_geometry(scene, camera, rig, g, path):
    obj, t, group, star, radius, realize = rig
    for link in [lk for lk in t.links if lk.from_node in (star, group) or lk.to_node == group]:
        t.links.remove(link)
    group.node_tree = g
    out = next((s for s in group.outputs if s.type == "GEOMETRY"), None)
    if out is None:
        return None
    for s in group.inputs:
        if s.type == "GEOMETRY":
            t.links.new(star.outputs[0], s)
    t.links.new(out, realize.inputs[0])
    return show_geometry(scene, camera, rig, path)


def show_geometry(scene, camera, rig, path, keep=True):
    obj, t, group, star, radius, realize = rig
    radius.outputs[0].default_value = 0.0
    b = bounds(obj)
    if b is None:
        return None
    lo, hi = b
    flat = is_flat(lo, hi)
    radius.outputs[0].default_value = max((hi - lo).length * 0.006, 1e-4)
    lo, hi = bounds(obj) or b
    frame(camera, lo, hi, flat)
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 16
    scene.render.film_transparent = True
    obj.hide_render = False
    try:
        if not keep:
            return reference(scene, path, compositing=False)
        return render_to(scene, path, compositing=False)
    finally:
        obj.hide_render = True


def geometry_references(scene, camera, rig, folder):
    """The star the geometry inputs are given, drawn as a group that gives it back would be."""
    obj, t, group, star, radius, realize = rig
    t.links.new(star.outputs[0], realize.inputs[0])
    show_geometry(scene, camera, rig, folder / "reference.png", keep=False)
    t.links.remove(realize.inputs[0].links[0])


def plot_rig(scene):
    """The curve of a function of one Float: x from 0 to 1, y its value, as a tube seen from above."""
    t = bpy.data.node_groups.new("preview plot", "GeometryNodeTree")
    t.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n, link = t.nodes, t.links.new
    line = n.new("GeometryNodeMeshLine")
    line.inputs["Count"].default_value = 256
    line.inputs["Offset"].default_value = (1.0 / 255, 0.0, 0.0)
    xyz = n.new("ShaderNodeSeparateXYZ")
    link(n.new("GeometryNodeInputPosition").outputs[0], xyz.inputs[0])
    group = n.new("GeometryNodeGroup")
    point = n.new("ShaderNodeCombineXYZ")
    link(xyz.outputs["X"], point.inputs["X"])
    move = n.new("GeometryNodeSetPosition")
    link(line.outputs[0], move.inputs["Geometry"])
    link(point.outputs[0], move.inputs["Position"])
    curve = n.new("GeometryNodeMeshToCurve")
    link(move.outputs[0], curve.inputs[0])
    out = n.new("NodeGroupOutput")
    link(curve.outputs[0], out.inputs[0])
    return t, group, xyz, point


def straight(obj) -> bool:
    """Whether the evaluated geometry lies on one straight line."""
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = obj.evaluated_get(dg)
    mesh = ev.to_mesh()
    try:
        co = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", co)
    finally:
        ev.to_mesh_clear()
    co = co.reshape(-1, 3)[:, :2]
    if len(co) < 3:
        return True
    a, b = co[co[:, 0].argmin()], co[co[:, 0].argmax()]
    chord = b - a
    length = float(np.hypot(*chord)) or 1e-9
    off = np.abs((co[:, 0] - a[0]) * chord[1] - (co[:, 1] - a[1]) * chord[0]) / length
    return float(off.max()) < 0.01 * max(length, float(np.ptp(co[:, 1])))


def render_plot(scene, camera, rig, plot, g, path):
    """A function of one Float to a Float: its curve, drawn by the geometry rig."""
    t, group, xyz, point = plot
    group.node_tree = g
    inputs = [s for s in group.inputs]
    out = next((s for s in group.outputs if s.type == "VALUE"), None)
    if out is None or not inputs or inputs[0].type != "VALUE" or len(group.outputs) != 1:
        return None
    for link in list(t.links):
        if link.to_node == group or link.from_node == group:
            t.links.remove(link)
    t.links.new(xyz.outputs["X"], inputs[0])
    t.links.new(out, point.inputs["Y"])
    obj, gt, ggroup, star, radius, realize = rig
    for link in list(realize.inputs[0].links):
        gt.links.remove(link)
    plotted = gt.nodes.get("preview plot") or gt.nodes.new("GeometryNodeGroup")
    plotted.name = "preview plot"
    plotted.node_tree = t
    gt.links.new(plotted.outputs[0], realize.inputs[0])
    try:
        radius.outputs[0].default_value = 0.0  # tubes of no width: the points of the curve alone
        if straight(obj):
            return None  # a line says less than the card
        return show_geometry(scene, camera, rig, path)
    finally:
        for link in list(realize.inputs[0].links):
            gt.links.remove(link)


FIELD = 2.4  # the side of the square a field is drawn on, centered on the origin


def by_id(sockets, identifier):
    return next(x for x in sockets if x.identifier == identifier)


def field_rig(scene):
    """A function of the position to a Float drawn on a grid of the plane z = 0: a signed distance
    with its isolines, inside warm and outside cool (after Inigo Quilez), any other value in grey."""
    mat = bpy.data.materials.new("preview field")
    nt = mat.node_tree
    nt.nodes.clear()
    n, link = nt.nodes, nt.links.new
    attr = n.new("ShaderNodeAttribute")
    attr.attribute_name = "preview_value"
    kind = n.new("ShaderNodeAttribute")
    kind.attribute_name = "preview_sdf"

    def math(op, a, b=None, value=None):
        m = n.new("ShaderNodeMath")
        m.operation = op
        if a is not None:
            link(a, m.inputs[0])
        if b is not None:
            link(b, m.inputs[1])
        elif value is not None:
            m.inputs[1].default_value = value
        return m.outputs[0]

    d = attr.outputs["Fac"]
    ad = math("ABSOLUTE", d)
    inside = math("LESS_THAN", d, value=0.0)
    side = n.new("ShaderNodeMix")
    side.data_type = "RGBA"
    link(inside, side.inputs["Factor"])
    by_id(side.inputs, "A_Color").default_value = (0.9, 0.6, 0.3, 1.0)
    by_id(side.inputs, "B_Color").default_value = (0.65, 0.85, 1.0, 1.0)
    fade = math("SUBTRACT", None, math("EXPONENT", math("MULTIPLY", ad, value=-6.0)))
    fade.node.inputs[0].default_value = 1.0
    bands = math("ADD", math("MULTIPLY", math("COSINE", math("MULTIPLY", d, value=60.0)), value=0.2), value=0.8)
    shade = math("MULTIPLY", fade, bands)
    col = n.new("ShaderNodeMix")
    col.data_type = "RGBA"
    col.blend_type = "MULTIPLY"
    col.inputs["Factor"].default_value = 1.0
    link(by_id(side.outputs, "Result_Color"), by_id(col.inputs, "A_Color"))
    link(shade, by_id(col.inputs, "B_Color"))
    edge = n.new("ShaderNodeMix")
    edge.data_type = "RGBA"
    link(math("LESS_THAN", ad, value=0.012), edge.inputs["Factor"])
    link(by_id(col.outputs, "Result_Color"), by_id(edge.inputs, "A_Color"))
    by_id(edge.inputs, "B_Color").default_value = (1, 1, 1, 1)
    grey = math("ADD", math("MULTIPLY", d, value=0.5), value=0.5)
    pick = n.new("ShaderNodeMix")
    pick.data_type = "RGBA"
    link(kind.outputs["Fac"], pick.inputs["Factor"])
    link(grey, by_id(pick.inputs, "A_Color"))
    link(by_id(edge.outputs, "Result_Color"), by_id(pick.inputs, "B_Color"))
    emit = n.new("ShaderNodeEmission")
    link(by_id(pick.outputs, "Result_Color"), emit.inputs["Color"])
    out = n.new("ShaderNodeOutputMaterial")
    link(emit.outputs[0], out.inputs["Surface"])

    t = bpy.data.node_groups.new("preview field", "GeometryNodeTree")
    t.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n, link = t.nodes, t.links.new
    grid = n.new("GeometryNodeMeshGrid")
    grid.inputs["Size X"].default_value = grid.inputs["Size Y"].default_value = FIELD
    grid.inputs["Vertices X"].default_value = grid.inputs["Vertices Y"].default_value = 384
    group = n.new("GeometryNodeGroup")
    store = n.new("GeometryNodeStoreNamedAttribute")
    store.data_type = "FLOAT"
    store.inputs["Name"].default_value = "preview_value"
    sdf = n.new("GeometryNodeStoreNamedAttribute")
    sdf.data_type = "FLOAT"
    sdf.inputs["Name"].default_value = "preview_sdf"
    set_mat = n.new("GeometryNodeSetMaterial")
    set_mat.inputs["Material"].default_value = mat
    out = n.new("NodeGroupOutput")
    link(grid.outputs["Mesh"], store.inputs["Geometry"])
    link(store.outputs[0], sdf.inputs["Geometry"])
    link(sdf.outputs[0], set_mat.inputs["Geometry"])
    link(set_mat.outputs[0], out.inputs[0])
    obj = bpy.data.objects.new("preview field", bpy.data.meshes.new("preview field"))
    scene.collection.objects.link(obj)
    obj.hide_render = True
    obj.modifiers.new("preview", "NODES").node_group = t
    return obj, t, group, store, sdf


def render_field(scene, camera, field, g, path):
    """A function of a Vector (the position) to one Float: the field on the plane z = 0."""
    obj, t, group, store, sdf = field
    group.node_tree = g
    inputs = list(group.inputs)
    outs = [s for s in group.outputs if s.type == "VALUE"]
    if not inputs or inputs[0].type != "VECTOR" or len(group.outputs) != 1 or not outs:
        return None
    for link in list(t.links):
        if link.to_node == group or link.from_node == group:
            t.links.remove(link)
    t.links.new(outs[0], store.inputs["Value"])
    sdf.inputs["Value"].default_value = 1.0 if g.name.startswith("sdf") else 0.0
    # the position is the input's default (Position()), as an unlinked socket gives it
    frame(camera, Vector((-FIELD / 2, -FIELD / 2, 0)), Vector((FIELD / 2, FIELD / 2, 0)), flat=True)
    camera.data.ortho_scale = FIELD
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 4
    scene.render.film_transparent = False
    obj.hide_render = False
    try:
        return render_to(scene, path, compositing=False)
    finally:
        obj.hide_render = True


# ---- Compositor ----

def test_pictures():
    """Two square pictures of SIZE, the first with a disc of alpha, premultiplied."""
    out = []
    for k, name in enumerate(PICTURES):
        img = bpy.data.images.load(str(ROOT / "site" / "images" / name))
        w, h = img.size
        px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
        side = min(w, h)
        y0, x0 = (h - side) // 2, (w - side) // 2
        px = px[y0:y0 + side, x0:x0 + side]
        idx = (np.arange(SIZE) * side // SIZE)
        px = px[idx][:, idx].copy()
        px[..., 3] = 1.0
        if k == 0:
            yy, xx = np.mgrid[0:SIZE, 0:SIZE]
            d = np.hypot(xx - SIZE * 0.42, yy - SIZE * 0.55) / (SIZE * 0.36)
            alpha = np.clip((1.0 - d) * 8.0, 0.0, 1.0)
            px[..., :3] *= alpha[..., None]
            px[..., 3] = alpha
        bpy.data.images.remove(img)
        pic = bpy.data.images.new(f"preview picture {k}", SIZE, SIZE, alpha=True, float_buffer=True)
        pic.pixels[:] = px.ravel()
        pic.alpha_mode = "PREMUL"
        pic.pack()
        out.append(pic)
    return out


def compositor_rig():
    t = bpy.data.node_groups.new("preview compositor", "CompositorNodeTree")
    t.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    pictures = []
    for pic in test_pictures():
        node = t.nodes.new("CompositorNodeImage")
        node.image = pic
        pictures.append(node)
    group = t.nodes.new("CompositorNodeGroup")
    out = t.nodes.new("NodeGroupOutput")
    return t, pictures, group, out


def compositor_references(scene, rig, folder):
    """Each picture alone, and the first over the second."""
    t, pictures, group, out = rig
    over = t.nodes.new("CompositorNodeAlphaOver")
    shows = [pictures[0].outputs["Image"], pictures[1].outputs["Image"], over.outputs["Image"]]
    t.links.new(pictures[1].outputs["Image"], over.inputs["Background"])
    t.links.new(pictures[0].outputs["Image"], over.inputs["Foreground"])
    scene.compositing_node_group = t
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 1
    scene.render.film_transparent = False
    for show in shows:
        for link in list(out.inputs[0].links):
            t.links.remove(link)
        t.links.new(show, out.inputs[0])
        reference(scene, folder / "reference.png", compositing=True)
    t.nodes.remove(over)
    scene.compositing_node_group = None


def render_compositor(scene, rig, g, path):
    t, pictures, group, out = rig
    for link in list(t.links):
        t.links.remove(link)
    group.node_tree = g
    result = next((s for s in group.outputs if s.type == "RGBA"), None)
    if result is None and "mask" in g.name.lower():
        result = next((s for s in group.outputs if s.type == "VALUE"), None)
    if result is None:
        return None
    images = [s for s in group.inputs if s.type == "RGBA"]
    for picture, s in zip(pictures, images):
        t.links.new(picture.outputs["Image"], s)
    t.links.new(result, out.inputs[0])
    scene.compositing_node_group = t
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 1
    scene.render.film_transparent = False
    try:
        return render_to(scene, path, compositing=True)
    finally:
        scene.compositing_node_group = None


# ---- Shader ----

def render_shader(scene, camera, g, path):
    if not any(s.socket_type == "NodeSocketShader" for s in g.interface.items_tree
               if s.item_type == "SOCKET" and s.in_out == "OUTPUT"):
        return None
    mat = bpy.data.materials.new(f"preview {g.name}")
    nodes = mat.node_tree.nodes
    nodes.clear()
    group = nodes.new("ShaderNodeGroup")
    group.node_tree = g
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = next(s for s in group.outputs if s.type == "SHADER")
    mat.node_tree.links.new(shader, output.inputs["Surface"])
    mesh = bpy.data.meshes.new("preview sphere")
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=1.0)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)
    obj = bpy.data.objects.new("preview sphere", mesh)
    scene.collection.objects.link(obj)
    frame(camera, Vector((-1, -1, -1)), Vector((1, 1, 1)))
    camera.data.type = "PERSP"
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.film_transparent = True
    try:
        return render_to(scene, path, compositing=False)
    finally:
        bpy.data.objects.remove(obj)


# ---- The steps ----

def render(folder: Path) -> None:
    groups = asset_groups()
    fonts = bpy.utils.system_resource("DATAFILES", path="fonts")
    data = describe(groups, fonts)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "render").mkdir(exist_ok=True)
    for old in (folder / "render").glob("*.png"):
        old.unlink()
    scene, camera = scene_setup()
    geometry = geometry_rig(scene)
    plot = plot_rig(scene)
    field = field_rig(scene)
    compositor = compositor_rig()
    geometry_references(scene, camera, geometry, folder)
    compositor_references(scene, compositor, folder)
    shown = 0
    for g, d in zip(groups, data["groups"]):
        path = folder / "render" / d["file"]
        try:
            if d["kind"] == "geometry":
                got = (render_geometry(scene, camera, geometry, g, path)
                       or render_plot(scene, camera, geometry, plot, g, path)
                       or render_field(scene, camera, field, g, path))
            elif d["kind"] == "compositor":
                got = render_compositor(scene, compositor, g, path)
            else:
                got = render_shader(scene, camera, g, path)
        except Exception as e:  # a group that fails to show gets its card
            print(f"PREVIEW {g.name}: {type(e).__name__}: {e}")
            got = None
        d["render"] = got is not None
        shown += d["render"]
        print(f"PREVIEW {d['kind']:10} {'render' if d['render'] else 'card  '} {g.name}")
    (folder / "groups.json").write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"PREVIEWS {shown} rendered of {len(groups)}")


def apply(folder: Path) -> None:
    data = json.loads((folder / "groups.json").read_text(encoding="utf-8"))
    by_name = {g.name: g for g in asset_groups()}
    for d in data["groups"]:
        g = by_name[d["name"]]
        img = bpy.data.images.load(str(folder / "final" / d["file"]))
        try:
            w, h = img.size
            p = g.preview_ensure()
            p.image_size = (w, h)
            p.image_pixels_float = img.pixels[:]
        finally:
            bpy.data.images.remove(img)
    bpy.ops.wm.save_mainfile(compress=True)
    print(f"PREVIEWS {len(data['groups'])} applied to {bpy.data.filepath}")


if __name__ == "__main__":
    step, folder = sys.argv[sys.argv.index("--") + 1:][:2]
    {"render": render, "apply": apply}[step](Path(folder))
