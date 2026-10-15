"""Concept-derived textures: projects each concept picture's sphere onto the ball and splits it into layers.
Python 3 + numpy + Pillow + scipy. Inputs are data: the three concept PNGs in unreal/concepts/ (not committed). Run:

  python project_concepts.py

For each ball, writes SourceArt/proj_<ball>_{base,emis,norm}.png: 2048x1024 equirect maps in ball space
(u = atan2(y, x) / 2pi + 0.5, v = acos(z) / pi; z up):
  base  the outer layer's colour (dark stone, black glass, ice), sRGB
  emis  the glowing layer (crystal light, liquid, ice glow), sRGB; drawn deeper with parallax by the shader
  norm  object-space normals (n * 0.5 + 0.5) from the picture's own shading of the outer layer
How: the picture's ball is a fitted circle (centre, radius, measured on the originals). The front hemisphere (-x, the
direction the previews' concept camera looks from: screen right = +y, up = +z) is the orthographic view of the
picture: a ball direction (x, y, z) with x < 0 is the pixel (cx + r*y, cy - r*z). The outer 7% of the radius (rim
light and background) is left out by mapping the hemisphere onto 93% of the radius. The back hemisphere is the
picture mirrored and turned 120 degrees about the view axis (Toxic: the designer's own unwrapped strip), blended
with the front over a band round the silhouette (see project()). The picture is first upscaled 4x (Lanczos) and
sharpened (unsharp mask), all scripted. The glow map's alpha is the picture's edge mask (crisp detail up close).
"""
import os

import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import gaussian_filter, map_coordinates

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "SourceArt"))
W, H = 2048, 1024
# The concept pictures are not in the repo (they stay private): put void.png, frost.png and toxic.png in
# unreal/concepts/ (gitignored) before building.
CONCEPT_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "concepts"))
CONCEPTS = {
    "void": (os.path.join(CONCEPT_DIR, "void.png"), (390, 345, 300)),
    "frost": (os.path.join(CONCEPT_DIR, "frost.png"), (205, 180, 165)),
    "toxic": (os.path.join(CONCEPT_DIR, "toxic.png"), (226, 194, 167)),
}
UP = 4
# Toxic's designer strip (bottom-left panel of its concept): an unwrapped band of the ball, used for its back
STRIPS = {"toxic": (30, 466, 322, 536)}


def load(path):
    im = Image.open(path).convert("RGB")
    im = im.resize((im.width * UP, im.height * UP), Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=3, percent=80, threshold=2))
    return np.asarray(im).astype(np.float64) / 255.0


def srgb_to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def directions():
    u = (np.arange(W) + 0.5) / W
    v = (np.arange(H) + 0.5) / H
    U, V = np.meshgrid(u, v)
    phi = (U - 0.5) * 2 * np.pi
    th = V * np.pi
    return np.stack([np.sin(th) * np.cos(phi), np.sin(th) * np.sin(phi), np.cos(th)], -1)


def sample(img, py, px):
    return np.clip(np.stack([map_coordinates(img[..., c], [py, px], order=3, mode="nearest") for c in range(3)], -1), 0, 1)


def project(img, circle, strip=None, back_turn=2.1, seam=0.32):
    """Front (-x): the picture, orthographic. Back (+x): the picture again, mirrored AND turned back_turn radians
    about the view axis (so rolling doesn't show an obvious twin), or for Toxic the designer's own unwrapped strip
    (back longitude -90..90 deg across the strip's width, latitude +-90 deg down its height). The two are blended over
    a band |x| < seam round the silhouette, where they differ."""
    cx, cy, r = (c * UP for c in circle)
    d = directions()
    k = 0.93 * r
    front = sample(img, cy - k * d[..., 2], cx + k * d[..., 1])
    c, s = np.cos(back_turn), np.sin(back_turn)
    yb = c * d[..., 1] - s * d[..., 2]
    zb = s * d[..., 1] + c * d[..., 2]
    back = sample(img, cy - k * zb, cx + k * yb)
    if strip is not None:
        x0, y0, x1, y1 = (v * UP for v in strip)
        lon = np.arctan2(d[..., 1], d[..., 0])                     # 0 at +x (the back's middle)
        lat = np.arcsin(np.clip(d[..., 2], -1, 1))
        su = x0 + (np.clip(lon / np.pi + 0.5, 0, 1)) * (x1 - x0)
        sv = y0 + np.clip(0.5 - lat / np.pi, 0, 1) * (y1 - y0)
        polar = smooth(0.7, 0.92, np.abs(d[..., 2]))[..., None]     # the strip pinches at the poles: use the
        st = sample(img, sv, su)
        # the strip is more teal than the front: move its teal toward lime (about the front's 60% lime balance)
        lime = np.stack([st[..., 0] + 0.55 * st[..., 2], st[..., 1], st[..., 2] * 0.25], -1)
        st = st * 0.45 + np.clip(lime, 0, 1) * 0.55
        back = st * (1 - polar) + back * polar                       # turned picture there
    w = smooth(-seam, seam, d[..., 0])[..., None]                  # 0 front .. 1 back
    return front * (1 - w) + back * w, d


