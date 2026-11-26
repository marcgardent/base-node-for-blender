"""The shaping curves of the module math in Python, and the two plots of the shaping motion tutorial.

  python3 examples/tutorials/shaping_motion/curves.py

Each function is the formula of its graph in stdlib/math.bn, with the same defaults, so the plots are the
graphs' own curves: site/images/tutorials/shaping-motion-profile.svg (the profile of steps 1 to 3, from
the centre of the grid to its edge) and shaping-motion-curves.svg (the ten curves of step 4). render.py
imports this file to check the columns Blender builds against these formulas.
"""

import math
from pathlib import Path

OUT = Path(__file__).resolve().parents[3] / "site" / "images" / "tutorials"

# The defaults of the steps
RINGS, FORCE, CONTRAST, LEVELS, RISE = 1.0, 0.3, 0.25, 4, 0.25


def fract(x):
    return x - math.floor(x)


def smoothstep(x, lo, hi):
    """Map Range, Smooth Step: clamped to [lo, hi], then 3f² − 2f³."""
    f = min(max((x - lo) / (hi - lo), 0.0), 1.0)
    return f * f * (3.0 - 2.0 * f)


def sine01(x):
    return math.sin(x * 6.283185) * 0.5 + 0.5


def bias(x, force=0.25):
    return x / ((1.0 / force - 2.0) * (1.0 - x) + 1.0)


def gain(x, contrast=0.25):
    if x < 0.5:
        return bias(x * 2.0, contrast) * 0.5
    return 1.0 - bias(2.0 - x * 2.0, contrast) * 0.5


def steps(x, rise=0.25):
    return math.floor(x) + smoothstep(fract(x), 1.0 - rise, 1.0)


def triangle(x):
    return 1.0 - abs(fract(x) * 2.0 - 1.0)


def square(x, duty_cycle=0.5):
    return 1.0 if fract(x) < duty_cycle else 0.0


def parabola(x, sharpness=1.0):
    return (x * 4.0 * (1.0 - x)) ** sharpness


def bump(x, center=0.5, half_width=0.25):
    d = min(abs(x - center) / half_width, 1.0)
    return 1.0 - d * d * (3.0 - d * 2.0)


def impulse(x, stiffness=4.0):
    h = stiffness * x
    return h * math.exp(1.0 - h)


def ease_in(t, power=2.0):
    return t ** power


def ease_in_out(t, power=2.0):
    return (t * 2.0) ** power * 0.5 if t < 0.5 else 1.0 - (2.0 - t * 2.0) ** power * 0.5


def bounce(t):
    if t < 0.3636364:
        return t * t * 7.5625
    if t < 0.7272727:
        u = t - 0.5454545
        return u * u * 7.5625 + 0.75
    if t < 0.9090909:
        v = t - 0.8181818
        return v * v * 7.5625 + 0.9375
    w = t - 0.9545454
    return w * w * 7.5625 + 0.984375


def elastic(t):
    return math.exp(t * -6.931472) * math.sin((t * 10.0 - 0.75) * 2.094395) + 1.0


def recoil(t, force=1.70158):
    return (force + 1.0) * t * t * t - force * t * t


# The rows of step 4, from the front
GALLERY = [
    ("sine01", sine01), ("triangle", triangle), ("square", square), ("parabola", parabola),
    ("bump", bump), ("impulse", impulse), ("ease in out", ease_in_out), ("bounce", bounce),
    ("recoil", recoil), ("elastic", elastic),
]


def wave(d):
    return sine01(d * RINGS)


def shaped(d):
    return gain(bias(wave(d), FORCE), CONTRAST)


def stepped(d):
    return steps(wave(d) * LEVELS, RISE) / LEVELS


# The ripple of step 5, with its defaults
FALL, LAG, STIFFNESS, CRESTS, REACH = 0.25, 0.15, 14.0, 10.0, 3.0


def ripple(u, d):
    local = max(u - FALL - d * LAG, 0.0)
    return impulse(local, STIFFNESS) * math.sin(local * CRESTS * 6.283185) * bump(d, 0.0, REACH)


BG, GRID, TEXT = "#161920", "#262b36", "#939ab0"
FONT = 'font-family="ui-monospace, Menlo, Consolas, monospace" font-size="12"'


