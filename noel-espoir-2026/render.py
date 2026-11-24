#!/usr/bin/env python3
"""Noël de l'Espoir 2026 – série « Le compte à rebours de l'espoir ».

Monte les vidéos verticales (1080x1920, 30 i/s) en animation graphique :
image générée image par image avec Pillow, musique et effets sonores
synthétisés avec numpy, encodage avec ffmpeg.

Usage :
    python3 render.py                 # toutes les vidéos
    python3 render.py c1 c5_j20       # certaines vidéos
    python3 render.py --stills c1     # images de contrôle seulement
    python3 render.py --voice voix/   # mixe les voix off trouvées dans voix/
"""
import functools
import math
import os
import random
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
BASE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(BASE, "assets")
OUT = os.path.join(BASE, "videos")
FONT_PF = os.path.join(A, "fonts", "PlayfairDisplay.ttf")
FONT_OS = os.path.join(A, "fonts", "Oswald.ttf")

GREEN_BG = (15, 42, 29)
GOLD = (212, 165, 55)
GOLD_L = (255, 210, 110)
GOLD_D = (168, 118, 30)
RED = (179, 32, 42)
CREAM = (255, 248, 236)

PHONE = "+228 90 31 77 98"
MOMO = "+228 92 44 17 19"
EMAIL = "emergencesocialcommunity@gmail.com"


# ---------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ramp(t, a, b):
    if b <= a:
        return 1.0 if t >= a else 0.0
    return clamp((t - a) / (b - a))


def ease_out(x):
    return 1 - (1 - x) ** 3


def ease_io(x):
    return x * x * (3 - 2 * x)


def ease_back(x):
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def window(t, a, b, fi=0.35, fo=0.35):
    return min(ramp(t, a, a + fi), 1 - ramp(t, b - fo, b))


@functools.lru_cache(None)
def font(path, size, wght):
    f = ImageFont.truetype(path, size)
    try:
        f.set_variation_by_axes([wght])
    except Exception:
        pass
    return f


def with_alpha(im, a):
    if a >= 0.999:
        return im
    r, g, b, al = im.split()
    al = al.point(lambda v: int(v * a))
    return Image.merge("RGBA", (r, g, b, al))


def paste(frame, spr, cx, cy, scale=1.0, alpha=1.0, rot=0.0):
    if alpha <= 0.004 or scale <= 0.01:
        return
    s = spr
    if rot:
        s = s.rotate(rot, resample=Image.BICUBIC, expand=True)
    if abs(scale - 1) > 1e-3:
        s = s.resize((max(1, int(s.width * scale)), max(1, int(s.height * scale))), Image.BILINEAR)
    s = with_alpha(s, min(1.0, alpha))
    x = int(round(cx - s.width / 2))
    y = int(round(cy - s.height / 2))
    fx0, fy0 = max(0, x), max(0, y)
    fx1, fy1 = min(frame.width, x + s.width), min(frame.height, y + s.height)
    if fx1 <= fx0 or fy1 <= fy0:
        return
    frame.alpha_composite(s, (fx0, fy0), (fx0 - x, fy0 - y, fx1 - x, fy1 - y))


def supersample(w, h, fn, k=3):
    im = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    fn(ImageDraw.Draw(im), k, im)
    return im.resize((w, h), Image.LANCZOS)


def radial(size, color, a0=255, power=2.0):
    y, x = np.mgrid[0:size, 0:size]
    d = np.sqrt((x - size / 2) ** 2 + (y - size / 2) ** 2) / (size / 2)
    a = np.clip(1 - d, 0, 1) ** power * a0
    arr = np.zeros((size, size, 4), np.uint8)
    arr[..., :3] = color
    arr[..., 3] = a.astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def gradient_fill(mask, top, bottom):
    w, h = mask.size
    g = np.linspace(0, 1, h)[:, None, None]
    arr = (np.array(top) * (1 - g) + np.array(bottom) * g).repeat(w, axis=1)
    out = np.dstack([arr.astype(np.uint8), np.array(mask)])
    return Image.fromarray(out, "RGBA")


@functools.lru_cache(None)
def text_spr(text, path=FONT_OS, size=60, wght=600, fill=CREAM, gold=False,
             glow=0, shadow=True, stroke=0):
    f = font(path, size, wght)
    bb = f.getbbox(text, stroke_width=stroke)
    pad = 24 + glow * 3
    w, h = bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad
    org = (pad - bb[0], pad - bb[1])
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text(org, text, font=f, fill=255, stroke_width=stroke, stroke_fill=255)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sh.putalpha(mask.point(lambda v: int(v * 0.7)))
        sh = sh.filter(ImageFilter.GaussianBlur(6))
        out.alpha_composite(sh, (0, 4))
    if glow:
        gl = Image.new("RGBA", (w, h), GOLD_L + (0,))
        gl.putalpha(mask.filter(ImageFilter.GaussianBlur(glow)).point(lambda v: min(255, int(v * 1.6))))
        out.alpha_composite(gl)
    if gold:
        out.alpha_composite(gradient_fill(mask, (255, 226, 140), GOLD_D))
    else:
        layer = Image.new("RGBA", (w, h), fill + (0,))
        layer.putalpha(mask)
        out.alpha_composite(layer)
    return out


