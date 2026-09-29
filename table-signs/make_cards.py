"""Generate the 4x6" table cards as vector PDFs (text converted to outlines).

  python make_cards.py

Writes to ./cards:
  print/table-cards-print.pdf   all 12 cards, 4.25x6.25" pages = 4x6" trim + 1/8" bleed,
                                TrimBox/BleedBox set - send this to a professional printer
  print/table-NN-name.pdf       the same, one file per card
  table-cards-4x6.pdf           trimmed 4x6" pages - printers that take 4x6 cardstock
  table-cards-letter.pdf        two cards per US Letter sheet with crop marks - home printing
  jpg/table-NN-name.jpg         1200x1800 @ 300 dpi - photo labs (Walgreens, Costco...)

The bottom 16 mm of each card is hidden by the base's slot, so nothing important goes there.
Artwork is drawn in 300-dpi pixel units (1200x1800 trim); the PDF scales it to points.
"""
import math
import os
import random

import pymupdf as fitz
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from PIL import Image
from reportlab.graphics.barcode.qrencoder import QRCode, QRErrorCorrectLevel
from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas
from reportlab.pdfgen.canvas import FILL_NON_ZERO

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "cards")
REVIEW_URL = "https://g.page/r/CVUmePkpa86oEAE/review"
STORE = "WE GEEK TOGETHER"
LOGO = r"C:\dev\wegeektogether\assets\we-geek-together-logo.png"
FONT = os.path.join(os.environ["LOCALAPPDATA"], r"Microsoft\Windows\Fonts\monofonto rg.otf")

# (name, accent colour, hologram style)
TABLES = [  # alphabetical, one first letter per table
    ("ARRAKIS",   "#FFB000", "two_moons"),
    ("EARTH",     "#3A8DFF", "orbit"),
    ("GALLIFREY", "#FF5FA2", "sphere"),
    ("HOTH",      "#7FE3FF", "sphere"),
    ("JUPITER",   "#FF7A1A", "bands"),
    ("KRYPTON",   "#3DDC5A", "shattered"),
    ("MARS",      "#FF4436", "sphere"),
    ("NEPTUNE",   "#6A5CFF", "sphere"),
    ("PLUTO",     "#A8B3C0", "craters"),
    ("SATURN",    "#F5E663", "rings"),
    ("TATOOINE",  "#D9B27C", "twin_suns"),
    ("VENUS",     "#F2F0E6", "sphere"),
]

W, H = 1200, 1800          # 4x6" trim at 300 dpi
BLEED = 37.5               # 1/8" at 300 dpi
M = 80                     # content margin
HIDDEN_TOP = H - 189       # 16 mm slot at the bottom
PX = 72 / 300              # points per artwork pixel
PAGE_W, PAGE_H = (W + 2 * BLEED) * PX, (H + 2 * BLEED) * PX   # 306 x 450 pt
TRIM = fitz.Rect(BLEED * PX, BLEED * PX, PAGE_W - BLEED * PX, PAGE_H - BLEED * PX)
BG = (14, 18, 22)
TEXT = (236, 238, 240)
DIM = (130, 140, 150)
STAR_GOLD = (255, 196, 40)
GLOW = ((18, 0.07), (10, 0.10), (4, 0.16))  # (extra stroke width px, alpha) halo layers


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ---- Text as outlines --------------------------------------------------------------
_FONT = TTFont(FONT)
_GLYPHS = _FONT.getGlyphSet()
_CMAP = _FONT.getBestCmap()
_UPM = _FONT["head"].unitsPerEm
_ADV = _FONT["hmtx"].metrics


class Font:
    def __init__(self, size):
        self.size = size

    def getlength(self, s):
        return sum(_ADV[_CMAP[ord(ch)]][0] for ch in s if ord(ch) in _CMAP) * self.size / _UPM


def font(size):
    return Font(size)


def fit_font(text, max_width, start):
    size = start
    while font(size).getlength(text) > max_width:
        size -= 4
    return font(size)


class _PathPen(BasePen):
    """Draws font outlines into a reportlab path, flipping y (artwork space is y-down)."""

    def __init__(self, path, x, y, scale):
        super().__init__(_GLYPHS)
        self.p, self.x, self.y, self.s = path, x, y, scale

    def _t(self, pt):
        return self.x + pt[0] * self.s, self.y - pt[1] * self.s

    def _moveTo(self, pt):
        self.p.moveTo(*self._t(pt))

    def _lineTo(self, pt):
        self.p.lineTo(*self._t(pt))

    def _curveToOne(self, a, b, c):
        self.p.curveTo(*self._t(a), *self._t(b), *self._t(c))

    def _closePath(self):
        self.p.close()


