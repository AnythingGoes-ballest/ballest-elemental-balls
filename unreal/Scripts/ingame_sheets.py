"""Sheets from in-game screenshots (a sandboxed slot's data folder), next to the concepts:

  python ingame_sheets.py <slot data folder> <out folder>

Expects (the test commands' shot names): fc_<ball>_0 (Customize), fm_<ball>_<0..2> (Customize under slomo 0.156,
taken ~6.6 s apart = ~1 s of game time apart), fr_<ball> (race start, on the yellow pad), fo_<ball>_<1..2> (rolling
down the track, off the pad).
ingame_comparison.png  concept | Customize | race on the pad | race off the pad | race off the pad (2)
ingame_motion.png      Customize frames at 0, 1, 2 s game time
ingame_race.png        full race frames off the pad
"""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

SRC, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
# The concept pictures are not in the repo (they stay private): put void.png, frost.png and toxic.png in
# unreal/concepts/ (gitignored) before building.
CONCEPT_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "concepts"))
CONCEPTS = {"void": os.path.join(CONCEPT_DIR, "void.png"), "frost": os.path.join(CONCEPT_DIR, "frost.png"),
            "toxic": os.path.join(CONCEPT_DIR, "toxic.png")}
CONCEPT_BALL = {"void": (90, 45, 690, 645), "frost": (40, 15, 370, 345), "toxic": (60, 30, 390, 360)}
NAMES = {"void": "Void Crystal", "frost": "Frost", "toxic": "Toxic Current"}
BALLS = ["void", "frost", "toxic"]
C = 340
BG = (18, 18, 22)
try:
    FONT, BIG = ImageFont.truetype("arial.ttf", 16), ImageFont.truetype("arialbd.ttf", 20)
except OSError:
    FONT = BIG = ImageFont.load_default()
CUST_BOX = (520, 200, 840, 520)          # the Customize page's ball (1280x720 screenshot)
PAD_BOX = (480, 340, 800, 660)           # the race ball on the start pad
OFF_BOX = (440, 430, 760, 750)           # rolling down the track (bottom clipped at 720 -> black)


def ball_crop(path, box):
    im = Image.open(path).convert("RGB")
    return im.crop(box).resize((C, C), Image.LANCZOS)


def concept(b):
    return Image.open(CONCEPTS[b]).convert("RGB").crop(CONCEPT_BALL[b]).resize((C, C), Image.LANCZOS)


def off_crop(path):
    """The ball off the pad: find its bright, saturated pixels below the horizon and crop round them."""
    im = Image.open(path).convert("RGB")
    import numpy as np
    a = np.asarray(im).astype(int)
    sat = a.max(-1) - a.min(-1)
    sky = (a[..., 2] > a[..., 0] + 40) & (a[..., 2] > a[..., 1] - 10)      # the blue track/water
    mask = (~sky) & (sat > 60)
    mask[:330] = False
    mask[:, :250] = False
    mask[:, 1030:] = False
    ys, xs = np.nonzero(mask)
    if len(xs) < 50:
        return im.crop((480, 300, 800, 620)).resize((C, C), Image.LANCZOS)
    cx, cy = int(np.median(xs)), int(np.median(ys))
    r = 110
    return im.crop((cx - r, cy - r, cx + r, cy + r)).resize((C, C), Image.LANCZOS)


def sheet(title, cols_fn, ncols, name):
    sh = Image.new("RGB", (10 + ncols * (C + 10), 50 + 3 * (C + 34)), BG)
    d = ImageDraw.Draw(sh)
    d.text((10, 12), title, fill=(235, 235, 235), font=BIG)
    y = 50
    for b in BALLS:
        for i, (t, im) in enumerate(cols_fn(b)):
            d.text((10 + i * (C + 10), y), t, fill=(235, 235, 235), font=FONT)
            sh.paste(im, (10 + i * (C + 10), y + 24))
        y += C + 34
    sh.save(os.path.join(OUT, name))


def p(n):
    return os.path.join(SRC, n + ".png")


sheet("Elemental Balls v2 IN THE GAME (sandboxed slot): concept | Customize | race start (pad) | race, off the pad",
      lambda b: [("concept: " + NAMES[b], concept(b)), ("in game: Customize", ball_crop(p("fc_%s_0" % b), CUST_BOX)),
                 ("race: on the start pad", ball_crop(p("fr_%s" % b), PAD_BOX)),
                 ("race: rolling, off the pad", off_crop(p("fo_%s_1" % b))),
                 ("race: rolling, off the pad (2)", off_crop(p("fo_%s_2" % b)))], 5, "ingame_comparison.png")
sheet("In game, Customize: frames at 0 / 1 / 2 s of game time (slomo 0.156; the glow flows, the outer layer is fixed)",
      lambda b: [("%s  t = %d s" % (NAMES[b], i), ball_crop(p("fm_%s_%d" % (b, i)), CUST_BOX)) for i in range(3)], 3,
      "ingame_motion.png")
rs = Image.new("RGB", (10 + 2 * (640 + 10), 50 + 3 * (360 + 34)), BG)
d = ImageDraw.Draw(rs)
d.text((10, 12), "In game, race (editor test run on the user's own unreleased map): off the start pad", fill=(235, 235, 235), font=BIG)
for r, b in enumerate(BALLS):
    for c in range(2):
        d.text((10 + c * 650, 50 + r * 394), "%s, %s" % (NAMES[b], ["~1 s", "~2 s"][c] + " after rolling off"), fill=(235, 235, 235), font=FONT)
        rs.paste(Image.open(p("fo_%s_%d" % (b, c + 1))).convert("RGB").resize((640, 360), Image.LANCZOS), (10 + c * 650, 74 + r * 394))
rs.save(os.path.join(OUT, "ingame_race.png"))
print("in-game sheets in", OUT)
