"""Composes preview sheets from render_previews.py output (plain Python 3 + Pillow).

  python compose_sheets.py <render dir> <out dir> [t list, default 0,1,2]

comparison.png : concept | Customize (t=0) | race (full chase-camera frame, t=0) | race close-up (same frame, cropped)
motion.png     : per ball, Customize and race close-up at each t (1 s apart)
"""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

SRC, OUT = sys.argv[1], sys.argv[2]
TIMES = sys.argv[3].split(",") if len(sys.argv) > 3 else ["0", "1", "2"]
os.makedirs(OUT, exist_ok=True)
# The concept pictures are not in the repo (they stay private): put void.png, frost.png and toxic.png in
# unreal/concepts/ (gitignored) before building.
CONCEPT_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "concepts"))
CONCEPTS = {
    "void": os.path.join(CONCEPT_DIR, "void.png"),
    "frost": os.path.join(CONCEPT_DIR, "frost.png"),
    "toxic": os.path.join(CONCEPT_DIR, "toxic.png"),
}
NAMES = {"void": "Void Crystal", "frost": "Frost", "toxic": "Toxic Current"}
CELL = 360
BG = (18, 18, 22)
try:
    FONT = ImageFont.truetype("arial.ttf", 16)
    BIG = ImageFont.truetype("arialbd.ttf", 20)
except OSError:
    FONT = BIG = ImageFont.load_default()


def fit(img, w, h):
    img = img.convert("RGB")
    s = max(w / img.width, h / img.height)
    img = img.resize((max(1, int(img.width * s + 0.5)), max(1, int(img.height * s + 0.5))), Image.LANCZOS)
    l, t = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((l, t, l + w, t + h))


def concept(ball):
    c = Image.open(CONCEPTS[ball]).convert("RGB")
    if ball == "toxic":                       # the toxic concept is a card: take the ball
        c = c.crop((40, 20, 410, 390))
    return fit(c, CELL, CELL)


def load(ball, scene, t):
    p = os.path.join(SRC, "%s_%s_t%s.png" % (ball, scene, t))
    return Image.open(p).convert("RGB") if os.path.exists(p) else None


def race_close(img):
    # ball sits in the middle of the 16:9 frame; crop a square ~2.4 ball diameters wide
    w, h = img.size
    side = int(h * 0.62)
    cx, cy = w // 2, h // 2
    return fit(img.crop((cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2)), CELL, CELL)


def race_full(img):
    return fit(img, int(CELL * 16 / 9), CELL)


def label(d, x, y, text, font=FONT):
    d.text((x, y), text, fill=(235, 235, 235), font=font)


def comparison():
    balls = ["void", "frost", "toxic"]
    cols = [CELL, CELL, int(CELL * 16 / 9), CELL]
    W = sum(cols) + 10 * (len(cols) + 1)
    H = 50 + len(balls) * (CELL + 34)
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    label(d, 10, 12, "Elemental Balls v2: real UE 5.8 materials (headless previews, game renderer settings)", BIG)
    y = 50
    for b in balls:
        x = 10
        cust, race = load(b, "customize", TIMES[0]), load(b, "race", TIMES[0])
        tiles = [("concept: " + NAMES[b], concept(b)),
                 ("Customize distance", fit(cust, CELL, CELL) if cust else None),
                 ("race: chase-camera frame (ball at game size)", race_full(race) if race else None),
                 ("race: close-up of the same frame", race_close(race) if race else None)]
        for (title, img), w in zip(tiles, cols):
            label(d, x, y, title)
            if img:
                sheet.paste(img, (x, y + 24))
            x += w + 10
        y += CELL + 34
    sheet.save(os.path.join(OUT, "comparison.png"))


def motion():
    balls = ["void", "frost", "toxic"]
    n = len(TIMES)
    W = 10 + 2 * n * (CELL + 10)
    H = 50 + len(balls) * (CELL + 34)
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    label(d, 10, 12, "Motion: frames 1 s apart (left: Customize, right: race close-up)", BIG)
    y = 50
    for b in balls:
        x = 10
        for scene in ["customize", "race"]:
            for t in TIMES:
                img = load(b, scene, t)
                label(d, x, y, "%s  %s  t=%ss" % (NAMES[b], scene, t))
                if img:
                    sheet.paste(fit(img, CELL, CELL) if scene == "customize" else race_close(img), (x, y + 24))
                x += CELL + 10
        y += CELL + 34
    sheet.save(os.path.join(OUT, "motion.png"))


def aura_sheet(levels=("0", "0.5", "1")):
    balls = ["void", "frost", "toxic"]
    W = 10 + (1 + 2 * len(levels)) * (CELL + 10)
    H = 50 + len(balls) * (CELL + 34)
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    label(d, 10, 12, "Aura strength (one dial, AuraStrength): Customize and race close-up at 0 / 0.5 / 1", BIG)
    y = 50
    for b in balls:
        x = 10
        label(d, x, y, "concept: " + NAMES[b])
        sheet.paste(concept(b), (x, y + 24))
        x += CELL + 10
        for scene in ["customize", "race"]:
            for a in levels:
                p = os.path.join(SRC, "%s_%s_t%s_a%s.png" % (b, scene, TIMES[0], a))
                label(d, x, y, "%s  aura %s" % (scene, a))
                if os.path.exists(p):
                    img = Image.open(p).convert("RGB")
                    sheet.paste(fit(img, CELL, CELL) if scene == "customize" else race_close(img), (x, y + 24))
                x += CELL + 10
        y += CELL + 34
    sheet.save(os.path.join(OUT, "aura.png"))