def text_path(c, s, x, y, f, anchor):
    if anchor == "rs":
        x -= f.getlength(s)
    p = c.beginPath()
    scale = f.size / _UPM
    for ch in s:
        g = _CMAP.get(ord(ch))
        if g:
            _GLYPHS[g].draw(_PathPen(p, x, y, scale))
            x += _ADV[g][0] * scale
    return p


# ---- Vector drawing with a PIL-ImageDraw-like API ------------------------------------
def _rgba(fill):
    r, g, b = (v / 255 for v in fill[:3])
    return r, g, b, (fill[3] / 255 if len(fill) > 3 else 1.0)


class Layer:
    """Records drawing calls, then replays them onto a reportlab canvas as vector paths.
    With glow=True every element also gets soft halo strokes underneath (neon look)."""

    def __init__(self, c, glow=False):
        self.c, self.glow, self.ops = c, glow, []

    # Recording (same call shapes as PIL.ImageDraw)
    def line(self, pts, fill, width=1, joint=None):
        p = self.c.beginPath()
        p.moveTo(*pts[0])
        for pt in pts[1:]:
            p.lineTo(*pt)
        self.ops.append((p, None, fill, width))

    def ellipse(self, box, fill=None, outline=None, width=1):
        p = self.c.beginPath()
        p.ellipse(box[0], box[1], box[2] - box[0], box[3] - box[1])
        self.ops.append((p, fill, outline, width))

    def arc(self, box, start, end, fill, width=1):
        p = self.c.beginPath()
        p.arc(box[0], box[1], box[2], box[3], start, end - start)
        self.ops.append((p, None, fill, width))

    def polygon(self, pts, fill):
        p = self.c.beginPath()
        p.moveTo(*pts[0])
        for pt in pts[1:]:
            p.lineTo(*pt)
        p.close()
        self.ops.append((p, fill, None, 0))

    def rectangle(self, box, fill):
        p = self.c.beginPath()
        p.rect(box[0], box[1], box[2] - box[0], box[3] - box[1])
        self.ops.append((p, fill, None, 0))

    def text(self, xy, s, font, fill, anchor="ls"):
        self.ops.append((text_path(self.c, s, xy[0], xy[1], font, anchor), fill, None, 0))

    # Replay
    def render(self):
        c = self.c
        c.saveState()
        c.setLineJoin(1)
        c.setLineCap(1)
        if self.glow:
            for extra, alpha in GLOW:
                for p, fill, stroke, width in self.ops:
                    col = stroke or fill
                    r, g, b, a = _rgba(col)
                    if stroke is None and a < 0.5:
                        continue  # translucent fills (hologram bodies) don't glow
                    c.setStrokeColorRGB(r, g, b, alpha=alpha * a)
                    c.setLineWidth(width + extra)
                    c.drawPath(p, stroke=1, fill=0)
        for p, fill, stroke, width in self.ops:
            if fill:
                r, g, b, a = _rgba(fill)
                c.setFillColorRGB(r, g, b, alpha=a)
            if stroke:
                r, g, b, a = _rgba(stroke)
                c.setStrokeColorRGB(r, g, b, alpha=a)
                c.setLineWidth(width)
            c.drawPath(p, stroke=1 if stroke else 0, fill=1 if fill else 0, fillMode=FILL_NON_ZERO)
        c.restoreState()


