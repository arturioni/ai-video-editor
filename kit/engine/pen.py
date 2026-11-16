"""Pen strokes drawn on over time: hand-drawn (pressure, taper, a wobble and three copies that swap at 8 fps,
like line boil) or clean (smooth lines of even width). The style's "marks" setting picks which.

Every stroke is an SVG path revealed by a mask, queued on the shared GSAP timeline `tl`.
"""
import json, math, os, random, shutil

BOIL_FPS = 8
VARIANTS = 3
CLEAN = [False]        # set by reel.py from the style: True draws even, smooth lines

tl, based, sfx, defs_count = [], set(), [], [0]


def ft(sel, frm, to, at):
    fr = json.dumps(frm)
    if sel not in based:
        based.add(sel)
        tl.append(f'tl.set("{sel}", {fr}, 0);')
    tl.append(f'tl.fromTo("{sel}", {fr}, {json.dumps({**to, "immediateRender": False})}, {max(0, at):.3f});')


def catmull(pts, step=8.0):
    """dense polyline through the control points"""
    if len(pts) == 2:
        pts = [pts[0], ((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2), pts[1]]
    p = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        n = max(4, int(math.dist(p1, p2) / step))
        for k in range(n):
            t = k / n
            out.append(tuple(0.5 * (2 * p1[a] + (p2[a] - p0[a]) * t + (2 * p0[a] - 5 * p1[a] + 4 * p2[a] - p3[a]) * t * t
                                    + (3 * p1[a] - p0[a] - 3 * p2[a] + p3[a]) * t ** 3) for a in (0, 1)))
    out.append(pts[-1])
    return out


def normals(line):
    res = []
    for i in range(len(line)):
        a, b = line[max(i - 1, 0)], line[min(i + 1, len(line) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx, dy) or 1
        res.append((-dy / d, dx / d))
    return res


def noise_fn(r, amp, wave):
    ph = [r.uniform(0, 6.28) for _ in range(3)]
    return lambda s: amp * (0.6 * math.sin(s / wave + ph[0]) + 0.3 * math.sin(s / (wave * 0.43) + ph[1]) + 0.2 * math.sin(s / (wave * 0.17) + ph[2]))


def wobble(line, fn):
    ns, s, out = normals(line), 0.0, []
    for i, p in enumerate(line):
        if i:
            s += math.dist(line[i - 1], p)
        d = fn(s)
        out.append((p[0] + ns[i][0] * d, p[1] + ns[i][1] * d))
    return out


def ink_shape(line, width, fn):
    """filled outline: width follows pressure and tapers at both ends"""
    ns, total, s, left, right = normals(line), 0.0, 0.0, [], []
    for i in range(1, len(line)):
        total += math.dist(line[i - 1], line[i])
    for i, p in enumerate(line):
        if i:
            s += math.dist(line[i - 1], p)
        taper = min(1.0, 0.3 + min(s, total - s) / 22.0)
        w = width * (0.82 + 0.3 * fn(s)) * taper / 2
        left.append((p[0] + ns[i][0] * w, p[1] + ns[i][1] * w))
        right.append((p[0] - ns[i][0] * w, p[1] - ns[i][1] * w))
    pts = left + right[::-1]
    return "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + "Z"


def stroke(pts, at, dur, width=6.5, seed=None, amp=2.6, pen=True, k=3.4):
    """one pen stroke: returns svg markup (mask + 3 boil copies) and queues the draw-on"""
    defs_count[0] += 1
    n = defs_count[0]
    r = random.Random(1000 + (seed if seed is not None else n))
    clean = CLEAN[0]
    base = wobble(catmull(pts), noise_fn(r, 0 if clean else amp, 70))
    press = (lambda s_: 0.0) if clean else noise_fn(r, 1.0, 55)
    d_mask = "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in base)
    copies = []
    for v in range(1 if clean else VARIANTS):
        rv = random.Random(7000 + n * 10 + v)
        shape = ink_shape(base if clean else wobble(base, noise_fn(rv, 1.1, 34)), width, press)
        copies.append(f'<path{"" if clean else f' class="v{v}"'} d="{shape}"/>')
    ft(f"#st{n}", {"opacity": 0}, {"opacity": 1, "duration": 0.01}, at)
    # lengths are in thousandths: GSAP rounds px values to whole numbers, so a 0 to 1 range snaps at the midpoint
    ft(f"#mp{n}", {"strokeDashoffset": 1020}, {"strokeDashoffset": 0, "duration": dur, "ease": "power1.inOut"}, at)
    if pen:
        sfx.append({"t": round(at, 3), "d": round(dur, 3)})
    return (f'<mask id="m{n}" maskUnits="userSpaceOnUse" x="-100" y="-100" width="1400" height="2200">'
            f'<path id="mp{n}" d="{d_mask}" pathLength="1000" fill="none" stroke="#fff" stroke-width="{width * k:.1f}" '
            f'stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="1020 1020"/></mask>'
            f'<g id="st{n}" class="st" mask="url(#m{n})">{"".join(copies)}</g>')


def ellipse(cx, cy, rx, ry, start=-2.2, turns=1.1, tilt=-0.05):
    pts = []
    for k in range(int(26 * turns) + 1):
        a = start + k / 26 * 6.283
        grow = 1 + 0.05 * k / 26          # a hand doesn't close a circle on itself
        x, y = rx * grow * math.cos(a), ry * grow * math.sin(a)
        pts.append((cx + x * math.cos(tilt) - y * math.sin(tilt), cy + x * math.sin(tilt) + y * math.cos(tilt)))
    return pts


def arrow(pts, at, dur, width=6):
    """swoop + a two-stroke head, angled off the curve's end"""
    (x1, y1), (x2, y2) = pts[-2], pts[-1]
    a = math.atan2(y2 - y1, x2 - x1)
    head = lambda o, L: [(x2 + L * math.cos(a + o), y2 + L * math.sin(a + o)), (x2, y2)]
    return (stroke(pts, at, dur, width) + stroke(head(2.6, 44), at + dur, 0.09, width)
            + stroke(head(-2.5, 40), at + dur + 0.09, 0.09, width))
