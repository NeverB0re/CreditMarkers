"""The game's own currency icons (tools/icons/*.svg, from content/ui/shared/resources/generated_icons/currency_icons,
extracted with filediver) as RGBA8 pixels, in every size in SIZES along the longer side. build.py packs them into the
mod's patch; Chef Shared Loader's chef.bitmap draws a texture shipped there.

    python tools/make_icons.py    -> tools/preview.png, every icon at every size, and src/icon.png, the manager's
"""
import os
import re
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ICONS = {"medal": "medal.svg", "credit": "credit.svg"}
SIZES = (16, 20, 24, 28, 32, 40, 48, 64)   # the mod draws the smallest at least as big as it needs
SOURCE_LONG = 256                          # worked out at this size, then shrunk
SUB = 4                                    # scan lines per pixel


def encode(w, h, rgba):
    """RGBA8 pixels (rows top down) as a PNG."""
    raw = b"".join(b"\x00" + bytes(rgba[y * w * 4:(y + 1) * w * 4]) for y in range(h))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def polygons(d):
    """An SVG path's M L H V C Z (absolute, as these files have) as closed polygons, curves in 16 steps."""
    tokens = re.findall(r"[MLHVCZ]|-?\d*\.?\d+", d)
    out, poly, i, cmd, x, y = [], [], 0, None, 0.0, 0.0
    def num():
        nonlocal i
        i += 1
        return float(tokens[i - 1])
    while i < len(tokens):
        if tokens[i] in "MLHVCZ":
            cmd = tokens[i]
            i += 1
            if cmd == "Z":
                if poly:
                    out.append(poly)
                poly = []
                continue
        if cmd == "M":
            x, y = num(), num()
            poly = [(x, y)]
            cmd = "L"
        elif cmd == "L":
            x, y = num(), num()
            poly.append((x, y))
        elif cmd == "H":
            x = num()
            poly.append((x, y))
        elif cmd == "V":
            y = num()
            poly.append((x, y))
        elif cmd == "C":
            x1, y1, x2, y2, x3, y3 = num(), num(), num(), num(), num(), num()
            for k in range(1, 17):
                t = k / 16
                u = 1 - t
                poly.append((u * u * u * x + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t * t * t * x3,
                             u * u * u * y + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t * t * t * y3))
            x, y = x3, y3
        else:
            raise SystemExit("unexpected path data: %r" % tokens[i])
    if poly:
        out.append(poly)
    return out


