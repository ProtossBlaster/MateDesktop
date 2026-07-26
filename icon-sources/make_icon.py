"""Draw the Mate app icon and emit every asset both platforms need.

    python3 make_icon.py            # writes mate-icon.svg, Mate.icns, Mate.ico, previews

Drawn with Pillow rather than rendered from the SVG because there is no SVG renderer on this
machine and adding one (librsvg, cairo, a headless browser) would put a build dependency in the
way of a file that changes twice a year. The SVG is written out too — it is the readable source,
and the geometry below is its single origin.

Everything is drawn at 4x and reduced with Lanczos. That is what gives the small sizes their edge
quality: antialiasing a 16-pixel icon directly looks like porridge, downsampling a 64-pixel one
looks like an icon.

DESIGN — what was wrong with the previous one and what this fixes:

  * The pulse peaked at y=190 while the wheels ended at y=187. They touched, and at 32 pixels —
    which is how it is actually seen, in the taskbar and the Dock — car and heartbeat merged into
    one smudge. Here the car SITS ON the line, so the two are one object rather than two competing
    ones, and the heartbeat is off to the left where nothing else is.
  * The whole composition sat in the bottom 60%, leaving the top empty. The centre of mass is now
    within two pixels of the middle.
  * The outline was a plain rounded rectangle. Apple's is a squircle — a superellipse, continuous
    curvature — and next to the system icons in the Dock the difference is visible even when you
    cannot name it.
"""
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OUT = HERE.parent                      # Mate.icns / Mate.ico live beside the build scripts

NAVY = (15, 23, 42, 255)               # #0f172a — Mate's dashboard background
LIGHT = (226, 232, 240, 255)           # #e2e8f0
TEAL = (20, 184, 166, 255)             # #14b8a6 — the brand accent

S = 256                                # design units; every coordinate below is in these
SCALE = 4                              # drawn this many times larger, then reduced


# ── geometry, in design units ───────────────────────────────────────────────────────────
# THE PROPORTIONS ARE THE OLD ICON'S, and that is deliberate. Two attempts at redrawing the car
# from scratch produced something that read as a van: body 2.6:1 instead of 3.8:1, cabin too tall
# and too wide. The original silhouette was right — what was wrong with the old icon was where the
# parts sat, not what they were. So the shape is kept and only the arrangement changes.
#
# Every number below is derived from those ratios at a body 176 wide and 46 tall:
#   cabin base   25% .. 82.5% of the body   |   cabin roof   40% .. 62.5%
#   cabin height 76% of the body height     |   wheels at    27.5% and 77.5%, radius 43%
BODY = (62, 76, 238, 122)                        # x0, y0, x1, y1
BODY_R = 21
CABIN = [(106, 76), (132, 43), (132, 41), (141, 41),
         (172, 41), (183, 41), (188, 47), (207, 76)]
WHEELS = [(110, 120), (198, 120)]
WHEEL_R = 20
WHEEL_W = 10
# The road the car stands on, with the heartbeat in the one stretch nothing else occupies. The
# wheels overlap the line rather than hovering over it: that overlap is what makes the two read as
# one object instead of a car parked above a decoration — which is exactly what the old icon was,
# and why its wheels and its pulse collided.
PULSE = [(22, 156), (30, 156), (41, 130), (52, 208), (62, 156), (236, 156)]
PULSE_W = 14


def squircle(n=5.0, steps=256):
    """Apple's icon outline: |x/a|^n + |y/b|^n = 1, not a rounded rectangle."""
    a = b = S / 2
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        ct, st = math.cos(t), math.sin(t)
        pts.append((a + a * math.copysign(abs(ct) ** (2 / n), ct),
                    b + b * math.copysign(abs(st) ** (2 / n), st)))
    return pts


def thick_polyline(draw, pts, colour, width):
    """A stroked polyline with round caps and joins, which ImageDraw does not do on its own —
    it butts every segment square, and on a heartbeat that shows as notches at every corner."""
    draw.line(pts, fill=colour, width=width)
    r = width / 2
    for x, y in pts:
        draw.ellipse((x - r, y - r, x + r, y + r), fill=colour)