def load_any(ball, scene, t):
    for suffix in ["", "_a1"]:
        p = os.path.join(SRC, "%s_%s_t%s%s.png" % (ball, scene, t, suffix))
        if os.path.exists(p):
            return Image.open(p).convert("RGB")
    return None


def grid_sheet(scene="customize"):
    """3x3 variant grid per ball (render_previews grid mode), concept first."""
    balls = [b for b in ["void", "frost", "toxic"] if os.path.exists(os.path.join(SRC, "%s_%s_t%s_v0.png" % (b, scene, TIMES[0])))]
    C = 300
    for b in balls:
        W = 10 + 4 * (C + 10)
        H = 50 + 3 * (C + 34)
        sheet = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(sheet)
        label(d, 10, 12, "%s variants (%s, t=%ss): concept, then 9 parameter sets" % (NAMES[b], scene, TIMES[0]), BIG)
        label(d, 10, 50, "concept")
        sheet.paste(concept(b).resize((C, C)), (10, 74))
        for i in range(9):
            p = os.path.join(SRC, "%s_%s_t%s_v%d.png" % (b, scene, TIMES[0], i))
            if not os.path.exists(p):
                continue
            img = Image.open(p).convert("RGB")
            img = fit(img, C, C) if scene == "customize" else race_close(img).resize((C, C))
            x = 10 + (1 + i % 3) * (C + 10)
            y = 50 + (i // 3) * (C + 34)
            txt = open(p[:-4] + ".txt").read() if os.path.exists(p[:-4] + ".txt") else ""
            label(d, x, y, "#%d  %s" % (i, txt))
            sheet.paste(img, (x, y + 24))
        sheet.save(os.path.join(OUT, "grid_%s_%s.png" % (b, scene)))


# the ball's box in each concept picture (measured by eye on the originals)
CONCEPT_BALL = {"void": (90, 45, 690, 645), "frost": (40, 15, 370, 345), "toxic": (60, 30, 390, 360)}


def fidelity(t="0"):
    """Concept | A procedural | B concept-projected | 50/50 blends, per ball (scene "concept": front view, dark
    backdrop, the ball the concept's size). A = <ball>_concept, B = <ball>p_concept."""
    C = 340

    def ren(name):
        p = os.path.join(SRC, "%s_concept_t%s.png" % (name, t))
        if not os.path.exists(p):
            return None
        img = Image.open(p).convert("RGB")
        w, h = img.size
        r = int(h * 0.43)                                   # the ball fills 86% of the frame height
        return img.crop((w // 2 - r, h // 2 - r, w // 2 + r, h // 2 + r)).resize((C, C), Image.LANCZOS)

    balls = [b for b in ["void", "frost", "toxic"] if ren(b) or ren(b + "p")]
    if not balls:
        return
    sheet = Image.new("RGB", (10 + 5 * (C + 10), 50 + len(balls) * (C + 34)), BG)
    d = ImageDraw.Draw(sheet)
    label(d, 10, 12, "Fidelity: concept | A procedural | B concept-projected | 50/50 A | 50/50 B (front, dark backdrop, same size)", BIG)
    y = 50
    for b in balls:
        con = Image.open(CONCEPTS[b]).convert("RGB").crop(CONCEPT_BALL[b]).resize((C, C), Image.LANCZOS)
        a, bb = ren(b), ren(b + "p")
        tiles = [("concept: " + NAMES[b], con), ("A procedural", a), ("B concept-projected", bb),
                 ("50/50 A", Image.blend(con, a, 0.5) if a else None), ("50/50 B", Image.blend(con, bb, 0.5) if bb else None)]
        for i, (title, im) in enumerate(tiles):
            label(d, 10 + i * (C + 10), y, title)
            if im:
                sheet.paste(im, (10 + i * (C + 10), y + 24))
        y += C + 34
    sheet.save(os.path.join(OUT, "fidelity.png"))
    print("fidelity sheet in", OUT)


load = load_any
if os.path.exists(os.path.join(SRC, "void_concept_t%s.png" % TIMES[0])) or os.path.exists(os.path.join(SRC, "frost_concept_t%s.png" % TIMES[0])) or os.path.exists(os.path.join(SRC, "toxic_concept_t%s.png" % TIMES[0])):
    fidelity(TIMES[0])
if os.path.exists(os.path.join(SRC, "void_customize_t%s_v0.png" % TIMES[0])) or os.path.exists(os.path.join(SRC, "frost_customize_t%s_v0.png" % TIMES[0])):
    grid_sheet()
    print("grid sheets in", OUT)
    raise SystemExit
comparison()
if len(TIMES) > 1:
    motion()
if os.path.exists(os.path.join(SRC, "void_customize_t%s_a0.5.png" % TIMES[0])):
    aura_sheet()
print("sheets in", OUT)