# ---- Background ----------------------------------------------------------------------
def background(c, rng, accent):
    x0, y0, x1, y1 = -BLEED, -BLEED, W + BLEED, H + BLEED
    c.setFillColorRGB(*(v / 255 for v in BG))
    c.rect(x0, y0, x1 - x0, y1 - y0, stroke=0, fill=1)
    bg = Color(*(v / 255 for v in BG))
    for _ in range(14):  # grime blotches: soft dark radial fades
        x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(40, 160)
        k = 1 - rng.uniform(0.08, 0.18)
        c.radialGradient(x, y, r, [Color(*(v / 255 * k for v in BG)), bg], extend=False)
    c.setLineWidth(1)
    c.setStrokeColorRGB(1, 1, 1, alpha=0.035)
    p = c.beginPath()
    for x in range(-40, W + 80, 40):
        p.moveTo(x, y0)
        p.lineTo(x, y1)
    for y in range(-40, H + 80, 40):
        p.moveTo(x0, y)
        p.lineTo(x1, y)
    c.drawPath(p, stroke=1, fill=0)
    c.setLineCap(1)
    for _ in range(90):  # scuffs and scratches
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        a, n = rng.uniform(0, math.pi), rng.uniform(15, 140)
        c.setStrokeColorRGB(1, 1, 1, alpha=rng.randint(8, 24) / 255)
        c.setLineWidth(rng.choice((1, 1, 2)))
        c.line(x, y, x + n * math.cos(a), y + n * math.sin(a))
    # Hazard stripes in the hidden slot zone, running out into the bleed
    c.setFillColorRGB(*(v * 0.35 / 255 for v in accent))
    for x in range(-H, W + H, 60):
        p = c.beginPath()
        top, bot = HIDDEN_TOP + 30, y1
        p.moveTo(x, top)
        p.lineTo(x + 30, top)
        p.lineTo(x + 30 + (bot - top), bot)
        p.lineTo(x + (bot - top), bot)
        p.close()
        c.drawPath(p, stroke=0, fill=1)


def frame(d, accent):
    c, i = 36, 40
    pts = [(i + c, i), (W - i - c, i), (W - i, i + c), (W - i, HIDDEN_TOP - 10),
           (i, HIDDEN_TOP - 10), (i, i + c)]
    d.line(pts + [pts[0]], fill=accent + (170,), width=4, joint="curve")
    for x in range(260, W - i - 60, 22):  # tick marks along the top rail, clear of the logo
        d.line([(x, i + 10), (x, i + 18)], fill=accent + (110,), width=2)


def rivets(d):
    i = 40
    for x, y in ((i + 14, i + 60), (W - i - 14, i + 60), (i + 14, HIDDEN_TOP - 30), (W - i - 14, HIDDEN_TOP - 30)):
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(70, 78, 86, 255))


