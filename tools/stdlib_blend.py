"""Write a .blend of the standard library, every group open in its editor: the distribution file.

Every module of stdlib/ the Blender that runs promises is built, and each of its groups is put as a
node in the tree of its editor:

- Geometry Nodes: the group "Base Node stdlib geometry" of the modifier of an object "Base Node stdlib";
- Shader Editor: the material "Base Node stdlib" of that object;
- Compositor: "Base Node stdlib compositor", the compositing group of the scene.

They are put in frames, a frame per module and inside it a frame per section of the module (its
`// ---- Section ----` comments), so that the tree reads as the library does. The workspaces
Geometry Nodes, Shading and Compositing show them.

Run in Blender via:
    blender --background --factory-startup --python-exit-code 1 \
      --python tools/stdlib_blend.py -- [out.blend]

The default out is site/assets/<x.y>/base-node-stdlib.blend: a remote asset library, a library
by version of Blender. Each group of the standard library is an asset, in the catalog
Base Node/<module>/<section>; beside the file are its catalogs (blender_assets.cats.txt) and the
head of the library (_asset-library-meta.json), whose index this Blender then writes:
    blender -c asset_listing generate site/assets/<x.y>
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon" / "tests"))
import test_extension as T  # noqa: E402  (loads base_node)

import bpy  # noqa: E402

from base_node.host import modules  # noqa: E402
from base_node.ui import actions  # noqa: E402

VERSION = ".".join(str(v) for v in bpy.app.version[:2])
NAME = "Base Node stdlib"

KINDS = {  # graph kind: the bl_idname of its trees
    "geometry": "GeometryNodeTree",
    "shader": "ShaderNodeTree",
    "compositor": "CompositorNodeTree",
}

SECTION = re.compile(r"^//\s*-{2,}\s*(.+?)\s*-{2,}\s*$")
GRAPH = re.compile(r'^(?:export\s+)?(\w+)\s+graph\s+(?:"([^"]+)"|(\w+))')

# Layout, in the units of the node editor
COLUMNS = 4  # groups on a row of a section
GAP_X, GAP_Y = 60, 50  # between two groups
SECTION_GAP = 120  # between two sections of a module
MODULE_GAP = 300  # between two modules
LABEL = 60  # the room a frame's label takes above its nodes


def sections(path: Path) -> tuple[dict[str, str], list[str], str]:
    """(section of each graph, the sections in their order, the module's description)."""
    of, order, section, description = {}, [], "", ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("// @description"):
            description = line.removeprefix("// @description").strip()
        if m := SECTION.match(line):
            section = m.group(1)
            continue
        if m := GRAPH.match(line):
            of[m.group(2) or m.group(3)] = section
            if section not in order:
                order.append(section)
    return of, order, description


def node_height(tree) -> float:
    """The height of a group node of `tree`, without Blender drawing it (background mode)."""
    rows = 0
    for i in tree.interface.items_tree:
        if i.item_type == "PANEL":
            rows += 1.2
        elif i.in_out == "OUTPUT":
            rows += 1
        elif i.socket_type in ("NodeSocketVector", "NodeSocketRotation") and not i.hide_value:
            rows += 4.2  # its label, then a row by component
        elif i.socket_type == "NodeSocketMatrix" and not i.hide_value:
            rows += 1
        else:
            rows += 1.1
    return 60 + 22 * rows


def frame(tree, name: str, label: str, parent=None):
    f = tree.nodes.new("NodeFrame")
    f.name, f.label = name, label
    f.label_size = 20 if parent is None else 16
    f.shrink = True
    if parent is not None:
        f.parent = parent
    return f


def module_of(g, order: dict) -> str:
    """The module a group comes from: the one its build named (a module another one uses), else
    the one whose text has a graph of its name (the module imported)."""
    if name := g.get(modules.MODULE):
        return name
    for module, (of, _sections, _description) in order.items():
        if g.name in of:
            return module
    return "other"


def lay_out(tree, groups: list, order: dict) -> None:
    """Put a group node of each of `groups` in `tree`, in frames by module and section.

    `order` maps a module to (section of each graph, its sections, its description).
    """
    for n in list(tree.nodes):
        tree.nodes.remove(n)
    by_module: dict[str, dict[str, list]] = {}
    for g in groups:
        module = module_of(g, order)
        of = order.get(module, ({}, [], ""))[0]
        by_module.setdefault(module, {}).setdefault(of.get(g.name, ""), []).append(g)

    x = 0.0
    for module in [m for m in order if m in by_module] + [m for m in by_module if m not in order]:
        of, section_order, description = order.get(module, ({}, [], ""))
        mframe = frame(tree, f"module {module}", module)
        width_module, y = 0.0, -LABEL
        found = by_module[module]
        for section in [s for s in section_order if s in found] + [s for s in found if s not in section_order]:
            sframe = frame(tree, f"{module} / {section or 'graphs'}", section or module, mframe)
            items = sorted(found[section], key=lambda g: g.name) if not section_order else found[section]
            row_y, width = y - LABEL, 0.0
            for i in range(0, len(items), COLUMNS):
                row = items[i:i + COLUMNS]
                cx, tallest = x + 40, 0.0
                for g in row:
                    node = tree.nodes.new(tree.bl_idname.replace("Tree", "Group"))
                    node.node_tree = g
                    node.width = 220
                    node.label = ""
                    node.parent = sframe
                    node.location = (cx, row_y)
                    cx += node.width + GAP_X
                    tallest = max(tallest, node_height(g))
                width = max(width, cx - x)
                row_y -= tallest + GAP_Y
            y = row_y - SECTION_GAP
            width_module = max(width_module, width)
        if description:
            mframe.label = f"{module} — {description}"[:63]
        x += width_module + MODULE_GAP


CATALOG_ROOT = "Base Node"
CATALOG_NS = uuid.UUID("6f1d1c0e-8b7a-4f0e-9a51-0b5e0de57d1b")  # catalog ids, the same from one build to the next
KIND_TAGS = {idname: kind.capitalize() for kind, idname in KINDS.items()}


def catalog_path(*parts: str) -> str:
    """A catalog path: its parts cannot hold the `:` of the catalog file, nor a `/`."""
    return "/".join(re.sub(r"\s*[:/]\s*", " - ", p).strip() for p in parts if p)


def mark_assets(groups: list, order: dict) -> dict[str, str]:
    """Mark each group an asset, in the catalog Base Node/<module>/<section>; returns {path: id}."""
    catalogs: dict[str, str] = {}
    for g in groups:
        module = module_of(g, order)
        path = catalog_path(CATALOG_ROOT, module, order[module][0].get(g.name, ""))
        parts = path.split("/")
        for i in range(1, len(parts) + 1):  # the parents too, so that the tree of catalogs is whole
            sub = "/".join(parts[:i])
            catalogs.setdefault(sub, str(uuid.uuid5(CATALOG_NS, sub)))
        g.asset_mark()
        a = g.asset_data
        a.catalog_id = catalogs[path]
        a.description = g.description
        a.author = "Base Node"
        a.license = "Apache-2.0 OR MIT"
        for tag in ("Base Node", module, KIND_TAGS[g.bl_idname]):
            a.tags.new(tag, skip_if_exists=True)
    return catalogs


def write_catalogs(catalogs: dict[str, str], folder: Path) -> None:
    lines = ["# This is an Asset Catalog Definition file for Blender.", "", "VERSION 1", ""]
    for path, cid in sorted(catalogs.items()):
        lines.append(f"{cid}:{path}:{path.replace('/', '-')}")
    (folder / "blender_assets.cats.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_meta(folder: Path) -> None:
    """The head of a remote asset library, `blender -c asset_listing generate` fills its versions."""
    meta = folder / "_asset-library-meta.json"
    if not meta.exists():
        meta.write_text(json.dumps({
            "api_versions": {},
            "name": f"Base Node stdlib (Blender {VERSION})",
            "contact": {"name": "Base Node", "url": "https://blender.basenode.ludopant.com/"},
        }, indent=2) + "\n", encoding="utf-8")


def main(out: Path) -> None:
    bpy.ops.wm.read_homefile(use_factory_startup=True)
    order = {}
    built = []
    for path in sorted(T.STDLIB_DIR.glob("*.bn")):
        module = path.stem
        if not T.promises_this_blender(module):
            print(f"skip {module}: not promised for Blender {VERSION}")
            continue
        order[module] = sections(path)
        warnings: list = []
        built += actions.import_file(str(path), warnings)
        for w in warnings:
            print(f"{module}: {w}")
    # every group a module made, its own and those of the modules it uses
    groups = [g for g in bpy.data.node_groups if module_of(g, order) != "other"]
    others = sorted(g.name for g in bpy.data.node_groups if g not in groups)
    if others:
        print(f"left out, of no module: {others}")

    scene = bpy.context.scene
    # Geometry Nodes and Shader Editor: an object with a modifier and a material
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)
    mesh = bpy.data.meshes.new(NAME)
    obj = bpy.data.objects.new(NAME, mesh)
    scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    gn = bpy.data.node_groups.new(f"{NAME} geometry", "GeometryNodeTree")
    gn.use_fake_user = True
    lay_out(gn, [g for g in groups if g.bl_idname == KINDS["geometry"]], order)
    mod = obj.modifiers.new(NAME, "NODES")
    mod.node_group = gn
    mod.show_viewport = False  # the tree is a catalog: it has no output to compute

    mat = bpy.data.materials.new(NAME)
    mat.use_nodes = True
    mat.use_fake_user = True
    lay_out(mat.node_tree, [g for g in groups if g.bl_idname == KINDS["shader"]], order)
    mesh.materials.append(mat)

    comp = bpy.data.node_groups.new(f"{NAME} compositor", "CompositorNodeTree")
    comp.use_fake_user = True
    lay_out(comp, [g for g in groups if g.bl_idname == KINDS["compositor"]], order)
    scene.compositing_node_group = comp

    catalogs = mark_assets(groups, order)

    for kind, idname in KINDS.items():
        print(f"{kind}: {sum(g.bl_idname == idname for g in groups)} groups")
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
    write_catalogs(catalogs, out.parent)
    write_meta(out.parent)
    print(f"wrote {out}, {len(catalogs)} catalogs")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    main(Path(argv[0]) if argv else ROOT / "site" / "assets" / VERSION / "base-node-stdlib.blend")