def coverage(polys, W, H, scale, ox, oy):
    """How much of each pixel the polygons cover (even-odd), rows of 0..1: spans on SUB scan lines per pixel."""
    rows = [[0.0] * W for _ in range(H)]
    edges = []
    for poly in polys:
        pts = [((px - ox) * scale, (py - oy) * scale) for px, py in poly]
        edges += [(pts[k], pts[(k + 1) % len(pts)]) for k in range(len(pts))]
    for sub in range(H * SUB):
        y = (sub + 0.5) / SUB
        xs = sorted(a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]) for a, b in edges if (a[1] > y) != (b[1] > y))
        row = rows[sub // SUB]
        for k in range(0, len(xs) - 1, 2):
            x0, x1 = max(0.0, xs[k]), min(float(W), xs[k + 1])
            if x1 <= x0:
                continue
            p0, p1 = int(x0), min(W - 1, int(x1))
            if p0 == p1:
                row[p0] += (x1 - x0) / SUB
            else:
                row[p0] += (p0 + 1 - x0) / SUB
                for p in range(p0 + 1, p1):
                    row[p] += 1 / SUB
                row[p1] += (x1 - p1) / SUB
    return rows


def picture(file):
    """The icon's layers painted over each other, cut to where it shows: rows of premultiplied (r, g, b, a), 0..1.
    (These files' viewBox doesn't fit their paths, so the paths' own bounds are used.)"""
    text = open(os.path.join(HERE, "icons", file), encoding="utf-8").read()
    layers = [(polygons(d), tuple(int(c[k:k + 2], 16) / 255 for k in (0, 2, 4)))
              for d, c in re.findall(r'<path d="([^"]+)"\s+fill="#([0-9a-fA-F]{6})"', text)]
    pts = [p for polys, _ in layers for poly in polys for p in poly]
    ox, oy = min(p[0] for p in pts), min(p[1] for p in pts)
    bw, bh = max(p[0] for p in pts) - ox, max(p[1] for p in pts) - oy
    scale = SOURCE_LONG / max(bw, bh)
    W, H = max(1, round(bw * scale)), max(1, round(bh * scale))
    out = [[(0.0, 0.0, 0.0, 0.0)] * W for _ in range(H)]
    for polys, rgb in layers:
        cov = coverage(polys, W, H, scale, ox, oy)
        for y in range(H):
            line, c = out[y], cov[y]
            for x in range(W):
                a = min(1.0, c[x])
                if a > 0:
                    d = line[x]
                    line[x] = (rgb[0] * a + d[0] * (1 - a), rgb[1] * a + d[1] * (1 - a), rgb[2] * a + d[2] * (1 - a),
                               a + d[3] * (1 - a))
    return out


def shrink(px, size):
    """Box filter to this size along the longer side, back to straight RGBA8."""
    h, w = len(px), len(px[0])
    if w >= h:
        W, H = size, max(1, round(h * size / w))
    else:
        W, H = max(1, round(w * size / h)), size
    out = bytearray(W * H * 4)
    for j in range(H):
        sy0, sy1 = j * h / H, (j + 1) * h / H
        for i in range(W):
            sx0, sx1 = i * w / W, (i + 1) * w / W
            acc = [0.0, 0.0, 0.0, 0.0]
            weight = 0.0
            y = int(sy0)
            while y < sy1:
                hy = min(sy1, y + 1) - max(sy0, y)
                x = int(sx0)
                while x < sx1:
                    k = (min(sx1, x + 1) - max(sx0, x)) * hy
                    p = px[min(y, h - 1)][min(x, w - 1)]
                    for c in range(4):
                        acc[c] += p[c] * k
                    weight += k
                    x += 1
                y += 1
            a = acc[3] / weight
            if a > 0:
                o = (j * W + i) * 4
                out[o:o + 4] = bytes((min(255, round(acc[0] / weight / a * 255)), min(255, round(acc[1] / weight / a * 255)),
                                      min(255, round(acc[2] / weight / a * 255)), min(255, round(a * 255))))
    return W, H, bytes(out)


def baked():
    """[(icon name, size, width, height, RGBA8 pixels)] for every icon and size."""
    out = []
    for name, file in sorted(ICONS.items()):
        px = picture(file)
        for size in SIZES:
            w, h, rgba = shrink(px, size)
            out.append((name, size, w, h, rgba))
    return out


def over(canvas, W, ox, oy, w, h, rgba, back):
    """Paint RGBA8 pixels on an RGBA8 canvas with this background."""
    for y in range(h):
        for x in range(w):
            s = (y * w + x) * 4
            a = rgba[s + 3] / 255
            o = ((oy + y) * W + ox + x) * 4
            canvas[o:o + 4] = bytes([round(back[c] * (1 - a) + rgba[s + c] * a) for c in range(3)] + [255])


if __name__ == "__main__":
    back = (46, 58, 64)                           # a preview: over a grey like the ground
    items = baked()
    W, H = sum(s + 6 for s in SIZES) + 6, sum(1 for _ in ICONS) * 76
    canvas = bytearray(bytes(list(back) + [255]) * (W * H))
    row = {name: k for k, name in enumerate(sorted(ICONS))}
    x_at = {}
    for name, size, w, h, rgba in items:
        ox = x_at.get(name, 6)
        over(canvas, W, ox, row[name] * 76 + 6, w, h, rgba, back)
        x_at[name] = ox + size + 6
    with open(os.path.join(HERE, "preview.png"), "wb") as f:
        f.write(encode(W, H, canvas))
    # the manager's icon: both, over a dark square
    S = 256
    dark = (12, 16, 21)
    canvas = bytearray(bytes(list(dark) + [255]) * (S * S))
    medal = shrink(picture(ICONS["medal"]), 170)
    credit = shrink(picture(ICONS["credit"]), 110)
    over(canvas, S, 14, 20, medal[0], medal[1], medal[2], dark)
    over(canvas, S, 158, 120, credit[0], credit[1], credit[2], dark)
    with open(os.path.join(os.path.dirname(HERE), "src", "icon.png"), "wb") as f:
        f.write(encode(S, S, canvas))
    print("%d textures, preview.png, src/icon.png" % len(items))
