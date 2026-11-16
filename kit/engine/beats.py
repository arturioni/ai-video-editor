"""Ready-made scene pieces. Each returns HTML for a scene and queues its own animation, sound moments and
self-check moments, so a scenes.py stays short. Colours default to the style: FG is the text colour of the
scene's ground, ACCENT the style's accent. Pass color= only to override.

    from beats import *       # brings in reel.py's helpers too

Coordinates are pixels on the 1080x1920 frame. Keep words and key marks between y=240 and y=1560:
Instagram and TikTok cover the rest with their buttons and captions.
"""
from reel import *

_n = [0]


def _id(prefix):
    _n[0] += 1
    return f"{prefix}{_n[0]}"


def fit(text, most=None):
    """the biggest headline size that keeps `text` on one row across the frame"""
    most = most or HEADLINE
    return int(min(most, 1450 / max(1, len(text))))


def stamp(text, top, size, at, color=FG, noise=True, extra=""):
    """big words in the headline font that arrive at `at` (stamp or soft rise, per the style's motion)"""
    hid = _id("h")
    land(f"#{hid}", at, noise, what=f"'{re.sub('<[^>]+>', ' ', text).strip()}' arrived")
    return big(text, top, size, color, extra).replace('class="big"', f'id="{hid}" class="big"')


def stack(key, rows, color=FG):
    """a title made of stacked rows of big words, each arriving on a word of the line.
    rows: [(text, size, top, word or None, color or None)]; word None = at the scene's cut"""
    out = ""
    for text, size, top, word, col in rows:
        at = T[key] + 0.04 if word is None else start_of(key, word)
        out += stamp(text, top, size, at, col or color)
    return out


def label(text, top, at=None, color=FG, size=30):
    """a small spaced-out label, e.g. "STEP 2 OF 5" """
    lid = _id("lb")
    if at is not None:
        show(f"#{lid}", at)
    return f'<div class="label" id="{lid}" style="top:{top}px;color:{color};font-size:{size}px">{text}</div>'


def note(text, top, at=None, color=FG, size=56):
    """a quieter line in the body font, next to big words"""
    nid = _id("nt")
    if at is not None:
        show(f"#{nid}", at)
    return f'<div class="note" id="{nid}" style="top:{top}px;color:{color};font-size:{size}px">{text}</div>'


serif = note          # older name


def strike(x1, y1, x2, y2, at, color=ACCENT, width=17, dur=0.24):
    """a pen line struck through words"""
    mid = ((x1 + x2) / 2, (y1 + y2) / 2 - 18)
    sound("scribble", at)
    moment(at + dur + 0.1, "strike drawn")
    return Sk().add([(x1, y1), mid, (x2, y2)], width, color, 1.6).play(at, at + dur, z=8)


def circle(cx, cy, rx, ry, at, color=ACCENT, width=10, dur=0.35):
    """a drawn ring around something"""
    sound("scribble", at)
    moment(at + dur + 0.1, "circle drawn")
    return Sk().add(ellipse(cx, cy, rx, ry, tilt=-0.06), width, color, 2).play(at, at + dur, z=8)


def underline(x1, x2, y, at, color=ACCENT, width=9, dur=0.22):
    moment(at + dur + 0.1, "underline drawn")
    pts = [(x1, y + 4), ((x1 * 2 + x2) / 3, y - 3), ((x1 + x2 * 2) / 3, y + 5), (x2, y - 2)]
    return Sk().add(pts, width, color, 1.1).play(at, at + dur, z=8)


def pen_arrow(pts, at, color=ACCENT, width=8, dur=0.3):
    """a swooping arrow along pts, head at the last point"""
    moment(at + dur + 0.3, "arrow drawn")
    body = pen.arrow(pts, at, dur, width)
    return f'<svg class="draw" style="z-index:8" viewBox="0 0 1080 1920"><g style="fill:{color}">{body}</g></svg>'


def tick(x, y, at, color=ACCENT, size=1.0, dur=0.24):
    moment(at + dur + 0.1, "tick drawn")
    return Sk().add([(x, y), (x + 40 * size, y + 48 * size), (x + 133 * size, y - 88 * size)], 14, color, 1).play(at, at + dur, z=8)


def rays(cx, cy, r0, r1, at, n=12, color=ACCENT, width=7, dur=0.3, skip=()):
    """burst lines around a point: something just happened here"""
    sk = Sk()
    burst(sk, cx, cy, r0, r1, n, color, width, skip)
    moment(at + dur + 0.1, "burst drawn")
    return sk.play(at, at + dur, z=8)


