"""Drawing basics shared by the engine: pen-stroke batches, big words, bursts, and the list of scenes.

Colours are CSS variables, so the same scene code works in any style: FG is the text colour of whatever
ground the scene sits on, ACCENT is the style's accent for that ground. reel.py fills them in from the style.
"""
import json, math, os, random, shutil
import pen
from pen import tl, ft, stroke, ellipse, catmull

FG, ACCENT = "var(--fg)", "var(--accent)"
FPS = 8

T = {}
scenes = []


def plen(pts):
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


class Sk:
    """a batch of pen strokes drawn one after the other between two times"""

    def __init__(self):
        self.items = []

    def add(self, pts, w=6.0, color=FG, amp=2.2, k=3.4):
        self.items.append((pts, w, color, amp, k))
        return self

    def play(self, t0, t1, cls="draw", z=6):
        lens = [max(20, plen(i[0])) for i in self.items]
        total = sum(lens)
        t, out = t0, []
        for (pts, w, color, amp, k), l in zip(self.items, lens):
            d = max(0.04, (t1 - t0) * l / total)
            out.append(f'<g style="fill:{color}">{stroke(pts, t, d, w, amp=amp, k=k)}</g>')
            t += d
        return f'<svg class="{cls}" style="z-index:{z}" viewBox="0 0 1080 1920">{"".join(out)}</svg>'


def big(html, top, size, color=FG, extra=""):
    """words in the style's headline font, centred across the frame with its top edge at `top`"""
    return f'<div class="big" style="top:{top}px;font-size:{size}px;color:{color};{extra}">{html}</div>'


heavy = big           # older name


def scene(sid, start, end, bg, body):
    """one scene: from `start` to `end` on ground "main", "alt" or "photo" """
    scenes.append((sid, start, end, bg, body))


def burst(sk, cx, cy, r0, r1, n=12, color=ACCENT, w=5, skip=()):
    for i in range(n):
        a = i / n * 6.283 + 0.2
        if any(lo <= a <= hi for lo, hi in skip):
            continue
        sk.add([(cx + r0 * math.cos(a), cy + r0 * math.sin(a)), (cx + r1 * math.cos(a), cy + r1 * math.sin(a))], w, color, 1)