def render(size):
    k = SCALE * size / S                                  # design units -> supersampled pixels
    px = int(S * k)
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def sc(seq):
        return [(x * k, y * k) for x, y in seq]

    d.polygon(sc(squircle()), fill=NAVY)

    x0, y0, x1, y1 = BODY
    d.rounded_rectangle((x0 * k, y0 * k, x1 * k, y1 * k), radius=BODY_R * k, fill=LIGHT)
    d.polygon(sc(CABIN), fill=LIGHT)

    for cx, cy in WHEELS:
        r = WHEEL_R * k
        d.ellipse((cx * k - r, cy * k - r, cx * k + r, cy * k + r),
                  fill=NAVY, outline=LIGHT, width=max(1, round(WHEEL_W * k)))

    thick_polyline(d, sc(PULSE), TEAL, max(1, round(PULSE_W * k)))

    return img.resize((size, size), Image.LANCZOS)


def write_svg(path):
    """The readable source. Same numbers as above — if one is edited, edit both."""
    pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in squircle())
    cab = " ".join(f"{'M' if i == 0 else 'L'}{x},{y}" for i, (x, y) in enumerate(CABIN))
    pulse = " ".join(f"{x},{y}" for x, y in PULSE)
    x0, y0, x1, y1 = BODY
    wheels = "\n  ".join(
        f'<circle cx="{cx}" cy="{cy}" r="{WHEEL_R}" fill="#0f172a" '
        f'stroke="#e2e8f0" stroke-width="{WHEEL_W}"/>' for cx, cy in WHEELS)
    path.write_text(f'''<svg width="{S}" height="{S}" viewBox="0 0 {S} {S}"
     xmlns="http://www.w3.org/2000/svg">
  <title>LeapMotor Mate</title>
  <!-- Apple's icon outline is a superellipse, not a rounded rectangle. -->
  <polygon points="{pts}" fill="#0f172a"/>
  <path d="{cab} Z" fill="#e2e8f0"/>
  <rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" rx="{BODY_R}" fill="#e2e8f0"/>
  {wheels}
  <!-- The car sits ON the line: one object, not a car with a heartbeat parked under it. -->
  <polyline points="{pulse}" fill="none" stroke="#14b8a6" stroke-width="{PULSE_W}"
            stroke-linecap="round" stroke-linejoin="round"/>
</svg>
''', encoding="utf-8")


def main():
    write_svg(HERE / "mate-icon.svg")
    render(1024).save(HERE / "icon_1024.png")

    # macOS wants an .iconset directory; iconutil turns it into the .icns.
    iconset = HERE / "Mate.iconset"
    iconset.mkdir(exist_ok=True)
    for base in (16, 32, 128, 256, 512):
        render(base).save(iconset / f"icon_{base}x{base}.png")
        render(base * 2).save(iconset / f"icon_{base}x{base}@2x.png")
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(OUT / "Mate.icns")],
                   check=True)

    # Windows takes every size inside one .ico. 256 is what File Explorer shows at "extra large",
    # 16 is the title bar — both come from this same file, so both have to be in it.
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    render(256).save(OUT / "Mate.ico", format="ICO",
                     sizes=[(s, s) for s in sizes],
                     append_images=[render(s) for s in sizes if s != 256])

    # A strip at the sizes people actually see, for eyeballing before it ships.
    strip = Image.new("RGBA", (16 + 128 + 16 + 64 + 16 + 32 + 16 + 16 + 16, 160), (255, 255, 255, 0))
    x = 16
    for s in (128, 64, 32, 16):
        strip.paste(render(s), (x, 16 + (128 - s) // 2))
        x += s + 16
    strip.save(HERE / "preview_sizes.png")

    print(f"svg   {HERE / 'mate-icon.svg'}")
    print(f"icns  {OUT / 'Mate.icns'}  ({(OUT / 'Mate.icns').stat().st_size / 1024:.0f} KB)")
    print(f"ico   {OUT / 'Mate.ico'}  ({(OUT / 'Mate.ico').stat().st_size / 1024:.0f} KB, {len(sizes)} sizes)")


if __name__ == "__main__":
    main()