def hsv(rgb):
    mx = rgb.max(-1)
    mn = rgb.min(-1)
    s = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0)
    return s, mx


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def normals(height, d, strength):
    """Object-space normals from a height field on the equirect grid (gradient along longitude and latitude)."""
    h = gaussian_filter(height, 1.2)
    gy, gx = np.gradient(h)
    th = (np.arange(H) + 0.5) / H * np.pi
    sin_th = np.maximum(np.sin(th), 0.05)[:, None]
    phi_dir = np.stack([-d[..., 1], d[..., 0], np.zeros_like(d[..., 0])], -1)
    phi_dir /= np.maximum(np.linalg.norm(phi_dir, axis=-1, keepdims=True), 1e-6)
    th_dir = np.cross(phi_dir, d)
    dphi = gx * (W / (2 * np.pi)) / sin_th
    dth = gy * (H / np.pi)
    n = d - strength * (dphi[..., None] * phi_dir - dth[..., None] * th_dir) / W * 8
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n


def save(name, rgb, alpha=None):
    a = np.clip(rgb, 0, 1)
    mode = "RGB"
    if alpha is not None:
        a = np.concatenate([a, np.clip(alpha, 0, 1)[..., None]], -1)
        mode = "RGBA"
    Image.fromarray((a * 255 + 0.5).astype(np.uint8), mode).save(os.path.join(OUT, name))


def edges(lum):
    """The picture's own edges (facet borders, crack lines, shard edges): where crisp detail is added up close."""
    gy, gx = np.gradient(gaussian_filter(lum, 0.8))
    e = np.sqrt(gx * gx + gy * gy)
    return smooth(np.percentile(e, 70), np.percentile(e, 97), e)


def main():
    os.makedirs(OUT, exist_ok=True)
    for ball, (path, circle) in CONCEPTS.items():
        img = load(path)
        col, d = project(img, circle, strip=STRIPS.get(ball))
        s, v = hsv(col)
        lum = col @ np.array([0.2126, 0.7152, 0.0722])
        if ball == "void":
            # crystal light: saturated or very bright; stone: grey, low saturation
            glow = np.maximum(smooth(0.38, 0.62, s) * smooth(0.15, 0.35, v), smooth(0.75, 0.92, v) * smooth(0.25, 0.45, s + 0.1))
            base = col * (1 - glow)[..., None]
            emis = col * glow[..., None]
            height = lum * (1 - glow)
            ns = 2.5
        elif ball == "frost":
            # ice is luminous: most of the picture glows; the outer layer is the ice's own sheen
            glow = smooth(0.08, 0.35, v)
            base = col * 0.25
            emis = col * glow[..., None]
            height = lum
            ns = 1.5
        else:
            # liquid: saturated green/teal; black glass: the dark, unsaturated rest (its facets from its shading)
            glow = smooth(0.2, 0.42, s) * smooth(0.07, 0.2, v)
            base = col * (1 - glow)[..., None]
            emis = col * glow[..., None]
            height = lum * (1 - glow)
            ns = 3.0
        save("proj_%s_base.png" % ball, base)
        save("proj_%s_emis.png" % ball, emis, edges(lum))        # alpha: the edge mask for detail
        save("proj_%s_norm.png" % ball, normals(height, d, ns) * 0.5 + 0.5)
        print(ball, "glow cover %.0f%%" % (glow.mean() * 100))


if __name__ == "__main__":
    main()