def stack(sprites, gap=0):
    w = max(s.width for s in sprites)
    h = sum(s.height for s in sprites) + gap * (len(sprites) - 1)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    y = 0
    for s in sprites:
        out.alpha_composite(s, ((w - s.width) // 2, y))
        y += s.height + gap
    return out


def wrap(text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        test = (cur + " " + wd).strip()
        if f.getlength(test) <= maxw or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = wd
    lines.append(cur)
    return lines


# ---------------------------------------------------------------- fixed layers
def make_background():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((x - W / 2) / W) ** 2 + ((y - H * 0.42) / H) ** 2)
    k = np.clip(1 - d * 1.7, 0, 1)[..., None] ** 1.5
    img = np.array(GREEN_BG) * (1 - k) + np.array((30, 74, 50)) * k
    return Image.fromarray(img.astype(np.uint8), "RGB").convert("RGBA")


def make_bokeh(seed, n, rmin, rmax, amin, amax, blur):
    rnd = random.Random(seed)
    im = Image.new("RGBA", (W + 240, H + 240), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for _ in range(n):
        cx, cy = rnd.uniform(0, W + 240), rnd.uniform(0, H + 240)
        # plus de lumières en haut et sur les bords, comme l'affiche
        if 380 < cx < W - 140 and 700 < cy < H - 300 and rnd.random() < 0.7:
            continue
        r = rnd.uniform(rmin, rmax)
        c = rnd.choice([(255, 196, 92), (255, 214, 140), (240, 170, 60), (255, 230, 180)])
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=c + (int(rnd.uniform(amin, amax)),))
    return im.filter(ImageFilter.GaussianBlur(blur))


def make_vignette():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((x - W / 2) / (W * 0.62)) ** 2 + ((y - H / 2) / (H * 0.62)) ** 2)
    a = np.clip((d - 0.55) * 1.4, 0, 0.75) * 255
    arr = np.zeros((H, W, 4), np.uint8)
    arr[..., 3] = a.astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


BULB_X = [170, 355, 540, 725, 910]


def wire_y(x):
    return 236 + 96 * (1 - ((x - 540) / 600) ** 2)


def make_garland():
    gw, gh = W, 520

    def draw(d, k, im):
        pts = [(x * k, wire_y(x) * k) for x in range(-20, W + 21, 6)]
        d.line(pts, fill=(40, 30, 18, 255), width=5 * k, joint="curve")
        for bx in BULB_X:
            wy = wire_y(bx)
            d.rounded_rectangle(((bx - 15) * k, (wy - 4) * k, (bx + 15) * k, (wy + 36) * k),
                                radius=5 * k, fill=(120, 92, 40, 255), outline=(70, 52, 22, 255), width=2 * k)
            for i in range(4):
                yy = wy + 6 + i * 8
                d.line(((bx - 14) * k, yy * k, (bx + 14) * k, yy * k), fill=(80, 60, 25, 255), width=2 * k)
            cy = wy + 84
            d.ellipse(((bx - 33) * k, (cy - 44) * k, (bx + 33) * k, (cy + 40) * k),
                      fill=(200, 225, 210, 46), outline=(225, 238, 230, 140), width=3 * k)
            d.line(((bx - 8) * k, (wy + 38) * k, (bx - 6) * k, (cy + 6) * k, (bx + 6) * k, (cy + 6) * k,
                    (bx + 8) * k, (wy + 38) * k), fill=(150, 120, 70, 200), width=2 * k)
            d.arc(((bx - 22) * k, (cy - 34) * k, (bx + 4) * k, (cy + 6) * k), 190, 250,
                  fill=(255, 255, 255, 150), width=4 * k)
    return supersample(gw, gh, draw)


def make_lit_bulb():
    s = 140

    def draw(d, k, im):
        c = s / 2
        d.ellipse(((c - 33) * k, (c - 44) * k, (c + 33) * k, (c + 40) * k), fill=(255, 214, 120, 255))
        d.ellipse(((c - 22) * k, (c - 30) * k, (c + 22) * k, (c + 26) * k), fill=(255, 236, 180, 255))
        d.ellipse(((c - 11) * k, (c - 14) * k, (c + 11) * k, (c + 10) * k), fill=(255, 252, 235, 255))
    return supersample(s, s, draw)


# ---------------------------------------------------------------- logos & icons
def load_icon(name, size):
    return Image.open(os.path.join(A, "icons", name + ".png")).convert("RGBA").resize((size, size), Image.LANCZOS)


def make_disc_logo(img, box, size, ring=True, fit=0.86):
    src = img.crop(box).convert("RGBA")

    def draw(d, k, im):
        d.ellipse((0, 0, size * k - 1, size * k - 1), fill=(255, 255, 255, 255))
    disc = supersample(size, size, draw)
    inner = int(size * fit)
    lg = src.resize((inner, int(inner * src.height / src.width)), Image.LANCZOS)
    disc.alpha_composite(lg, ((size - lg.width) // 2, (size - lg.height) // 2))
    # tout ce qui dépasse du cercle est retiré, puis l'anneau doré est redessiné par-dessus
    m = Image.new("L", (size * 3, size * 3), 0)
    ImageDraw.Draw(m).ellipse((0, 0, size * 3 - 1, size * 3 - 1), fill=255)
    disc.putalpha(m.resize((size, size), Image.LANCZOS))
    if ring:
        def ring_fn(d, k, im):
            d.ellipse((3 * k, 3 * k, (size - 3) * k, (size - 3) * k), outline=GOLD + (255,), width=7 * k)
        disc.alpha_composite(supersample(size, size, ring_fn))
    return disc


def esc_logo(size):
    img = Image.open(os.path.join(A, "logos", "esc_original.png"))
    return make_disc_logo(img, (130, 35, 980, 885), size)


def alpha_card(size):
    img = Image.open(os.path.join(A, "logos", "alphasignal_original.jpg")).convert("RGBA")
    src = img.crop((214, 220, 1828, 1687))

    def draw(d, k, im):
        d.rounded_rectangle((0, 0, size * k - 1, size * k - 1), radius=26 * k, fill=(255, 255, 255, 255))
    card = supersample(size, size, draw)
    inner = int(size * 0.86)
    lg = src.resize((inner, int(inner * src.height / src.width)), Image.LANCZOS)
    card.alpha_composite(lg, ((size - lg.width) // 2, (size - lg.height) // 2))
    return card


def alpha_disc(size):
    img = Image.open(os.path.join(A, "logos", "alphasignal_original.jpg"))
    return make_disc_logo(img, (214, 220, 1828, 1687), size, fit=0.66)


# ---------------------------------------------------------------- UI pieces
def make_caption(text):
    f = font(FONT_OS, 50, 500)
    lines = wrap(text, f, 900)
    sprites = [text_spr(l, FONT_OS, 50, 500, CREAM, shadow=False) for l in lines]
    body = stack(sprites, gap=-30)
    pw, ph = body.width + 40, body.height + 10
    box = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    ImageDraw.Draw(box).rounded_rectangle((0, 0, pw - 1, ph - 1), radius=28, fill=(6, 20, 13, 170))
    box.alpha_composite(body, ((pw - body.width) // 2, (ph - body.height) // 2))
    return box


def make_cta(text="SOYEZ LEUR ESPOIR DE NOËL !", star=True, size=62):
    t = text_spr(text, FONT_OS, size, 650, gold=True, shadow=False)
    star_d = 104
    bw = t.width + (star_d + 30 if star else 40) + 20
    bh = 140

    def draw(d, k, im):
        d.rounded_rectangle((3 * k, 3 * k, (bw - 3) * k, (bh - 3) * k), radius=22 * k,
                            fill=(10, 46, 28, 235), outline=GOLD + (255,), width=4 * k)
    box = supersample(bw, bh, draw)
    x = 24
    if star:
        box.alpha_composite(load_icon("star", star_d), (x, (bh - star_d) // 2))
        x += star_d + 8
    box.alpha_composite(t, (x, (bh - t.height) // 2))
    return box


def make_badge(text, size=46):
    t = text_spr(text, FONT_OS, size, 650, CREAM, shadow=False)
    bw, bh = t.width + 40, t.height + 6

    def draw(d, k, im):
        d.rounded_rectangle((0, 0, (bw - 1) * k, (bh - 1) * k), radius=(bh // 2) * k, fill=RED + (255,))
        d.rounded_rectangle((4 * k, 4 * k, (bw - 5) * k, (bh - 5) * k), radius=(bh // 2 - 4) * k,
                            outline=(255, 210, 150, 160), width=2 * k)
    box = supersample(bw, bh, draw)
    box.alpha_composite(t, ((bw - t.width) // 2, (bh - t.height) // 2))
    sh = Image.new("RGBA", (bw + 40, bh + 40), (0, 0, 0, 0))
    m = Image.new("L", sh.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((20, 26, bw + 20, bh + 26), radius=bh // 2, fill=150)
    sh.putalpha(m.filter(ImageFilter.GaussianBlur(10)))
    sh.alpha_composite(box, (20, 20))
    return sh


def make_info_box(text, size=58):
    t = text_spr(text, FONT_OS, size, 650, gold=True, shadow=False)
    bw, bh = t.width + 50, t.height + 10

    def draw(d, k, im):
        d.rounded_rectangle((2 * k, 2 * k, (bw - 2) * k, (bh - 2) * k), radius=18 * k,
                            fill=(8, 36, 22, 230), outline=GOLD + (220,), width=3 * k)
    box = supersample(bw, bh, draw)
    box.alpha_composite(t, ((bw - t.width) // 2, (bh - t.height) // 2))
    return box


# ---------------------------------------------------------------- illustrations
def shadow_ellipse(w, h, a=150):
    im = Image.new("RGBA", (w + 80, h + 80), (0, 0, 0, 0))
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).ellipse((40, 40, w + 40, h + 40), fill=a)
    im.putalpha(m.filter(ImageFilter.GaussianBlur(18)))
    return im


def make_puzzle():
    S, r, m = 210, 34, 40
    size = 2 * S + 2 * m
    colors = {(0, 0): (205, 60, 52), (0, 1): (236, 182, 60), (1, 0): (46, 140, 76), (1, 1): (56, 112, 186)}
    k = 3
    masks = {}
    for (i, j) in colors:
        mk = Image.new("L", (size * k, size * k), 0)
        ImageDraw.Draw(mk).rectangle(((m + j * S) * k, (m + i * S) * k, (m + (j + 1) * S) * k, (m + (i + 1) * S) * k), fill=255)
        masks[(i, j)] = mk

    def circ(cx, cy):
        return ((cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k)
    # knobs: left->right and top->bottom
    for i in range(2):
        cx, cy = m + S + r * 0.55, m + i * S + S / 2
        ImageDraw.Draw(masks[(i, 0)]).ellipse(circ(cx, cy), fill=255)
        ImageDraw.Draw(masks[(i, 1)]).ellipse(circ(cx, cy), fill=0)
    for j in range(2):
        cx, cy = m + j * S + S / 2, m + S + r * 0.55
        ImageDraw.Draw(masks[(0, j)]).ellipse(circ(cx, cy), fill=255)
        ImageDraw.Draw(masks[(1, j)]).ellipse(circ(cx, cy), fill=0)
    pieces = {}
    for key, col in colors.items():
        mk = masks[key].filter(ImageFilter.MinFilter(9)).resize((size, size), Image.LANCZOS)
        light = tuple(min(255, int(c * 1.25)) for c in col)
        dark = tuple(int(c * 0.7) for c in col)
        p = gradient_fill(mk, light, dark)
        edge = mk.filter(ImageFilter.GaussianBlur(4))
        inner = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        inner.putalpha(Image.fromarray(np.clip(np.array(mk, np.int16) - np.array(edge, np.int16), 0, 255).astype(np.uint8)).point(lambda v: v * 2))
        p.alpha_composite(inner)
        pieces[key] = p
    return pieces, size


def make_block(letter, size=160, lit=False, letter_color=None):
    top_h = int(size * 0.16)

    def draw(d, k, im):
        s = size
        face = (255, 236, 196, 255) if lit else (226, 190, 138, 255)
        d.polygon([(0, top_h * k), (top_h * k, 0), ((s - 1) * k, 0), ((s - 1 - top_h) * k, top_h * k)],
                  fill=(255, 244, 214, 255) if lit else (246, 222, 180, 255))
        d.rounded_rectangle((0, top_h * k, (s - top_h) * k, (s - 1) * k), radius=10 * k,
                            fill=face, outline=(176, 132, 82, 255), width=3 * k)
        d.polygon([((s - top_h) * k, top_h * k), ((s - 1) * k, 0), ((s - 1) * k, (s - top_h) * k),
                   ((s - top_h) * k, (s - 1) * k)], fill=(190, 150, 100, 255))
        if lit:
            d.rounded_rectangle((6 * k, (top_h + 6) * k, (s - top_h - 6) * k, (s - 7) * k), radius=8 * k,
                                outline=GOLD + (255,), width=4 * k)
    blk = supersample(size, size, draw)
    face_w = size - top_h
    if lit:
        t = text_spr(letter, FONT_PF, int(size * 0.62), 800, (14, 84, 40), shadow=False)
    else:
        t = text_spr(letter, FONT_PF, int(size * 0.62), 800, letter_color or (26, 110, 56), shadow=False)
    blk.alpha_composite(t, ((face_w - t.width) // 2, top_h + (size - top_h - t.height) // 2))
    return blk


def make_card_back(w=168, h=226):
    def draw(d, k, im):
        d.rounded_rectangle((0, 0, (w - 1) * k, (h - 1) * k), radius=16 * k, fill=(22, 96, 54, 255),
                            outline=GOLD + (255,), width=4 * k)
        d.rounded_rectangle((14 * k, 14 * k, (w - 15) * k, (h - 15) * k), radius=10 * k,
                            outline=GOLD + (160,), width=2 * k)
        for yy in range(40, h - 30, 36):
            for xx in range(38, w - 30, 46):
                d.ellipse(((xx - 4) * k, (yy - 4) * k, (xx + 4) * k, (yy + 4) * k), fill=GOLD + (200,))
    return supersample(w, h, draw)


def star_points(cx, cy, R, r, n=5, rot=-90):
    pts = []
    for i in range(2 * n):
        ang = math.radians(rot + i * 180 / n)
        rad = R if i % 2 == 0 else r
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    return pts


def heart_points(cx, cy, s, n=120):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * s, cy - y * s))
    return pts


def make_card_front(kind, w=168, h=226):
    def draw(d, k, im):
        d.rounded_rectangle((0, 0, (w - 1) * k, (h - 1) * k), radius=16 * k, fill=(252, 244, 226, 255),
                            outline=GOLD + (255,), width=4 * k)
        cx, cy = w / 2 * k, h / 2 * k
        if kind == "star":
            d.polygon(star_points(cx, cy, 52 * k, 22 * k), fill=GOLD + (255,))
        else:
            d.polygon(heart_points(cx, cy + 4 * k, 3.2 * k), fill=RED + (255,))
    return supersample(w, h, draw)


def make_bead(color, d=44):
    def draw(dr, k, im):
        dr.ellipse((0, 0, (d - 1) * k, (d - 1) * k), fill=color + (255,))
        dr.ellipse((d * 0.18 * k, d * 0.12 * k, d * 0.55 * k, d * 0.42 * k), fill=(255, 255, 255, 110))
    return supersample(d, d, draw)


def make_abacus_frame(w=620, h=250):
    def draw(d, k, im):
        d.rounded_rectangle((0, 0, (w - 1) * k, (h - 1) * k), radius=14 * k, outline=(150, 100, 52, 255), width=18 * k)
        for i in range(3):
            y = (60 + i * 65) * k
            d.line((18 * k, y, (w - 18) * k, y), fill=(200, 180, 140, 255), width=5 * k)
    return supersample(w, h, draw)


def make_table():
    tw, th = 740, 780

    def draw(d, k, im):
        d.rounded_rectangle((0, 0, (tw - 1) * k, (th - 1) * k), radius=30 * k, fill=(104, 66, 36, 255))
        d.rounded_rectangle((20 * k, 20 * k, (tw - 21) * k, (th - 21) * k), radius=20 * k, fill=(22, 86, 50, 255))
        d.rounded_rectangle((44 * k, 44 * k, (tw - 45) * k, (th - 45) * k), radius=14 * k,
                            outline=GOLD + (200,), width=3 * k)
        d.rounded_rectangle((56 * k, 56 * k, (tw - 57) * k, (th - 57) * k), radius=12 * k,
                            outline=GOLD + (110,), width=2 * k)
        for (x, y) in [(80, 80), (tw - 80, 80), (80, th - 80), (tw - 80, th - 80)]:
            d.ellipse(((x - 22) * k, (y - 22) * k, (x + 22) * k, (y + 22) * k), fill=(196, 34, 44, 255))
            d.ellipse(((x - 12) * k, (y - 16) * k, (x - 2) * k, (y - 6) * k), fill=(255, 255, 255, 120))
        for (x, y) in [(tw / 2, 150), (tw / 2, th - 150)]:
            d.ellipse(((x - 26) * k, (y - 26) * k, (x + 26) * k, (y + 26) * k), fill=(250, 238, 210, 255),
                      outline=(220, 190, 140, 255), width=3 * k)
            d.ellipse(((x - 7) * k, (y - 7) * k, (x + 7) * k, (y + 7) * k), fill=(255, 190, 70, 255))
    return supersample(tw, th, draw), tw, th


PLATE_POS = [(-170, -240), (170, -240), (-170, 0), (170, 0), (-170, 240), (170, 240)]
CANDLE_POS = [(0, -240), (0, 240)]


def make_plate(r=100):
    def draw(d, k, im):
        d.ellipse((0, 0, (2 * r - 1) * k, (2 * r - 1) * k), fill=(250, 250, 246, 255), outline=(210, 205, 196, 255), width=3 * k)
        d.ellipse((22 * k, 22 * k, (2 * r - 23) * k, (2 * r - 23) * k), outline=(222, 218, 208, 255), width=3 * k)
    return supersample(2 * r, 2 * r, draw)


def make_food(variant, r=100):
    rnd = random.Random(variant * 7 + 3)

    def draw(d, k, im):
        c = r
        if variant == 0:  # riz + sauce
            d.ellipse(((c - 60) * k, (c - 52) * k, (c + 30) * k, (c + 48) * k), fill=(246, 238, 214, 255))
            for _ in range(70):
                x, y = rnd.uniform(c - 52, c + 22), rnd.uniform(c - 42, c + 38)
                d.ellipse(((x - 3) * k, (y - 1.5) * k, (x + 3) * k, (y + 1.5) * k), fill=(255, 252, 240, 255))
            d.ellipse(((c - 6) * k, (c - 40) * k, (c + 62) * k, (c + 40) * k), fill=(196, 72, 34, 255))
            d.ellipse(((c + 10) * k, (c - 22) * k, (c + 30) * k, (c - 6) * k), fill=(120, 70, 40, 255))
            d.ellipse(((c + 26) * k, (c + 2) * k, (c + 46) * k, (c + 20) * k), fill=(120, 70, 40, 255))
        elif variant == 1:  # poulet + légumes
            for (x, y) in [(c - 22, c - 10), (c + 18, c + 14)]:
                d.ellipse(((x - 36) * k, (y - 24) * k, (x + 36) * k, (y + 24) * k), fill=(178, 104, 46, 255))
                d.ellipse(((x - 24) * k, (y - 14) * k, (x + 8) * k, (y + 2) * k), fill=(214, 146, 70, 255))
            for _ in range(9):
                x, y = rnd.uniform(c - 60, c + 60), rnd.uniform(c - 60, c + 60)
                if (x - c) ** 2 + (y - c) ** 2 > 68 ** 2:
                    continue
                d.ellipse(((x - 9) * k, (y - 9) * k, (x + 9) * k, (y + 9) * k), fill=rnd.choice([(60, 150, 60, 255), (240, 130, 40, 255)]))
        else:  # fruits
            for _ in range(7):
                a = rnd.uniform(0, 2 * math.pi)
                rr = rnd.uniform(0, 40)
                x, y = c + rr * math.cos(a), c + rr * math.sin(a)
                col = rnd.choice([(245, 150, 30), (250, 200, 40), (200, 40, 50), (120, 180, 60)])
                d.ellipse(((x - 20) * k, (y - 20) * k, (x + 20) * k, (y + 20) * k), fill=col + (255,))
                d.ellipse(((x - 12) * k, (y - 14) * k, (x - 4) * k, (y - 6) * k), fill=(255, 255, 255, 120))
    return supersample(2 * r, 2 * r, draw)


def make_ring(r, width=6, color=GOLD_L):
    s = 2 * r + 2 * width

    def draw(d, k, im):
        d.ellipse((width * k / 2, width * k / 2, (s - width / 2) * k, (s - width / 2) * k), outline=color + (255,), width=width * k)
    return supersample(s, s, draw)


def make_gift_parts():
    bw, bh, lw, lh = 420, 330, 460, 104
    pattern_rnd = random.Random(5)

    def body(d, k, im):
        d.rectangle((0, 0, (bw - 1) * k, (bh - 1) * k), fill=(22, 96, 54, 255))
        for yy in range(20, bh, 46):
            for xx in range(20 + (yy // 46 % 2) * 23, bw, 46):
                d.polygon(star_points(xx * k, yy * k, 9 * k, 4 * k), fill=GOLD + (190,))
        d.rectangle((0, 0, (bw - 1) * k, 18 * k), fill=(0, 0, 0, 70))
    body_im = supersample(bw, bh, body)

    def ribbon_v(d, k, im):
        d.rectangle(((bw / 2 - 34) * k, 0, (bw / 2 + 34) * k, (bh - 1) * k), fill=(196, 30, 42, 255))
        d.rectangle(((bw / 2 - 34) * k, 0, (bw / 2 - 24) * k, (bh - 1) * k), fill=(230, 70, 80, 255))
    ribbon_im = supersample(bw, bh, ribbon_v)

    lid_h_total = lh + 170

    def lid(d, k, im):
        y0 = 170
        # noeud
        cx = lw / 2
        for sgn in (-1, 1):
            pts = [(cx * k, (y0 + 6) * k), ((cx + sgn * 120) * k, (y0 - 120) * k),
                   ((cx + sgn * 150) * k, (y0 - 40) * k), ((cx + sgn * 40) * k, (y0 + 4) * k)]
            d.polygon(pts, fill=(196, 30, 42, 255))
            d.line(pts + [pts[0]], fill=(150, 18, 28, 255), width=4 * k)
            d.line([((cx + sgn * 30) * k, (y0 + 8) * k), ((cx + sgn * 90) * k, (y0 + 90) * k)], fill=(196, 30, 42, 255), width=26 * k)
        d.rounded_rectangle((0, y0 * k, (lw - 1) * k, (y0 + lh - 1) * k), radius=8 * k, fill=(28, 112, 62, 255),
                            outline=(16, 70, 40, 255), width=3 * k)
        for xx in range(24, lw, 46):
            d.polygon(star_points(xx * k, (y0 + lh / 2) * k, 9 * k, 4 * k), fill=GOLD + (200,))
        d.rectangle(((lw / 2 - 36) * k, y0 * k, (lw / 2 + 36) * k, (y0 + lh - 1) * k), fill=(196, 30, 42, 255))
        d.ellipse(((cx - 30) * k, (y0 - 26) * k, (cx + 30) * k, (y0 + 28) * k), fill=(210, 40, 52, 255),
                  outline=(150, 18, 28, 255), width=4 * k)
    lid_full = supersample(lw, lid_h_total, lid)
    return body_im, ribbon_im, lid_full, (bw, bh, lw, lh)


def make_rays(size=1300, n=14):
    def draw(d, k, im):
        c = size / 2 * k
        for i in range(n):
            a = 2 * math.pi * i / n
            w = 0.09
            pts = [(c, c), (c + math.cos(a - w) * c, c + math.sin(a - w) * c), (c + math.cos(a + w) * c, c + math.sin(a + w) * c)]
            d.polygon(pts, fill=(255, 214, 120, 90))
    im = supersample(size, size, draw, k=1).filter(ImageFilter.GaussianBlur(14))
    fade = radial(size, (0, 0, 0), 255, 0.8).getchannel("A")
    a = np.array(im.getchannel("A"), np.float32) * np.array(fade, np.float32) / 255
    im.putalpha(Image.fromarray(a.astype(np.uint8)))
    return im


def heart_mask(size):
    m = Image.new("L", (size * 3, size * 3), 0)
    ImageDraw.Draw(m).polygon(heart_points(size * 1.5, size * 1.42, size * 3 / 36), fill=255)
    return m.resize((size, size), Image.LANCZOS)


def make_dashed_circle(r, width=5, dashes=36):
    s = 2 * r + 20

    def draw(d, k, im):
        for i in range(dashes):
            a0 = 360 * i / dashes
            d.arc((10 * k, 10 * k, (s - 10) * k, (s - 10) * k), a0, a0 + 360 / dashes * 0.55, fill=GOLD_L + (255,), width=width * k)
    return supersample(s, s, draw)


# ---------------------------------------------------------------- base scene
class Scene:
    """Éléments communs : fond, lumières, guirlande, compteur, sous-titres, écran de fin."""

    def __init__(self, name, duration, counter, bulbs_before, new_bulb_at, endcard, end_start,
                 captions, bulb_count_total=None, end_badge_scale=1.0):
        self.name = name
        self.duration = duration
        self.counter = counter
        self.bulbs_before = bulbs_before
        self.new_bulb_at = new_bulb_at
        self.endcard = endcard
        self.end_start = end_start
        self.captions = [(a, b, make_caption(txt)) for a, b, txt in captions]
        self.end_badge_scale = end_badge_scale
        self.bg = make_background()
        self.bokeh1 = make_bokeh(11, 70, 14, 60, 60, 150, 7)
        self.bokeh2 = make_bokeh(23, 26, 60, 140, 25, 70, 16)
        self.vignette = make_vignette()
        self.garland = make_garland()
        self.lit = make_lit_bulb()
        self.glow = radial(380, (255, 190, 80), 170, 2.2)
        self.counter_spr = text_spr(counter, FONT_PF, 330, 900, gold=True, glow=18)
        self.counter_sub = text_spr("NOËL DE L'ESPOIR 2026", FONT_OS, 50, 500, CREAM)
        self.cta = make_cta()
        self.badge30 = make_badge("AVANT LE 30 NOVEMBRE")
        self._build_endcard()

    # -- background
    def draw_bg(self, t):
        fr = self.bg.copy()
        dx = 120 + 70 * math.sin(2 * math.pi * t / 22)
        dy = 120 + 70 * math.cos(2 * math.pi * t / 26)
        fr.alpha_composite(self.bokeh2.crop((int(dx * 0.6), int(dy * 0.6), int(dx * 0.6) + W, int(dy * 0.6) + H)))
        fr.alpha_composite(self.bokeh1.crop((int(dx), int(240 - dy), int(dx) + W, int(240 - dy) + H)))
        fr.alpha_composite(self.vignette)
        return fr

    def bulbs_on(self, t):
        out = []
        for i in range(5):
            if i < self.bulbs_before:
                out.append(1.0)
            elif i == self.bulbs_before and self.new_bulb_at is not None:
                out.append(ease_out(ramp(t, self.new_bulb_at, self.new_bulb_at + 0.3)))
            else:
                out.append(0.0)
        return out

    def draw_garland(self, fr, t, boost=1.0):
        fr.alpha_composite(self.garland, (0, 0))
        for i, a in enumerate(self.bulbs_on(t)):
            if a <= 0:
                continue
            flick = 0.92 + 0.08 * math.sin(t * 7.3 + i * 1.7) * math.sin(t * 3.1 + i)
            bx = BULB_X[i]
            cy = wire_y(bx) + 84
            paste(fr, self.glow, bx, cy, scale=1.0 + 0.15 * (boost - 1), alpha=a * flick * min(1.0, 0.9 * boost))
            paste(fr, self.lit, bx, cy - 2, alpha=a)

    def draw_counter(self, fr, t, start=0.1, end=2.15):
        a = window(t, start, end, 0.45, 0.35)
        if a <= 0:
            return
        sc = 0.86 + 0.14 * ease_out(ramp(t, start, start + 0.7)) + 0.03 * ramp(t, 0.8, end)
        paste(fr, self.counter_spr, W / 2, 930, scale=sc, alpha=a)
        paste(fr, self.counter_sub, W / 2, 1150, alpha=a * ramp(t, start + 0.3, start + 0.8))

    def draw_captions(self, fr, t):
        for a, b, spr in self.captions:
            al = window(t, a, b, 0.2, 0.2)
            if al > 0:
                paste(fr, spr, W / 2, 1545 + 12 * (1 - ease_out(ramp(t, a, a + 0.3))), alpha=al)

    # -- end card
    def _build_endcard(self):
        self.ec_logo = esc_logo(270)
        self.ec_title = text_spr("NOËL DE L'ESPOIR 2026", FONT_PF, 76, 800, gold=True)
        self.ec_partner_lbl = text_spr("PARTENAIRE OFFICIEL", FONT_OS, 34, 500, GOLD_L)
        self.ec_alpha = alpha_card(190)
        place = text_spr("Foyer Dieu Pourvoit – Élavagnon", FONT_OS, 42, 500, CREAM)
        place2 = text_spr("(entre Hihéatro et Témédja)", FONT_OS, 36, 400, (230, 225, 210))
        self.ec_place = stack([place, place2], gap=-38)
        if self.endcard == "A":
            self.ec_items = [
                (990, make_badge("DÉPÔT AVANT LE 30 NOVEMBRE 2026", 44), self.end_badge_scale),
                (1080, text_spr("Point de collecte : écrivez-nous", FONT_OS, 44, 500, CREAM), 1),
                (1142, text_spr(EMAIL, FONT_OS, 46, 600, GOLD_L), 1),
                (1208, text_spr("Tél. " + PHONE, FONT_OS, 46, 500, CREAM), 1),
            ]
        else:
            self.ec_items = [
                (928, text_spr("21 décembre 2026", FONT_OS, 44, 500, CREAM), 1),
                (1012, make_info_box("Mobile Money : " + MOMO, 54), 1),
                (1088, text_spr("Jusqu'au 15 décembre", FONT_OS, 40, 500, CREAM), 1),
                (1148, text_spr("Autres moyens : " + EMAIL, FONT_OS, 36, 500, GOLD_L), 1),
                (1208, text_spr("Tél. " + PHONE, FONT_OS, 44, 500, CREAM), 1),
            ]

    def draw_endcard(self, fr, t):
        t0 = self.end_start
        if t < t0 - 0.05:
            return
        def ap(d):
            return ease_out(ramp(t, t0 + d, t0 + d + 0.45))
        paste(fr, self.ec_logo, W / 2, 615, scale=0.9 + 0.1 * ap(0), alpha=ap(0))
        paste(fr, self.ec_title, W / 2, 830 + 20 * (1 - ap(0.12)), alpha=ap(0.12))
        for i, (y, spr, sc) in enumerate(self.ec_items):
            d = 0.22 + 0.08 * i
            paste(fr, spr, W / 2, y + 18 * (1 - ap(d)), scale=sc, alpha=ap(d))
        paste(fr, self.ec_place, W / 2, 1290, alpha=ap(0.6))
        a = ap(0.75)
        ImageDraw.Draw(fr).line((W / 2 - 260 * a, 1372, W / 2 + 260 * a, 1372), fill=GOLD + (int(200 * a),), width=2)
        paste(fr, self.ec_partner_lbl, W / 2, 1410, alpha=a)
        paste(fr, self.ec_alpha, W / 2, 1552, scale=0.92 + 0.08 * a, alpha=a)

    # -- to override
    def draw_stage(self, fr, t):
        pass

    def stage_alpha(self, t):
        return 1 - ramp(t, self.end_start - 0.4, self.end_start)

    def frame(self, t):
        fr = self.draw_bg(t)
        self.draw_garland(fr, t, boost=self.garland_boost(t))
        self.draw_counter(fr, t)
        sa = self.stage_alpha(t)
        if sa > 0:
            if sa < 1:
                layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                self.draw_stage(layer, t)
                fr.alpha_composite(with_alpha(layer, sa))
            else:
                self.draw_stage(fr, t)
        self.draw_captions(fr, t)
        self.draw_endcard(fr, t)
        self.overlay(fr, t)
        return fr

    def garland_boost(self, t):
        return 1.0

    def overlay(self, fr, t):
        pass

    def flash(self, fr, t, at, peak=0.55, dur=0.5, color=(255, 226, 150)):
        a = max(0.0, 1 - abs(t - at) / (dur / 2)) * peak
        if a > 0:
            fr.alpha_composite(Image.new("RGBA", (W, H), color + (int(255 * a),)))

    def draw_cta(self, fr, t, at, y=1300, spr=None):
        a = ease_out(ramp(t, at, at + 0.4))
        if a > 0:
            sc = 0.8 + 0.2 * ease_back(ramp(t, at, at + 0.5))
            paste(fr, spr or self.cta, W / 2, y, scale=sc, alpha=a)

    def draw_badge(self, fr, t, at, y, spr=None, scale=1.0):
        a = ramp(t, at, at + 0.15)
        if a > 0:
            sc = scale * (0.3 + 0.7 * ease_back(ramp(t, at, at + 0.45)))
            paste(fr, spr or self.badge30, W / 2, y, scale=sc, alpha=a, rot=3)


# ---------------------------------------------------------------- capsule 1
class C1(Scene):
    def __init__(self):
        super().__init__("C1_J-26_jeux-educatifs", 20.0, "J-26", 0, 1.5, "A", 16.0, [
            (2.2, 5.0, "Un puzzle… des lettres…"),
            (5.0, 8.0, "…un jeu de mémoire…"),
            (8.2, 12.0, "Un jeu éducatif, c'est un rire… et une leçon."),
            (12.2, 15.9, "Offrez-le avant le 30 novembre. Soyez leur espoir de Noël."),
        ])
        self.pieces, self.psize = make_puzzle()
        self.abc = [make_block(c, 170, letter_color=col) for c, col in
                    [("A", (200, 40, 50)), ("B", (26, 110, 56)), ("C", (50, 100, 180))]]
        self.cback = make_card_back()
        self.cfronts = [make_card_front(k) for k in ["star", "heart", "heart", "star", "star", "heart"]]
        self.frame_ab = make_abacus_frame()
        self.beads = [make_bead(c) for c in [(205, 50, 50), (236, 186, 50), (46, 140, 76)]]
        self.esp = [make_block(c, 150) for c in "ESPOIR"]
        self.esp_lit = [make_block(c, 150, lit=True) for c in "ESPOIR"]
        self.info = text_spr("Jeux éducatifs, neufs ou en bon état", FONT_OS, 52, 500, CREAM)
        self.shadow = shadow_ellipse(520, 70)
        self.glow_big = radial(1100, (255, 196, 90), 120, 1.6)

    def draw_stage(self, fr, t):
        # scène 1 : puzzle + cubes (2–5,3 s)
        a1 = window(t, 2.0, 5.3, 0.35, 0.35)
        if a1 > 0:
            cx, cy = 450, 860
            zoom = 1.0 + 0.04 * ramp(t, 2, 5.3)
            paste(fr, self.shadow, cx, cy + 250, alpha=a1 * 0.8)
            for key, p in self.pieces.items():
                ox, oy = 0, 0
                if key == (1, 1):
                    s = ease_out(ramp(t, 2.3, 3.4))
                    ox, oy = (1 - s) * 260, (1 - s) * 200
                paste(fr, p, cx + ox, cy + oy, scale=zoom, alpha=a1)
            for i, (bx, by) in enumerate([(300, 1240), (520, 1260), (760, 1230)]):
                p = ease_back(ramp(t, 2.7 + 0.25 * i, 3.2 + 0.25 * i))
                paste(fr, self.abc[i], bx, by, scale=max(0.01, p), alpha=a1 * ramp(t, 2.7 + 0.25 * i, 2.9 + 0.25 * i))
        # scène 2 : mémoire + boulier (5–8 s)
        a2 = window(t, 5.0, 8.1, 0.35, 0.15)
        if a2 > 0:
            gx = [540 - 192, 540, 540 + 192]
            gy = [690, 940]
            for idx in range(6):
                x, y = gx[idx % 3], gy[idx // 3]
                p = ramp(t, 5.35 + 0.22 * idx, 5.75 + 0.22 * idx)
                sx = abs(math.cos(math.pi * p))
                face = self.cfronts[idx] if p > 0.5 else self.cback
                f2 = face.resize((max(1, int(face.width * sx)), face.height), Image.BILINEAR)
                paste(fr, f2, x - 140 * (1 - ease_out(ramp(t, 5.0, 5.6))), y, alpha=a2)
            ax, ay = 540, 1265
            paste(fr, self.frame_ab, ax, ay, alpha=a2)
            for row in range(3):
                for b in range(7):
                    moved = clamp((t - 5.6 - row * 0.3) * 2.2 - (6 - b) * 0.25)
                    x0 = ax + 270 - (6 - b) * 44
                    x1 = ax - 270 + b * 44
                    x = x0 + (x1 - x0) * ease_io(moved)
                    paste(fr, self.beads[row], x, ay - 65 + row * 65, alpha=a2)
        # scène 3 : ESPOIR (8–16 s)
        if t >= 8.0:
            lit = ease_out(ramp(t, 12.0, 12.6))
            zoom = 1.0 + 0.05 * ease_io(ramp(t, 12.0, 16.0))
            if lit > 0:
                paste(fr, self.glow_big, W / 2, 860, scale=zoom, alpha=lit * 0.9)
            for i in range(6):
                st = 8.1 + 0.2 * i
                p = ramp(t, st, st + 0.45)
                if p <= 0:
                    continue
                x = W / 2 + (i - 2.5) * 162 * zoom
                y = 860 - 160 * (1 - ease_back(p))
                paste(fr, self.esp[i], x, y, scale=zoom, alpha=min(1, p * 3) * (1 - lit))
                if lit > 0:
                    paste(fr, self.esp_lit[i], x, y, scale=zoom, alpha=lit)
            paste(fr, self.info, W / 2, 1050, alpha=window(t, 9.4, 12.2, 0.4, 0.3))
            self.draw_badge(fr, t, 12.3, 1085)
            self.draw_cta(fr, t, 13.2, 1265)

    def overlay(self, fr, t):
        self.flash(fr, t, 8.0, 0.5, 0.4)


# ---------------------------------------------------------------- capsule 2
class C2(Scene):
    def __init__(self):
        super().__init__("C2_J-25_denrees", 20.0, "J-25", 1, 1.5, "A", 16.0, [
            (2.2, 6.0, "Noël, c'est aussi une table partagée."),
            (6.2, 12.0, "Vos denrées deviendront des repas chaleureux pour les enfants du foyer."),
            (12.2, 15.9, "Déposez-les avant le 30 novembre. Soyez leur espoir de Noël."),
        ])
        self.table, self.tw, self.th = make_table()
        self.plate = make_plate()
        self.food = [make_food(i % 3) for i in range(6)]
        self.flame = radial(120, (255, 200, 90), 230, 1.8)
        self.basket = load_icon("panier", 190)
        self.ring = make_ring(80)
        self.info = text_spr("Pour offrir des repas chaleureux.", FONT_OS, 54, 500, CREAM)
        self.glow_big = radial(1200, (255, 196, 90), 110, 1.6)
        self.table_layer = None

    def table_image(self, t):
        im = Image.new("RGBA", (self.tw, self.th), (0, 0, 0, 0))
        im.alpha_composite(self.table)
        cx, cy = self.tw / 2, self.th / 2
        for i, (dx, dy) in enumerate(PLATE_POS):
            paste(im, self.plate, cx + dx, cy + dy)
            st = 6.3 + 0.55 * i
            f = ease_out(ramp(t, st, st + 0.35))
            if f > 0:
                paste(im, self.food[i], cx + dx, cy + dy, scale=0.85 + 0.15 * f, alpha=f)
        for j, (dx, dy) in enumerate(CANDLE_POS):
            fl = 0.85 + 0.15 * math.sin(t * 9 + j * 2) * math.sin(t * 4.3)
            paste(im, self.flame, cx + dx, cy + dy, alpha=fl)
        paste(im, self.basket, cx, cy)
        return im

    def table_xform(self, t):
        p = ease_io(ramp(t, 12.0, 12.7))
        sc = 1.0 + 0.03 * ramp(t, 2, 12) - 0.24 * p
        cy = 870 - 70 * p
        return sc, cy

    def draw_stage(self, fr, t):
        a = ease_out(ramp(t, 2.0, 2.6))
        if a <= 0:
            return
        sc, cy = self.table_xform(t)
        lit = ramp(t, 12.0, 12.8)
        if lit > 0:
            paste(fr, self.glow_big, W / 2, cy, alpha=lit * 0.9)
        paste(fr, self.table_image(t), W / 2, cy + 60 * (1 - a), scale=sc, alpha=a, rot=-2 * (1 - a))
        for i, (dx, dy) in enumerate(PLATE_POS):
            st = 6.3 + 0.55 * i
            rp = ramp(t, st, st + 0.6)
            if 0 < rp < 1:
                paste(fr, self.ring, W / 2 + dx * sc, cy + dy * sc, scale=(0.9 + 0.8 * rp) * sc, alpha=1 - rp)
        paste(fr, self.info, W / 2, 1335, alpha=window(t, 8.0, 12.1, 0.4, 0.3))
        self.draw_badge(fr, t, 12.4, 1180)
        self.draw_cta(fr, t, 13.2, 1320)


# ---------------------------------------------------------------- capsule 3
class C3(Scene):
    def __init__(self):
        super().__init__("C3_J-24_cadeaux", 20.0, "J-24", 2, 1.5, "A", 16.0, [
            (2.2, 7.0, "Un cadeau emballé avec amour…"),
            (7.2, 12.0, "…c'est un souvenir qu'un enfant garde longtemps."),
            (12.2, 15.9, "Déposez le vôtre avant le 30 novembre. Soyez leur espoir de Noël."),
        ])
        self.body, self.ribbon, self.lid, (self.bw, self.bh, self.lw, self.lh) = make_gift_parts()
        self.rays = make_rays()
        self.spark = radial(40, (255, 230, 160), 255, 1.4)
        self.glow_big = radial(900, (255, 200, 100), 200, 1.4)
        self.shadow = shadow_ellipse(460, 60)
        self.info = text_spr("Pour créer des souvenirs inoubliables.", FONT_OS, 54, 500, CREAM)
        rnd = random.Random(9)
        self.parts = [(rnd.uniform(7.4, 12.0), rnd.uniform(-170, 170), rnd.uniform(160, 320), rnd.uniform(0, 6.28),
                       rnd.uniform(0.5, 1.1)) for _ in range(70)]

    def draw_stage(self, fr, t):
        p = ease_io(ramp(t, 12.0, 12.7))
        if p > 0:
            # calque deux fois plus grand que l'image pour que les rayons ne soient pas coupés
            layer = Image.new("RGBA", (2 * W, 2 * H), (0, 0, 0, 0))
            self.off = (W / 2, H / 2)
            self.draw_gift(layer, t)
            self.off = (0, 0)
            paste(fr, layer, W / 2, H / 2 - 150 * p - (H / 2 - 900) * 0.3 * p, scale=1 - 0.3 * p)
        else:
            self.draw_gift(fr, t)
        paste(fr, self.info, W / 2, 1335, alpha=window(t, 8.4, 12.1, 0.4, 0.3))
        self.draw_badge(fr, t, 12.8, 1100)
        self.draw_cta(fr, t, 13.3, 1265)

    def draw_gift(self, fr, t):
        a = ease_out(ramp(t, 2.0, 2.6))
        if a <= 0:
            return
        g_alpha = a
        ox, oy = getattr(self, "off", (0, 0))
        cx, top = W / 2 + ox, 900 + oy
        zoom = 1.0 + 0.04 * ramp(t, 2, 12)
        open_p = ease_io(ramp(t, 7.0, 8.2))
        light = ramp(t, 7.1, 8.6)
        if g_alpha > 0:
            paste(fr, self.shadow, cx, top + self.bh + 10, alpha=g_alpha)
            if light > 0:
                paste(fr, self.rays, cx, top - 20, rot=(t * 8) % 360, alpha=light * g_alpha)
                paste(fr, self.glow_big, cx, top, alpha=light * g_alpha * 0.9)
            paste(fr, self.body, cx, top + self.bh / 2 * zoom, scale=zoom, alpha=g_alpha)
            rv = ease_io(ramp(t, 2.4, 3.8))
            if rv > 0:
                h = max(1, int(self.bh * rv))
                rib = self.ribbon.crop((0, 0, self.bw, h))
                paste(fr, rib, cx, top + h / 2 * zoom, scale=zoom, alpha=g_alpha)
            bow = ease_back(ramp(t, 4.0, 4.6))
            lid_y = top - 170 / 2 * zoom + (self.lh / 2) * zoom - 2 - 170 * open_p
            if bow > 0 or True:
                lid = self.lid
                if bow < 1:
                    # nœud qui apparaît : on masque le haut tant qu'il n'est pas là
                    lid = lid.copy()
                    bow_part = lid.crop((0, 0, self.lw, 172))
                    lid.paste((0, 0, 0, 0), (0, 0, self.lw, 172))
                    if bow > 0.01:
                        bp = bow_part.resize((self.lw, max(1, int(172 * max(0.05, bow)))), Image.BILINEAR)
                        lid.alpha_composite(bp, (0, 172 - bp.height))
                paste(fr, lid, cx + 40 * open_p, lid_y, scale=zoom, alpha=g_alpha, rot=-14 * open_p)
        for (b, x, sp, ph, sz) in self.parts:
            age = t - b
            if 0 < age < 2.2:
                y = top - 10 - sp * age
                xx = cx + x * (0.6 + age * 0.3) + 18 * math.sin(ph + age * 3)
                paste(fr, self.spark, xx, y, scale=sz, alpha=(1 - age / 2.2) * a)

    def overlay(self, fr, t):
        self.flash(fr, t, 12.2, 0.55, 0.8)


# ---------------------------------------------------------------- capsule 4
class C4(Scene):
    def __init__(self):
        super().__init__("C4_J-23_partenariats", 20.0, "J-23", 3, 1.5, "B", 16.0, [
            (2.2, 7.0, "Entreprises, associations, institutions : le Noël de l'Espoir se construit ensemble."),
            (7.2, 12.0, "Aux côtés d'AlphaSignal, notre partenaire officiel… rejoignez-nous."),
        ])
        rnd = random.Random(4)
        nodes = []
        while len(nodes) < 28:
            x, y = rnd.uniform(110, 970), rnd.uniform(520, 1250)
            if ((x - 540) / 440) ** 2 + ((y - 880) / 380) ** 2 > 1:
                continue
            if all((x - a) ** 2 + (y - b) ** 2 > 120 ** 2 for a, b in nodes):
                nodes.append((x, y))
        self.nodes = nodes
        edges = set()
        for i, (x, y) in enumerate(nodes):
            near = sorted(range(len(nodes)), key=lambda j: (nodes[j][0] - x) ** 2 + (nodes[j][1] - y) ** 2)[1:4]
            for j in near:
                edges.add(tuple(sorted((i, j))))
        self.edges = edges

        def draw(d, k, im):
            for i, j in edges:
                d.line((nodes[i][0] * k, nodes[i][1] * k, nodes[j][0] * k, nodes[j][1] * k), fill=GOLD_L + (170,), width=3 * k)
        lines = supersample(W, H, draw, k=2)
        glow = lines.filter(ImageFilter.GaussianBlur(8))
        self.net = Image.alpha_composite(glow, lines)
        self.net_glow = lines.filter(ImageFilter.GaussianBlur(16))
        yy, xx = np.mgrid[0:H, 0:W]
        self.dist = np.sqrt((xx - 540) ** 2 + (yy - 880) ** 2).astype(np.float32)
        self.node_spr = radial(56, (255, 220, 140), 255, 1.2)
        self.hand = load_icon("poignee", 250)
        self.alpha = alpha_disc(300)
        self.empty = make_dashed_circle(132)
        self.etvous = text_spr("Et vous ?", FONT_PF, 46, 800, gold=True)
        self.lbl = text_spr("Partenaire officiel", FONT_OS, 40, 500, GOLD_L)
        self.info = text_spr("Entreprises · Associations · Institutions", FONT_OS, 50, 500, CREAM)
        self.cta_b = make_cta("ENSEMBLE, ALLONS PLUS LOIN.", star=True, size=60)

    def net_image(self, r, glow_a):
        a = np.array(self.net.getchannel("A"), np.float32)
        m = np.clip((r - self.dist) / 120, 0, 1)
        im = self.net.copy()
        im.putalpha(Image.fromarray((a * m).astype(np.uint8)))
        return im

    def draw_stage(self, fr, t):
        r = 60 + 720 * ease_out(ramp(t, 2.0, 6.5))
        dim = 1 - 0.6 * ramp(t, 7.0, 7.6) + 0.6 * ramp(t, 12.0, 12.6)
        if t > 2.0:
            paste(fr, self.net_image(r, 0), W / 2, H / 2, alpha=dim)
            if t > 12.0:
                paste(fr, self.net_glow, W / 2, H / 2, alpha=ramp(t, 12.0, 12.6) * (0.8 + 0.2 * math.sin(t * 5)))
            for i, (x, y) in enumerate(self.nodes):
                d = math.hypot(x - 540, y - 880)
                na = clamp((r - d) / 60)
                if na > 0:
                    pulse = 0.85 + 0.15 * math.sin(t * 4 + i)
                    paste(fr, self.node_spr, x, y, scale=pulse, alpha=na * dim)
        ha = window(t, 2.1, 7.2, 0.4, 0.4)
        if ha > 0:
            paste(fr, self.hand, 540, 880, scale=0.6 + 0.4 * ease_back(ramp(t, 2.1, 2.7)), alpha=ha)
        paste(fr, self.info, W / 2, 1335, alpha=window(t, 2.8, 7.0, 0.4, 0.3))
        # AlphaSignal + "Et vous ?"
        pa = ease_back(ramp(t, 7.2, 7.8))
        if pa > 0:
            la = ramp(t, 8.0, 8.5)
            d = ImageDraw.Draw(fr)
            x0, x1 = 360 + 150, 760 - 130
            if la > 0:
                d.line((x0, 870, x0 + (x1 - x0) * la, 870), fill=GOLD_L + (230,), width=5)
            paste(fr, self.alpha, 360, 870, scale=max(0.01, pa), alpha=ramp(t, 7.2, 7.4))
            paste(fr, self.lbl, 360, 1065, alpha=ramp(t, 7.6, 8.0))
            ea = ease_back(ramp(t, 8.3, 8.9))
            if ea > 0:
                pulse = 1 + 0.04 * math.sin(t * 5)
                paste(fr, self.empty, 760, 870, scale=ea * pulse, alpha=ramp(t, 8.3, 8.5))
                paste(fr, self.etvous, 760, 870, scale=ea, alpha=ramp(t, 8.5, 8.8))
        self.draw_cta(fr, t, 12.6, 1300, self.cta_b)


# ---------------------------------------------------------------- capsule 5
class C5(Scene):
    def __init__(self, counter, first_line, name):
        super().__init__(name, 20.0, counter, 4, 1.5, "B", 16.0, [
            (2.2, 7.0, first_line),
            (7.2, 12.0, "Chaque contribution compte. Même petite, votre générosité change des vies."),
            (12.2, 15.9, "Offrons un sourire à chaque orphelin. Soyez leur espoir de Noël."),
        ])
        self.medal = load_icon("coeur_main", 380)
        self.title = text_spr("NOËL DE L'ESPOIR 2026", FONT_PF, 76, 800, gold=True)
        self.spark = radial(40, (255, 230, 160), 255, 1.4)
        self.hs = 520
        self.hmask = np.array(heart_mask(self.hs), np.float32) / 255
        yy, xx = np.mgrid[0:self.hs, 0:self.hs]
        self.hy, self.hx = yy.astype(np.float32), xx.astype(np.float32)
        g = np.linspace(0, 1, self.hs)[:, None]
        self.gold_rgb = (np.array((255, 222, 130)) * (1 - g[..., None]) + np.array((200, 140, 30)) * g[..., None]).repeat(self.hs, 1)
        hm = Image.fromarray((self.hmask * 255).astype(np.uint8))
        glass = Image.new("RGBA", (self.hs, self.hs), (255, 255, 255, 0))
        glass.putalpha(hm.point(lambda v: int(v * 0.16)))
        edge = Image.fromarray(np.clip(np.array(hm, np.int16) - np.array(hm.filter(ImageFilter.MinFilter(9)), np.int16), 0, 255).astype(np.uint8))
        rim = Image.new("RGBA", (self.hs, self.hs), (255, 255, 255, 0))
        rim.putalpha(edge.point(lambda v: int(v * 0.8)))
        hl = Image.new("L", (self.hs, self.hs), 0)
        ImageDraw.Draw(hl).ellipse((120, 110, 210, 230), fill=120)
        hl = hl.filter(ImageFilter.GaussianBlur(18))
        shine = Image.new("RGBA", (self.hs, self.hs), (255, 255, 255, 0))
        shine.putalpha(Image.fromarray((np.array(hl, np.float32) * self.hmask).astype(np.uint8)))
        self.glass, self.rim, self.shine = glass, rim, shine
        self.heart_glow = radial(900, (255, 196, 90), 160, 1.6)
        self.momo = make_info_box("Mobile Money : " + MOMO, 58)
        self.until = text_spr("Jusqu'au 15 décembre", FONT_OS, 42, 500, CREAM)
        self.big1 = text_spr("UN SOURIRE POUR", FONT_PF, 92, 800, gold=True, glow=4)
        self.big2 = text_spr("CHAQUE ORPHELIN", FONT_PF, 92, 800, gold=True, glow=4)
        rnd = random.Random(12)
        self.rise = [(rnd.uniform(2.0, 7.0), rnd.uniform(140, 940), rnd.uniform(120, 260), rnd.uniform(0.4, 1.0), rnd.uniform(0, 6)) for _ in range(60)]
        self.orbs = [(7.3 + i * 0.16, rnd.uniform(-140, 140), rnd.uniform(0.6, 1.0)) for i in range(28)]
        self.burst = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(400, 900), rnd.uniform(0.5, 1.2)) for _ in range(80)]

    def garland_boost(self, t):
        return 1.0 + 0.5 * ease_out(ramp(t, 1.5, 2.0)) * (1 - ramp(t, 2.0, 4.0))

    def level(self, t):
        return self.hs * (0.95 - 0.78 * ease_io(ramp(t, 7.3, 11.8)))

    def heart_image(self, t):
        lv = self.level(t)
        wave = 7 * np.sin(self.hx / 38 + t * 4)
        fill = (self.hy > (lv + wave)).astype(np.float32) * self.hmask
        arr = np.zeros((self.hs, self.hs, 4), np.uint8)
        arr[..., :3] = self.gold_rgb.astype(np.uint8)
        arr[..., 3] = (fill * 245).astype(np.uint8)
        im = self.glass.copy()
        im.alpha_composite(Image.fromarray(arr, "RGBA"))
        im.alpha_composite(self.rim)
        im.alpha_composite(self.shine)
        return im

    def draw_stage(self, fr, t):
        # partie 1 : médaillon de l'affiche + particules
        ma = window(t, 2.0, 7.2, 0.4, 0.4)
        for (b, x, sp, sz, ph) in self.rise:
            age = t - b
            if 0 < age < 3 and t < 7.3:
                paste(fr, self.spark, x + 20 * math.sin(ph + age * 2), 1350 - sp * age * 1.6, scale=sz, alpha=(1 - age / 3) * ma)
        if ma > 0:
            paste(fr, self.medal, W / 2, 840, scale=0.7 + 0.3 * ease_back(ramp(t, 2.0, 2.6)), alpha=ma)
            paste(fr, self.title, W / 2, 1150, alpha=window(t, 2.6, 7.2, 0.4, 0.4))
        # partie 2 : cœur de verre qui se remplit
        hc = (W / 2, 820)
        ha = ramp(t, 7.0, 7.5) * (1 - ramp(t, 12.4, 12.9))
        if ha > 0:
            sc = 1.0 + 0.15 * ease_out(ramp(t, 12.0, 12.5))
            paste(fr, self.heart_glow, hc[0], hc[1], alpha=ha * (0.35 + 0.65 * ramp(t, 8, 12)))
            paste(fr, self.heart_image(t), hc[0], hc[1], scale=sc, alpha=ha)
            lv_abs = hc[1] - self.hs / 2 + self.level(t)
            for (b, dx, sz) in self.orbs:
                age = t - b
                y = 300 + 900 * age
                if 0 < age and y < lv_abs:
                    paste(fr, self.spark, hc[0] + dx, y, scale=sz * 1.3, alpha=min(1, age * 4) * ha)
        # boîte Mobile Money
        mp = ease_io(ramp(t, 12.4, 13.0))
        my = 1260 - 200 * mp
        paste(fr, self.momo, W / 2, my, scale=0.85 + 0.15 * ease_back(ramp(t, 7.6, 8.1)), alpha=ramp(t, 7.6, 7.9))
        paste(fr, self.until, W / 2, my + 80, alpha=ramp(t, 8.0, 8.4))
        # partie 3 : éclat + titre
        for (ang, sp, sz) in self.burst:
            age = t - 12.4
            if 0 < age < 1.6:
                d = sp * ease_out(age / 1.6)
                paste(fr, self.spark, hc[0] + math.cos(ang) * d, hc[1] + math.sin(ang) * d, scale=sz * 1.4, alpha=1 - age / 1.6)
        ta = ease_out(ramp(t, 12.7, 13.2))
        if ta > 0:
            paste(fr, self.big1, W / 2, 720 + 20 * (1 - ta), alpha=ta)
            paste(fr, self.big2, W / 2, 840 + 20 * (1 - ta), alpha=ease_out(ramp(t, 12.9, 13.4)))
        self.draw_cta(fr, t, 13.4, 1260)

    def overlay(self, fr, t):
        self.flash(fr, t, 12.4, 0.6, 0.5)


# ---------------------------------------------------------------- rappel
class Rappel(Scene):
    def __init__(self):
        super().__init__("Rappel_J-22_dons-en-nature", 10.0, "J-22", 4, None, "A", 6.0, [
            (1.5, 3.4, "Plus que deux jours pour vos dons en nature."),
            (3.4, 5.95, "Jeux éducatifs, denrées, cadeaux : déposez-les avant le 30 novembre."),
        ], end_badge_scale=1.12)
        self.c1 = C1.__new__(C1)
        self.esp_lit = [make_block(c, 150, lit=True) for c in "ESPOIR"]
        self.glow_big = radial(1100, (255, 196, 90), 120, 1.6)
        self.big = text_spr("PLUS QUE 2 JOURS", FONT_PF, 104, 800, gold=True, glow=4)
        self.c2 = C2()
        self.c3 = C3()
        self.cats = text_spr("Jeux éducatifs · Denrées · Cadeaux", FONT_OS, 54, 600, CREAM)

    def draw_counter(self, fr, t, start=0.0, end=1.5):
        if t >= 1.5:
            return
        blink = 1.0 if t < 0.6 or t > 0.9 else 0.35
        sc = 1.0 + 0.04 * t
        paste(fr, self.counter_spr, W / 2, 930, scale=sc, alpha=blink)
        paste(fr, self.counter_sub, W / 2, 1150, alpha=blink)

    def draw_stage(self, fr, t):
        if 1.5 <= t < 3.0:
            paste(fr, self.glow_big, W / 2, 820, alpha=0.9)
            for i in range(6):
                paste(fr, self.esp_lit[i], W / 2 + (i - 2.5) * 162, 820)
            pulse = 1 + 0.05 * math.sin((t - 1.5) * 8)
            paste(fr, self.big, W / 2, 1120, scale=pulse)
        elif 3.0 <= t < 4.5:
            paste(fr, self.c2.table_image(20.0), W / 2, 850, scale=0.82)
            paste(fr, self.cats, W / 2, 1360)
        elif 4.5 <= t < 6.0:
            c3, tt = self.c3, 9.0 + (t - 4.5)
            paste(fr, c3.rays, W / 2, 880, rot=(tt * 8) % 360)
            paste(fr, c3.glow_big, W / 2, 900, alpha=0.9)
            paste(fr, c3.body, W / 2, 900 + c3.bh / 2)
            paste(fr, c3.ribbon, W / 2, 900 + c3.bh / 2)
            paste(fr, c3.lid, W / 2 + 40, 900 - 85 + c3.lh / 2 - 2 - 170, rot=-14)
            paste(fr, self.cats, W / 2, 1360)

    def stage_alpha(self, t):
        return 1.0 if t < 6.0 else 0.0

    def overlay(self, fr, t):
        for at in (1.5, 3.0, 4.5):
            self.flash(fr, t, at, 0.35, 0.16)


SCENES = {
    "c1": C1,
    "c2": C2,
    "c3": C3,
    "c4": C4,
    "rappel": Rappel,
    "c5_j20": lambda: C5("J-20", "Le 21 décembre, c'est Noël au Foyer Dieu Pourvoit.", "C5_J-20_dons-financiers"),
    "c5_j13": lambda: C5("J-13", "Le 21 décembre, c'est Noël au Foyer Dieu Pourvoit.", "C5_J-13_dons-financiers"),
    "c5_j7": lambda: C5("J-7", "Dernier jour demain pour vos dons.", "C5_J-7_dons-financiers"),
}

# ---------------------------------------------------------------- audio
SR = 48000


def mtof(m):
    return 440 * 2 ** ((m - 69) / 12)


def tone(m, dur, vel, decay=1.3, partials=((1, 1), (2, .5), (3, .22), (4, .1), (5, .05))):
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = mtof(m)
    s = np.zeros(n)
    for k, a in partials:
        s += a * np.sin(2 * np.pi * f * k * t * (1 + 0.0003 * k)) * np.exp(-t * (decay + 0.8 * k))
    return s * np.minimum(1, t / 0.004) * vel


def glock(m, vel):
    return tone(m, 2.5, vel, 2.2, ((1, 1), (2.756, .35), (5.404, .15)))


def add(buf, sig, at, pan=0.0):
    i = int(at * SR)
    if i >= buf.shape[0]:
        return
    sig = sig[: buf.shape[0] - i]
    buf[i:i + len(sig), 0] += sig * (1 - max(0, pan))
    buf[i:i + len(sig), 1] += sig * (1 + min(0, pan))


def noise(n, seed):
    return np.random.default_rng(seed).standard_normal(n)


def highpass(x):
    return np.diff(x, prepend=0)


def lowpass(x, k=8):
    return np.convolve(x, np.ones(k) / k, mode="same")


def make_music(duration, chords, cta_at, sfx):
    n = int(SR * (duration + 0.5))
    buf = np.zeros((n, 2))
    CH = {"F": [53, 57, 60], "Dm": [50, 53, 57], "Bb": [46, 50, 53], "C": [48, 52, 55]}
    eighth = 60 / 92 / 2
    rnd = random.Random(1)
    for idx, (start, name) in enumerate(chords):
        end = chords[idx + 1][0] if idx + 1 < len(chords) else duration
        notes = CH[name]
        last = idx == len(chords) - 1
        add(buf, tone(notes[0] - 12, min(4, end - start + 1.5), 0.28, 0.6), start)
        for j, m in enumerate(notes):  # nappe
            ln = end - start + 1.0
            tt = np.arange(int(SR * ln)) / SR
            env = np.minimum(1, tt / 0.6) * np.minimum(1, (ln - tt) / 0.8)
            pad = (np.sin(2 * np.pi * mtof(m + 12) * tt) + 0.3 * np.sin(2 * np.pi * mtof(m + 24) * tt * 1.002)) * env * 0.035
            add(buf, pad, start, pan=(j - 1) * 0.4)
        if last:
            for j, m in enumerate(notes + [notes[0] + 12]):
                add(buf, tone(m + 12, 4.5, 0.16, 0.5), start + j * 0.06, pan=(j - 1.5) * 0.3)
            continue
        pattern = [0, 2, 4, 2, 3, 2, 4, 2]
        tones = [notes[0] + 12, notes[1] + 12, notes[2] + 12, notes[0] + 24, notes[1] + 24]
        k = 0
        tt = start
        while tt < end - 0.01:
            m = tones[pattern[k % 8]]
            add(buf, tone(m, 1.6, 0.11 + 0.03 * rnd.random(), 1.6), tt, pan=0.25 * math.sin(k))
            tt += eighth
            k += 1
    # pizzicati discrets au milieu
    t = 7.0
    while t < min(12.0, duration - 1):
        add(buf, tone(72 + rnd.choice([0, 4, 7, 12]), 0.4, 0.05, 9), t, pan=0.5)
        t += eighth * 2
    # grelots + glockenspiel à l'appel final
    if cta_at is not None:
        for i in range(int(2.2 / (eighth / 2))):
            at = cta_at + i * eighth / 2
            nz = highpass(highpass(noise(int(SR * 0.09), i))) * np.exp(-np.arange(int(SR * 0.09)) / SR * 40)
            add(buf, nz * (0.05 if i % 2 else 0.08), at, pan=0.3 * (1 if i % 2 else -1))
        for j, m in enumerate([89, 93, 96, 101]):
            add(buf, glock(m, 0.09), cta_at + j * 0.12, pan=(j - 1.5) * 0.25)
    # effets
    for at, kind in sfx:
        if kind == "bulb":
            nz = highpass(noise(int(SR * 0.012), 7)) * 0.35
            add(buf, nz, at)
            add(buf, tone(40, 0.08, 0.25, 40), at)
            for j, m in enumerate([89, 93, 96]):
                add(buf, glock(m, 0.10), at + 0.05 + j * 0.06, pan=(j - 1) * 0.3)
        elif kind == "bulb_big":
            for j, m in enumerate([84, 89, 93, 96, 101]):
                add(buf, glock(m, 0.11), at + j * 0.07, pan=(j - 2) * 0.25)
        elif kind == "pop":
            ln = int(SR * 0.06)
            tt = np.arange(ln) / SR
            f = 900 * np.exp(-tt * 30) + 250
            add(buf, np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 50) * 0.18, at)
        elif kind == "clink":
            add(buf, tone(100, 0.4, 0.05, 12, ((1, 1), (1.6, .6), (2.4, .4))), at, pan=0.3)
            add(buf, glock(96, 0.05), at + 0.03)
        elif kind == "rustle":
            ln = int(SR * 0.9)
            nz = highpass(noise(ln, 3)) * (0.5 + 0.5 * np.abs(np.sin(np.arange(ln) / SR * 23)))
            add(buf, nz * 0.05 * np.sin(np.pi * np.arange(ln) / ln), at)
        elif kind == "whoosh":
            ln = int(SR * 1.0)
            env = np.sin(np.pi * np.arange(ln) / ln) ** 2
            add(buf, lowpass(noise(ln, 5), 24) * env * 0.5, at)
        elif kind == "shimmer":
            for j in range(10):
                add(buf, glock(96 + rnd.choice([0, 2, 4, 7, 9, 12]), 0.035), at + j * 0.05, pan=rnd.uniform(-.6, .6))
    # réverbération
    irn = int(SR * 2.0)
    ir_t = np.arange(irn) / SR
    out = np.zeros_like(buf)
    nfft = 1 << int(math.ceil(math.log2(n + irn)))
    for c in range(2):
        ir = noise(irn, 100 + c) * np.exp(-ir_t * 3.2)
        ir /= np.sqrt(np.sum(ir ** 2))
        wet = np.fft.irfft(np.fft.rfft(buf[:, c], nfft) * np.fft.rfft(ir, nfft), nfft)[:n]
        out[:, c] = buf[:, c] + 0.35 * wet
    fade = int(SR * 1.2)
    end_i = int(SR * duration)
    out[end_i - fade:end_i] *= np.linspace(1, 0, fade)[:, None]
    out = out[:end_i]
    out /= max(1e-6, np.abs(out).max()) / 0.89
    return out


AUDIO = {
    "c1": dict(cta=14.0, sfx=[(1.5, "bulb")] + [(8.1 + 0.2 * i + 0.3, "pop") for i in range(6)] + [(12.0, "shimmer")]),
    "c2": dict(cta=14.0, sfx=[(1.5, "bulb")] + [(6.3 + 0.55 * i, "clink") for i in range(6)] + [(12.0, "shimmer")]),
    "c3": dict(cta=14.0, sfx=[(1.5, "bulb"), (2.4, "rustle"), (4.1, "pop"), (6.8, "whoosh"), (7.3, "shimmer"), (11.8, "whoosh")]),
    "c4": dict(cta=14.0, sfx=[(1.5, "bulb"), (2.2, "pop"), (7.3, "pop"), (8.4, "pop"), (12.0, "shimmer")]),
    "c5": dict(cta=12.4, sfx=[(1.5, "bulb_big"), (7.3, "shimmer"), (12.0, "whoosh")]),
    "rappel": dict(cta=6.0, sfx=[(0.2, "bulb_big"), (1.5, "whoosh"), (3.0, "pop"), (4.5, "pop")]),
}
CHORDS20 = [(0, "F"), (2.5, "Dm"), (5, "Bb"), (7.5, "C"), (10, "F"), (12.5, "Dm"), (14, "Bb"), (15, "C"), (16, "F")]
CHORDS10 = [(0, "F"), (1.5, "Dm"), (3.0, "Bb"), (4.5, "C"), (6.0, "F")]


def write_wav(path, data):
    pcm = (np.clip(data, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def audio_for(key, duration, wav_path, voice=None):
    cfg = AUDIO["c5" if key.startswith("c5") else key]
    music = make_music(duration, CHORDS10 if duration <= 10 else CHORDS20, cfg["cta"], cfg["sfx"])
    if voice and os.path.exists(voice):
        # voix off : on baisse la musique sous la voix (environ -10 dB)
        music *= 0.32
    write_wav(wav_path, music)


# ---------------------------------------------------------------- render
def render(key, stills=False, voice_dir=None):
    scene = SCENES[key]()
    os.makedirs(OUT, exist_ok=True)
    if stills:
        sd = os.path.join(BASE, "controle")
        os.makedirs(sd, exist_ok=True)
        times = [0.9, 2.0, 3.5, 6.5, 9.5, 11.5, 13.0, 14.8, 17.5] if scene.duration > 10 else [0.8, 2.2, 3.7, 5.2, 8.0]
        thumbs = []
        for t in times:
            im = scene.frame(t).convert("RGB")
            thumbs.append(im.resize((W // 3, H // 3), Image.LANCZOS))
        sheet = Image.new("RGB", (W // 3 * len(thumbs), H // 3), (0, 0, 0))
        for i, th in enumerate(thumbs):
            sheet.paste(th, (i * W // 3, 0))
        p = os.path.join(sd, f"{key}.jpg")
        sheet.save(p, quality=85)
        print("stills ->", p)
        return p
    name = f"ESC_Noel2026_{scene.name}"
    wav = os.path.join(OUT, f".{key}.wav")
    voice = None
    if voice_dir:
        for ext in (".mp3", ".m4a", ".wav", ".ogg", ".aac", ".opus"):
            cand = os.path.join(voice_dir, key + ext)
            if os.path.exists(cand):
                voice = cand
    audio_for(key, scene.duration, wav, voice)
    out = os.path.join(OUT, name + ".mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", wav]
    if voice:
        cmd += ["-i", voice, "-filter_complex",
                "[2:a]adelay=2000|2000,highpass=f=80,acompressor=threshold=-18dB:ratio=3,volume=1.6[v];"
                "[1:a][v]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-ar", "48000", "-movflags", "+faststart", "-metadata", "title=Noël de l'Espoir 2026 – E.S.C.",
            "-t", str(scene.duration), out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    nframes = int(round(scene.duration * FPS))
    for i in range(nframes):
        proc.stdin.write(scene.frame(i / FPS).convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    os.remove(wav)
    print("video ->", out, flush=True)
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    stills = "--stills" in args
    voice_dir = None
    if "--voice" in args:
        voice_dir = args[args.index("--voice") + 1]
        args.remove(voice_dir)
    keys = [a for a in args if not a.startswith("--")] or list(SCENES)
    if len(keys) > 1 and not stills:
        from multiprocessing import Pool
        with Pool(min(3, len(keys))) as pool:
            pool.starmap(render, [(k, False, voice_dir) for k in keys])
    else:
        for k in keys:
            render(k, stills, voice_dir)