def polyline(f, lo, hi, sx, sy, y0, y1, n=400):
    pts = []
    for i in range(n + 1):
        x = lo + (hi - lo) * i / n
        y = max(min(f(x), y1), y0)
        pts.append(f"{sx(x):.1f},{sy(y):.1f}")
    return "M" + " L".join(pts)


def profile():
    """Steps 1 to 3 as one profile: height against the distance to the centre of the grid."""
    W, H, LEFT, RIGHT, TOP, BOTTOM = 720, 300, 48, 20, 20, 44
    X0, X1, Y0, Y1 = 0.0, 2.0, 0.0, 1.0

    def sx(x):
        return LEFT + (x - X0) / (X1 - X0) * (W - LEFT - RIGHT)

    def sy(y):
        return TOP + (Y1 - y) / (Y1 - Y0) * (H - TOP - BOTTOM)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" {FONT}>',
             f'<rect width="{W}" height="{H}" rx="6" fill="{BG}"/>']
    for y in (0.0, 0.25, 0.5, 0.75, 1.0):
        parts.append(f'<line x1="{LEFT}" x2="{W - RIGHT}" y1="{sy(y):.1f}" y2="{sy(y):.1f}" stroke="{GRID}"/>')
        parts.append(f'<text x="{LEFT - 8}" y="{sy(y) + 4:.1f}" fill="{TEXT}" text-anchor="end">{y:g}</text>')
    for x in (0.0, 0.5, 1.0, 1.5, 2.0):
        parts.append(f'<line x1="{sx(x):.1f}" x2="{sx(x):.1f}" y1="{TOP}" y2="{H - BOTTOM}" stroke="{GRID}"/>')
        parts.append(f'<text x="{sx(x):.1f}" y="{H - BOTTOM + 18}" fill="{TEXT}" text-anchor="middle">{x:g}</text>')
    parts.append(f'<text x="{W - RIGHT}" y="{H - 6}" fill="{TEXT}" text-anchor="end">d: distance to the centre, in metres</text>')
    curves = [
        (wave, "#79c0ff", "1.5", "5 4", "step 1: sine01"),
        (shaped, "#f2cc60", "2", "", "step 2: gain(bias(…))"),
        (stepped, "#ff7b72", "2.5", "", "step 3: steps"),
    ]
    for i, (f, color, width, dash, label) in enumerate(curves):
        dashes = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(f'<path d="{polyline(f, X0, X1, sx, sy, Y0, Y1)}" fill="none" stroke="{color}" stroke-width="{width}"{dashes}/>')
        parts.append(f'<text x="{W - RIGHT - 190}" y="{TOP + 18 + i * 18}" fill="{color}">{label}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def gallery():
    """The ten curves of step 4, one small plot each, in the order of the rows from the front."""
    COLS, PW, PH, GAP, PAD = 5, 136, 112, 8, 12
    W = COLS * PW + (COLS - 1) * GAP + 2 * PAD
    H = 2 * PH + GAP + 2 * PAD
    Y0, Y1 = -0.2, 1.4
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" {FONT}>',
             f'<rect width="{W}" height="{H}" rx="6" fill="{BG}"/>']
    for i, (name, f) in enumerate(GALLERY):
        ox = PAD + (i % COLS) * (PW + GAP)
        oy = PAD + (i // COLS) * (PH + GAP)
        left, right, top, bottom = ox + 6, ox + PW - 6, oy + 22, oy + PH - 6

        def sx(x, left=left, right=right):
            return left + x * (right - left)

        def sy(y, top=top, bottom=bottom):
            return top + (Y1 - y) / (Y1 - Y0) * (bottom - top)

        parts.append(f'<rect x="{ox}" y="{oy}" width="{PW}" height="{PH}" rx="4" fill="#1c2029"/>')
        for y in (0.0, 1.0):
            parts.append(f'<line x1="{left}" x2="{right}" y1="{sy(y):.1f}" y2="{sy(y):.1f}" stroke="{GRID}"/>')
        parts.append(f'<text x="{ox + 8}" y="{oy + 16}" fill="#e6e9ef">{name}</text>')
        # Up to a hair short of 1, as the last column of a row is in single precision: at 1 itself, square
        # starts its next period, at 1
        parts.append(f'<path d="{polyline(f, 0.0, 0.9999999, sx, sy, Y0, Y1)}" fill="none" stroke="#f2cc60" stroke-width="2"/>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in (("profile", profile()), ("curves", gallery())):
        out = OUT / f"shaping-motion-{name}.svg"
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