# ---- Hologram planet -------------------------------------------------------------------
def hologram(d, cx, cy, r, accent, style, number):
    a = accent
    # Targeting reticle
    R = r + 72
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=a + (200,), width=3)
    for deg in range(0, 360, 10):
        t = math.radians(deg)
        n = 26 if deg % 30 == 0 else 12
        d.line([(cx + R * math.cos(t), cy + R * math.sin(t)),
                (cx + (R - n) * math.cos(t), cy + (R - n) * math.sin(t))], fill=a + (200,), width=3)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        d.line([(cx + dx * (R + 8), cy + dy * (R + 8)), (cx + dx * (R + 30), cy + dy * (R + 30))],
               fill=a + (255,), width=5)
    f = font(28)
    d.text((cx + R, cy - R + 12), "SCAN LOCK", font=f, fill=a + (230,), anchor="rs")
    d.text((cx - R, cy - R + 12), f"NAV-{number:02d}", font=f, fill=a + (230,), anchor="ls")

    def sphere(rr, lines=True, fill_alpha=40):
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=a + (fill_alpha,), outline=a + (255,), width=4)
        if not lines:
            return
        for s in (0.5, 0.87):
            d.ellipse([cx - rr * s, cy - rr, cx + rr * s, cy + rr], outline=a + (120,), width=2)
        d.line([(cx, cy - rr), (cx, cy + rr)], fill=a + (120,), width=2)
        for lat in (-60, -30, 0, 30, 60):
            y = cy + rr * math.sin(math.radians(lat))
            hw = rr * math.cos(math.radians(lat))
            d.ellipse([cx - hw, y - hw * 0.18, cx + hw, y + hw * 0.18], outline=a + (120,), width=2)

    if style == "star":
        for k in range(36):
            t = math.radians(k * 10)
            r0, r1 = r + 8, r + (44 if k % 2 else 26)
            d.line([(cx + r0 * math.cos(t), cy + r0 * math.sin(t)),
                    (cx + r1 * math.cos(t), cy + r1 * math.sin(t))], fill=a + (230,), width=4)
        sphere(r, lines=False, fill_alpha=110)
        for s in (0.75, 0.5, 0.25):
            d.ellipse([cx - r * s, cy - r * s, cx + r * s, cy + r * s], outline=a + (170,), width=3)
    elif style == "rings":
        rp = r * 0.72
        boxes = [(rp * k, rp * k * 0.24) for k in (1.55, 1.75, 1.95)]
        for hw, hh in boxes:  # far half of the rings, behind the planet
            d.arc([cx - hw, cy - hh, cx + hw, cy + hh], 180, 360, fill=a + (200,), width=4)
        d.ellipse([cx - rp, cy - rp, cx + rp, cy + rp], fill=BG + (255,))
        sphere(rp)
        for hw, hh in boxes:  # near half, in front
            d.arc([cx - hw, cy - hh, cx + hw, cy + hh], 0, 180, fill=a + (230,), width=4)
    elif style == "bands":
        sphere(r, lines=False)
        for k in range(-5, 6):
            y = cy + r * k / 6
            hw = math.sqrt(max(r * r - (y - cy) ** 2, 0))
            d.line([(cx - hw, y), (cx + hw, y)], fill=a + (140 if k % 2 else 200,), width=3)
        d.ellipse([cx + r * 0.1, cy + r * 0.2, cx + r * 0.55, cy + r * 0.42], outline=a + (255,), width=4)
    elif style == "craters":
        sphere(r, lines=False)
        for ox, oy, cr in ((-0.4, -0.3, 0.22), (0.3, -0.45, 0.12), (0.35, 0.25, 0.28),
                           (-0.25, 0.45, 0.14), (-0.55, 0.15, 0.09), (0.05, 0.0, 0.1)):
            x, y, rr = cx + ox * r, cy + oy * r, cr * r
            d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=a + (200,), width=3)
    elif style == "twin_suns":  # Tatooine: twin suns (with rays) and three moons
        sphere(r * 0.85)
        for ox, oy, sr in ((-1.05, -1.0, 0.17), (-0.66, -1.2, 0.11)):
            x, y, rr = cx + ox * r, cy + oy * r, sr * r
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=a + (220,))
            for k in range(12):
                t = math.radians(k * 30)
                d.line([(x + (rr + 5) * math.cos(t), y + (rr + 5) * math.sin(t)),
                        (x + (rr + 14) * math.cos(t), y + (rr + 14) * math.sin(t))], fill=a + (220,), width=3)
        hw, hh = r * 1.22, r * 0.42
        d.arc([cx - hw, cy - hh, cx + hw, cy + hh], 200, 340, fill=a + (140,), width=3)
        d.arc([cx - hw, cy - hh, cx + hw, cy + hh], 0, 180, fill=a + (200,), width=3)
        for deg, mr in ((15, 14), (165, 12), (215, 10)):
            mx, my = cx + hw * math.cos(math.radians(deg)), cy + hh * math.sin(math.radians(deg))
            d.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=a + (255,))
    elif style == "two_moons":
        sphere(r * 0.85)
        for ox, oy, mr in ((1.02, -0.78, 0.12), (1.2, -0.35, 0.08)):
            x, y, rr = cx + ox * r, cy + oy * r, mr * r
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=a + (230,))
    elif style == "shattered":
        sphere(r, lines=False)
        rng = random.Random(number)
        for k in range(7):  # fracture lines radiating from an off-centre impact point
            t = math.radians(k * 360 / 7 + rng.uniform(-15, 15))
            pts, dist = [(cx - r * 0.15, cy - r * 0.1)], 0
            while dist < r * 0.95:
                dist += r * rng.uniform(0.15, 0.3)
                jitter = math.radians(rng.uniform(-20, 20))
                pts.append((cx - r * 0.15 + min(dist, r * 0.95) * math.cos(t + jitter),
                            cy - r * 0.1 + min(dist, r * 0.95) * math.sin(t + jitter)))
            d.line(pts, fill=a + (220,), width=3, joint="curve")
    elif style == "orbit":
        sphere(r * 0.85)
        hw, hh = r * 1.22, r * 0.42
        d.arc([cx - hw, cy - hh, cx + hw, cy + hh], 200, 340, fill=a + (140,), width=3)
        d.arc([cx - hw, cy - hh, cx + hw, cy + hh], 0, 180, fill=a + (200,), width=3)
        mx, my = cx + hw * math.cos(math.radians(35)), cy + hh * math.sin(math.radians(35))
        d.ellipse([mx - 16, my - 16, mx + 16, my + 16], fill=a + (255,))
    else:
        sphere(r)


