"""The cards of the standard library's assets, for the groups no picture shows (tools/stdlib_previews.py).

    python3 tools/stdlib_cards.py <dir>

Reads <dir>/groups.json and <dir>/render/, writes <dir>/final/: for each group its rendered picture
(a compositor's over a dark background, as a viewer shows its alpha), or a card. A card has the colour of its kind of tree, the name of the group, its module and section,
and its sockets as Blender draws them: inputs on the left, outputs on the right, a dot of the colour
of their type. It is drawn at twice its size and halved, in Inter, Blender's font.
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 256
K = 2  # drawn at K times its size
BG = (29, 29, 29, 255)
PANEL = (48, 48, 48, 255)
TEXT = (230, 230, 230, 255)
DIM = (150, 150, 150, 255)

KIND = {  # header colour, the word
    "geometry": ((0, 150, 125, 255), "Geometry Nodes"),
    "shader": ((60, 140, 60, 255), "Shader"),
    "compositor": ((200, 110, 40, 255), "Compositor"),
}
SOCKET = {  # Blender's socket colours
    "Float": (161, 161, 161), "Int": (89, 140, 92), "Bool": (204, 166, 214), "Vector": (99, 99, 199),
    "Color": (199, 199, 41), "Rotation": (166, 99, 199), "Matrix": (66, 111, 150), "String": (112, 178, 255),
    "Geometry": (0, 214, 163), "Shader": (99, 199, 99), "Menu": (102, 102, 102), "Object": (237, 158, 92),
    "Image": (99, 56, 99), "Collection": (245, 245, 245), "Material": (235, 117, 130), "Texture": (158, 79, 163),
    "Bundle": (196, 140, 88), "Closure": (138, 188, 200),
}
ROWS = 6  # sockets shown on each side


def fonts(folder: str):
    inter = Path(folder) / "Inter.woff2"

    def font(size, weight):
        f = ImageFont.truetype(str(inter), size * K)
        try:
            f.set_variation_by_axes([weight])
        except (OSError, ValueError):
            pass
        return f
    return font


def fit(draw, text, font, width, lines):
    """`text` wrapped into at most `lines` lines of `width`, the last cut with an ellipsis."""
    words = text.split()
    out, line = [], ""
    for w in words:
        trial = f"{line} {w}".strip()
        if draw.textlength(trial, font=font) <= width:
            line = trial
            continue
        if line:
            out.append(line)
        line = w
    if line:
        out.append(line)
    if len(out) > lines:
        out = out[:lines]
        out[-1] += "…"
    clipped = []
    for ln in out:
        while draw.textlength(ln, font=font) > width and len(ln) > 2:
            ln = ln[:-2] + "…"
        clipped.append(ln)
    return clipped


def card(g: dict, font) -> Image.Image:
    s = SIZE * K
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color, word = KIND[g["kind"]]
    pad = 12 * K
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=18 * K, fill=BG)
    d.rounded_rectangle((0, 0, s - 1, 34 * K), radius=18 * K, fill=color)
    d.rectangle((0, 18 * K, s - 1, 34 * K), fill=color)
    small, label, title = font(12, 500), font(13, 500), font(24, 700)
    d.text((pad, 9 * K), word, font=label, fill=(255, 255, 255, 255))
    module = g["module"]
    d.text((s - pad, 9 * K), module, font=label, fill=(255, 255, 255, 230), anchor="ra")

    y = 44 * K
    for line in fit(d, g["name"], title, s - 2 * pad, 2):
        d.text((pad, y), line, font=title, fill=TEXT)
        y += 28 * K
    for line in fit(d, g["section"], small, s - 2 * pad, 1):
        d.text((pad, y + 2 * K), line, font=small, fill=DIM)
        y += 16 * K
    y += 8 * K

    d.rounded_rectangle((pad // 2, y, s - pad // 2, s - pad // 2), radius=10 * K, fill=PANEL)
    y += 8 * K
    half = (s - 3 * pad) // 2
    row = 17 * K
    for side, items in (("left", g["inputs"]), ("right", g["outputs"])):
        shown = items if len(items) <= ROWS else items[:ROWS - 1]
        for i, (name, kind) in enumerate(shown):
            cy = y + i * row + row // 2
            dot = SOCKET.get(kind, (128, 128, 128))
            r = 4 * K
            if side == "left":
                cx = pad + r
                text_at, anchor = (cx + 2 * r, cy), "lm"
            else:
                cx = s - pad - r
                text_at, anchor = (cx - 2 * r, cy), "rm"
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=dot + (255,), outline=(20, 20, 20, 255), width=K)
            name = fit(d, name, small, half - 4 * r, 1)[0] if name else ""
            d.text(text_at, name, font=small, fill=TEXT, anchor=anchor)
        if len(items) > ROWS:
            cy = y + (ROWS - 1) * row + row // 2
            more = f"+{len(items) - ROWS + 1} more"
            x = pad if side == "left" else s - pad
            d.text((x, cy), more, font=small, fill=DIM, anchor="lm" if side == "left" else "rm")
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def main(folder: Path) -> None:
    data = json.loads((folder / "groups.json").read_text(encoding="utf-8"))
    font = fonts(data["fonts"])
    final = folder / "final"
    final.mkdir(exist_ok=True)
    for old in final.glob("*.png"):
        old.unlink()
    cards = 0
    for g in data["groups"]:
        rendered = folder / "render" / g["file"]
        if g.get("render") and rendered.exists():
            picture = Image.open(rendered).convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS)
            if g["kind"] == "compositor":  # an image is seen over the dark of a viewer, as its alpha says
                picture = Image.alpha_composite(Image.new("RGBA", picture.size, BG), picture)
            picture.save(final / g["file"])
        else:
            card(g, font).save(final / g["file"])
            cards += 1
    print(f"{len(data['groups']) - cards} pictures, {cards} cards in {final}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