def count(key, values, final, on_word, top=700, size=None, color=FG, final_color=None, final_size=None):
    """numbers flick through `values` from the cut, then `final` arrives on `on_word`"""
    size = size or HEADLINE
    t0, at = T[key], start_of(key, on_word)
    step = max(0.06, (at - t0) / max(1, len(values)))
    out = ""
    for i, v in enumerate(values):
        nid = _id("n")
        a = t0 + i * step
        if a >= at:
            break
        show(f"#{nid}", a, min(a + step, at + 0.06) if i < len(values) - 1 else at + 0.06)   # held under the arrival's first step
        out += big(v, top, size, color).replace('class="big"', f'id="{nid}" class="big"')
    out += stamp(final, top - 40 if final_size else top, final_size or size, at, final_color or color)
    return out


def takeover(key, rows, at=None):
    """the reel's one big moment: the accent colour fills the frame from the centre, words arrive on it.
    rows: [(text, size, top, word or None)]. Use it once, on the turn."""
    t0 = T[key] if at is None else at
    tid = _id("tk")
    html = f'<div id="{tid}" style="position:absolute;inset:0;background:{ACCENT};z-index:3"></div>'
    ft(f"#{tid}", {"clipPath": "circle(0% at 50% 45%)"}, {"clipPath": "circle(80% at 50% 45%)", "duration": 0.32, "ease": "power3.out"}, t0 + 0.02)
    sound("hit", t0 + 0.02)
    moment(t0 + 0.4, "accent fills the frame")
    TAKEOVERS.append((t0 - 0.1, end_cut(key)))
    for text, size, top, word in rows:
        at_ = t0 + 0.1 if word is None else start_of(key, word)
        html += stamp(text, top, size, at_, ON_ACCENT, noise=False)
    return html




def typed(key, text, top=330, color=FG, marks=(), size=76, left=100, width=880):
    """a sentence typed letter by letter as it's spoken (its words must be in the line, in order).
    marks: words or phrases inside `text` that get an accent underline once typed"""
    words = text.split()
    k0 = wi(key, words[0])
    ct = []
    for j, token in enumerate(words):
        ws, we = S[k0 + j], E[k0 + j]
        ct += [ws + (we - ws) * n / len(token) for n in range(len(token))]
        ct.append(we)
    tid = _id("ty")

    def chars(txt, off):
        return "".join(f'<span id="{tid}c{off + i}">{" " if ch == " " else ch}</span>' for i, ch in enumerate(txt))

    pos, parts, rest = 0, [], text
    for m in marks:
        i = rest.index(m)
        parts.append(chars(rest[:i], pos))
        pos += i
        u_at = ct[pos + len(m) - 1]
        u = f'<svg class="under" viewBox="0 0 300 30" preserveAspectRatio="none"><g style="fill:{ACCENT}">{stroke([(4, 16), (80, 12), (160, 18), (296, 10)], u_at, 0.2, 7, amp=1.1)}</g></svg>'
        parts.append(f'<span class="mk">{chars(m, pos)}{u}</span>')
        pos += len(m)
        rest = rest[i + len(m):]
    parts.append(chars(rest, pos))
    for i in range(len(text)):
        tl.append(f'tl.set("#{tid}c{i}", {{opacity: 0}}, 0); tl.set("#{tid}c{i}", {{opacity: 1}}, {ct[i]:.3f});')
    for i in range(0, len(ct), 3):
        sound("key", ct[i])
    moment(ct[-1] + 0.1, "sentence typed")
    return f'<div class="sent" style="top:{top}px;left:{left}px;width:{width}px;font-size:{size}px;color:{color}">{"".join(parts)}</div>'


def stamp_words(key, words_rows, color=FG):
    """the call to action: each word arrives as it's spoken. words_rows: [(word in the line, size, top, accent?)]"""
    out = ""
    for word, size, top, acc in words_rows:
        out += stamp(word.strip(".,!?"), top, size, start_of(key, word), ACCENT if acc else color)
    return out


# ---------------------------------------------------------------- doodles
# Simple hand-drawn icons, drawn on with the pen. Points live in a 200 x 200 box centred on (0, 0), y down.

def _arc(cx, cy, r, a0, a1, n=14):
    return [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cy + r * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]


def _closed(pts):
    return catmull(pts + pts[:1], 6)