# ---- QR --------------------------------------------------------------------------
def draw_qr(c, data, x0, y0, module):
    """Dark modules on a light plate with a 4-module quiet zone. Returns the plate box."""
    qr = QRCode(None, QRErrorCorrectLevel.M)
    qr.addData(data)
    qr.make()
    n, quiet = qr.getModuleCount(), 4
    size = (n + 2 * quiet) * module
    c.setFillColorRGB(244 / 255, 244 / 255, 238 / 255)
    c.rect(x0, y0, size, size, stroke=0, fill=1)
    p = c.beginPath()
    for row in range(n):
        col = 0
        while col < n:  # merge horizontal runs so there are no hairline seams
            if not qr.isDark(row, col):
                col += 1
                continue
            start = col
            while col < n and qr.isDark(row, col):
                col += 1
            p.rect(x0 + (start + quiet) * module, y0 + (row + quiet) * module - 0.05,
                   (col - start) * module, module + 0.1)
    c.setFillColorRGB(*(v / 255 for v in BG))
    c.drawPath(p, stroke=0, fill=1)
    return (x0, y0, x0 + size, y0 + size)


def star(d, cx, cy, r, color):
    pts = []
    for k in range(10):
        t = math.radians(-90 + k * 36)
        rr = r if k % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(t), cy + rr * math.sin(t)))
    d.polygon(pts, fill=color + (255,))


def brackets(d, box, accent, arm=46, gap=16, width=6):
    x0, y0, x1, y1 = box[0] - gap, box[1] - gap, box[2] + gap, box[3] + gap
    for (x, y, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line([(x + sx * arm, y), (x, y), (x, y + sy * arm)], fill=accent + (255,), width=width, joint="curve")


def image(c, path, x, y, w, h):
    c.saveState()
    c.translate(x, y + h)
    c.scale(1, -1)  # artwork space is y-down; images must be drawn upright
    c.drawImage(path, 0, 0, w, h, mask="auto")
    c.restoreState()


# ---- Card ------------------------------------------------------------------------
def draw_card(c, number, name, accent_hex, style):
    """Draws one card page. Artwork coordinates are 300-dpi pixels, y down, origin at trim."""
    accent = hex_rgb(accent_hex)
    c.setPageSize((PAGE_W, PAGE_H))
    c.saveState()
    c.translate(BLEED * PX, PAGE_H - BLEED * PX)
    c.scale(PX, -PX)

    background(c, random.Random(number * 7919), accent)
    d = Layer(c)
    g = Layer(c, glow=True)
    frame(g, accent)

    # Header
    d.text((M + 170, 128), STORE, font=font(72), fill=TEXT, anchor="ls")
    d.text((M + 172, 182), "TOURNAMENT GRID // TABLE ASSIGNMENT", font=font(31), fill=DIM, anchor="ls")
    g.line([(M, 262), (W - M, 262)], fill=accent + (220,), width=3)
    g.rectangle([M, 256, M + 180, 268], fill=accent + (255,))

    # Table number
    d.text((M + 4, 340), "TABLE", font=font(50), fill=DIM, anchor="ls")
    g.text((M - 10, 715), f"{number:02d}", font=font(470), fill=accent + (255,), anchor="ls")

    # Hologram
    hologram(g, 850, 545, 165, accent, style, number)

    # Name
    g.text((M, 990), name, font=fit_font(name, W - 2 * M, 190), fill=accent + (255,), anchor="ls")

    # Divider stripes
    for x in range(M, W - M, 28):
        g.polygon([(x, 1070), (x + 14, 1070), (x + 4, 1084), (x - 10, 1084)], fill=accent + (160,))

    # Review prompt (QR goes on the left, text on the right)
    tx = 610
    d.text((tx, 1180), "ENJOYING YOUR GAME?", font=font(40), fill=DIM, anchor="ls")
    d.text((tx, 1258), "LEAVE US A", font=font(64), fill=TEXT, anchor="ls")
    g.text((tx - 2, 1340), "GOOGLE REVIEW", font=fit_font("GOOGLE REVIEW", W - M - tx, 84),
           fill=accent + (255,), anchor="ls")
    for k in range(5):
        star(g, tx + 44 + k * 100, 1418, 44, STAR_GOLD)
    g.text((tx, 1530), "<<< SCAN HERE", font=font(44), fill=accent + (255,), anchor="ls")
    d.render()

    # The QR plate is drawn last (clean, no scanlines), but its brackets belong to the glow layer
    qr_origin, module = (M + 14, 1128), 12
    probe = QRCode(None, QRErrorCorrectLevel.M)
    probe.addData(REVIEW_URL)
    probe.make()
    qr_size = (probe.getModuleCount() + 8) * module
    brackets(g, (*qr_origin, qr_origin[0] + qr_size, qr_origin[1] + qr_size), accent)
    g.render()

    # CRT scanlines over everything except the logo and QR
    c.setStrokeColorRGB(0, 0, 0, alpha=38 / 255)
    c.setLineWidth(1)
    p = c.beginPath()
    y = -BLEED
    while y < H + BLEED:
        p.moveTo(-BLEED, y)
        p.lineTo(W + BLEED, y)
        y += 4
    c.drawPath(p, stroke=1, fill=0)

    f = Layer(c)
    rivets(f)
    f.text((610, HIDDEN_TOP - 30), f"UNIT {number:02d}/{len(TABLES):02d} // LEAVE ON TABLE",
           font=font(26), fill=DIM, anchor="ls")
    f.render()
    draw_qr(c, REVIEW_URL, *qr_origin, module)
    image(c, LOGO, M, 52, 150, 150)
    c.restoreState()
    c.showPage()


def slug(name):
    return name.lower().replace(" ", "-")


def main():
    print_dir, jpg_dir = os.path.join(OUT, "print"), os.path.join(OUT, "jpg")
    os.makedirs(print_dir, exist_ok=True)
    os.makedirs(jpg_dir, exist_ok=True)

    # Master vector PDF with bleed
    master = os.path.join(print_dir, "table-cards-print.pdf")
    c = canvas.Canvas(master, pagesize=(PAGE_W, PAGE_H))
    c.setTitle("We Geek Together table cards (4x6 in, 1/8 in bleed)")
    for i, (name, accent, style) in enumerate(TABLES, start=1):
        draw_card(c, i, name, accent, style)
    c.save()

    src = fitz.open(master)
    for page in src:
        # reportlab references an (unused, unembedded) Helvetica on every page; drop it so
        # printers' preflight doesn't flag a missing font
        font_dict = src.xref_get_key(page.xref, "Resources/Font")
        if font_dict[0] != "null":
            src.xref_set_key(page.xref, "Resources/Font", "null")
        page.clean_contents()
        page.set_bleedbox(page.rect)
        page.set_trimbox(TRIM)
    src.save(master + ".tmp", garbage=4, deflate=True)
    src.close()
    os.replace(master + ".tmp", master)
    src = fitz.open(master)
    print("wrote", os.path.relpath(master, HERE))

    four_by_six = fitz.open()
    letter = fitz.open()
    for i, (name, _accent, _style) in enumerate(TABLES):
        stem = f"table-{i + 1:02d}-{slug(name)}"
        # One print file per card
        single = fitz.open()
        single.insert_pdf(src, from_page=i, to_page=i)
        single[0].set_bleedbox(single[0].rect)
        single[0].set_trimbox(TRIM)
        single.save(os.path.join(print_dir, f"{stem}.pdf"))
        # Trimmed 4x6 page (still vector)
        page = four_by_six.new_page(width=TRIM.width, height=TRIM.height)
        page.show_pdf_page(page.rect, src, i, clip=TRIM)
        # 300-dpi JPG for photo labs
        pix = src[i].get_pixmap(dpi=300, clip=TRIM)
        Image.frombytes("RGB", (pix.width, pix.height), pix.samples).crop((0, 0, W, H)).save(
            os.path.join(jpg_dir, f"{stem}.jpg"), quality=95, dpi=(300, 300))
        # Two per Letter sheet with crop marks
        if i % 2 == 0:
            sheet = letter.new_page(width=612, height=792)
            x0, y0 = 18, (792 - TRIM.height) / 2
            for x in (x0, x0 + TRIM.width, x0 + 2 * TRIM.width):
                sheet.draw_line((x, y0 - 25), (x, y0 - 7), width=0.5)
                sheet.draw_line((x, y0 + TRIM.height + 7), (x, y0 + TRIM.height + 25), width=0.5)
            for y in (y0, y0 + TRIM.height):
                sheet.draw_line((x0 - 14, y), (x0 - 4, y), width=0.5)
                sheet.draw_line((x0 + 2 * TRIM.width + 4, y), (x0 + 2 * TRIM.width + 14, y), width=0.5)
        slot = fitz.Rect(x0 + (i % 2) * TRIM.width, y0, x0 + (i % 2 + 1) * TRIM.width, y0 + TRIM.height)
        sheet.show_pdf_page(slot, src, i, clip=TRIM)
        print("wrote", stem)
    four_by_six.save(os.path.join(OUT, "table-cards-4x6.pdf"))
    letter.save(os.path.join(OUT, "table-cards-letter.pdf"))
    print("wrote cards/table-cards-4x6.pdf and cards/table-cards-letter.pdf")


if __name__ == "__main__":
    main()