DOODLES = {
    "sun": lambda: [ellipse(0, 0, 42, 42)] + [[(62 * math.cos(k * 0.785), 62 * math.sin(k * 0.785)), (90 * math.cos(k * 0.785), 90 * math.sin(k * 0.785))] for k in range(8)],
    "cloud": lambda: [_closed([(-80, 30), (-92, 6), (-72, -16), (-46, -14), (-34, -46), (0, -56), (30, -42), (42, -16), (70, -22), (92, 4), (80, 30)])],
    "plane": lambda: [_closed([(-90, 0), (-70, -11), (60, -12), (86, -4), (90, 2), (80, 9), (-70, 10)]),
                      [(-8, 6), (28, 58), (44, 58), (18, 6)], [(-70, -8), (-86, -46), (-72, -46), (-50, -11)]],
    "shaker": lambda: [[(-35, -30), (-46, 82), (46, 82), (35, -30), (-35, -30)], catmull([(-35, -30), (-30, -60), (0, -66), (30, -60), (35, -30)], 6),
                       ellipse(-14, -48, 4, 4), ellipse(0, -52, 4, 4), ellipse(14, -48, 4, 4)],
    "glass": lambda: [[(-46, -72), (-36, 82), (36, 82), (46, -72)], [(-42, -20), (42, -20)], [(14, -20), (36, -104)]],
    "nose": lambda: [catmull([(-22, -96), (-8, -50), (10, -4), (38, 34), (36, 52), (18, 60), (0, 56)], 6), catmull([(10, 42), (0, 50), (-10, 46)], 4)],
    "smell": lambda: [catmull([(x, 84), (x - 16, 42), (x + 14, 0), (x - 14, -42), (x + 6, -84)], 6) for x in (-44, 0, 44)],
    "ear": lambda: [catmull([(-10, 92), (-34, 62), (-46, 0), (-30, -62), (10, -86), (46, -60), (52, -10), (32, 30), (16, 56), (10, 82), (-10, 92)], 6),
                    catmull([(-2, -46), (24, -36), (24, -6), (6, 14), (6, 36)], 6)],
    "waves": lambda: [_arc(-80, 0, r, -0.75, 0.75) for r in (40, 80, 120)],
    "clock": lambda: [ellipse(0, 0, 82, 82), [(0, 0), (0, -56)], [(0, 0), (42, 16)]],
    "bulb": lambda: [catmull([(-24, 56), (-30, 30), (-56, 0), (-56, -40), (-30, -76), (0, -86), (30, -76), (56, -40), (56, 0), (30, 30), (24, 56)], 6),
                     [(-24, 66), (24, 66)], [(-18, 82), (18, 82)]],
    "heart": lambda: [catmull([(0, 80), (-60, 20), (-86, -26), (-66, -66), (-26, -70), (0, -36), (26, -70), (66, -66), (86, -26), (60, 20), (0, 80)], 6)],
    "drop": lambda: [catmull([(0, -84), (-34, -10), (-46, 30), (-30, 62), (0, 74), (30, 62), (46, 30), (34, -10), (0, -84)], 6)],
    "phone": lambda: [catmull([(-44, -92), (44, -92), (52, -84), (52, 84), (44, 92), (-44, 92), (-52, 84), (-52, -84), (-44, -92)], 4), ellipse(0, 72, 7, 7)],
    "x": lambda: [[(-62, -62), (62, 62)], [(62, -62), (-62, 62)]],
    "star": lambda: [[(90 * math.cos(-1.571 + k * 2.513), 90 * math.sin(-1.571 + k * 2.513)) for k in range(6)]],
}


def doodle(name, cx, cy, size=220, at=None, dur=0.55, color=FG, width=8):
    """a hand-drawn icon drawn on at `at`: """ + ", ".join(sorted(DOODLES)) + """.
    (cx, cy) is its centre, size its width in pixels."""
    if name not in DOODLES:
        sys.exit(f"No doodle called '{name}'. There are: {', '.join(sorted(DOODLES))}")
    k = size / 200
    sk = Sk()
    for stroke_pts in DOODLES[name]():
        sk.add([(cx + x * k, cy + y * k) for x, y in stroke_pts], max(5, width * k ** 0.5), color, 1.2)
    t = T[next(iter(T))] if at is None else at
    sound("scribble", t)
    moment(t + dur + 0.1, f"{name} drawn")
    return sk.play(t, t + dur, z=7)
