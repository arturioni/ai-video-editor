#!/usr/bin/env python3
"""The engine under every voiced reel. The look comes from the user's style (My Style/style.json), not from here.

A reel's scenes.py does:  from beats import *  ->  begin(__file__, LINES)  ->  its scenes  ->  finish()

begin() reads the reel's script.txt, assets/voice/voice.wav and voice.words.json. The transcriber's word times
drift, so they are pinned to the real silences in the audio. Long gaps between sentences are cut down (and a
recorded human voice is sped up a little), and every scene, caption and mark then sits on a word.

Everything is written inside the reel's own folder (work/<reel>/), so reels never step on each other:
  renders/project/          the HyperFrames project: index.html, timing.json, assets/ (copied in at each build)
  renders/voice.timed.wav   the voice as the reel plays it
  renders/sound/events.json the moments for the sound pass
"""
import re, subprocess, sys
from types import SimpleNamespace
import numpy as np
import kitpaths
from draw import *

ST, OWN_STYLE = kitpaths.style()
pen.CLEAN[0] = ST.get("marks", "clean") == "clean"
C = ST["colors"]

SENTENCE_GAP = 0.16            # longest silence kept between sentences
BEAT_GAP = 0.28                # except after the line named in begin(beat_after=...)
VFPS = 30
CAP = ST["captions"]
CAP_TOP = int(CAP.get("y", 1420))
CAP_MAX_WORDS = int(CAP.get("max_words", 4))
CAP_MAX_CHARS = int(900 / (0.55 * float(CAP.get("size", 54))))
HEADLINE = int(ST.get("headline_size", 190))
TRANSITIONS = ("cut", "slide", "zoom", "fade", "wipe", "flash")

raw, S, E, first, last, NEXT = [], [], [], {}, {}, {}
rootcaps, overlays, MOVES, EVENTS, CAPS, MOMENTS = [], [], [], [], [], []
TAKEOVERS = []                 # (start, end) of full-screen accent moments: captions there use the colour that reads on the accent
_R = SimpleNamespace(dir=None, slug=None, lines=None, total=None, voice_len=None, tempo=1.0)
norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
linspace = lambda a, b, n: [a + (b - a) * k / (n - 1) for k in range(n)]


def _lum(hex_):
    h = hex_.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


ON_ACCENT = C.get("text_on_accent") or ("#111111" if _lum(C["accent"]) > 0.4 else "#FFFFFF")
GROUND = {   # ground -> (background, text, accent)
    "main": (C["main"], C["text_on_main"], C["accent"]),
    "alt": (C["alt"], C["text_on_alt"], C.get("accent_on_alt", C["accent"])),
    "photo": ("#000000", C.get("text_on_photo", "#FFFFFF"), C["accent"]),
}


def project(rel=""):
    """a path inside this reel's own HyperFrames project"""
    return os.path.join(_R.dir, "renders", "project", rel)


def asset(rel):
    """a path inside this reel's assets folder"""
    return os.path.join(_R.dir, "assets", rel)


def _make_project():
    """a fresh HyperFrames project with the kit's and the user's fonts copied in (no links, so it works on Windows)"""
    os.makedirs(project("assets"), exist_ok=True)
    os.makedirs(os.path.join(_R.dir, "renders", "sound"), exist_ok=True)
    shutil.copy(os.path.join(kitpaths.KIT, "hyperframes.json"), project())
    shutil.copytree(os.path.join(kitpaths.ASSETS, "fonts"), project("assets/fonts"), dirs_exist_ok=True)
    shutil.copy(os.path.join(kitpaths.ASSETS, "grain.png"), project("assets/grain.png"))
    user_fonts = os.path.join(kitpaths.MY_STYLE, "fonts")
    if OWN_STYLE and os.path.isdir(user_fonts):
        shutil.copytree(user_fonts, project("assets/userfonts"), dirs_exist_ok=True)
    if os.path.isdir(asset("f")):
        shutil.copytree(asset("f"), project("assets/f"), dirs_exist_ok=True)


def _pcm(path):
    r = subprocess.run([kitpaths.ffmpeg(), "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", "48000", "-"],
                       capture_output=True, check=True, env=kitpaths.env())
    return np.frombuffer(r.stdout, dtype="float32").copy()


def begin(scenes_file, lines, heard=None, beat_after=None, ready_after=None):
    """lines: (key, words, "cut" or "move"), together the whole of script.txt. "move" lines come in with the
    style's transition (slide, zoom, fade...); "cut" lines on a plain cut. Every cut lands on the line's first word.
    heard: {line: {word: seconds}}, word starts measured by ear where the transcriber is off (rarely needed).
    beat_after: the line that keeps a longer pause after it."""
    _R.dir = os.path.dirname(os.path.abspath(scenes_file))
    _R.slug = os.path.basename(_R.dir)
    _R.lines = [(k, t, h) for k, t, h in lines]
    lines = _R.lines
    for k, _, h in lines:
        if h not in ("cut", "move"):
            sys.exit(f"Line '{k}': the third part must be \"cut\" or \"move\", not {h!r}.")
    if not OWN_STYLE:
        print("note: no My Style/style.json yet, so the neutral \"clean\" starter look is used. Say \"set up my style\" to make it yours.")
    _make_project()

    script = open(os.path.join(_R.dir, "script.txt"), encoding="utf-8").read().split()
    spoken = " ".join(text for _, text, _ in lines).split()
    if [norm(w) for w in script] != [norm(w) for w in spoken]:
        sys.exit("scenes.py LINES and script.txt don't match word for word. Make them the same, then build again.")

    wav = asset("voice/voice.wav")
    if not os.path.exists(wav):
        sys.exit(f"No voice yet. Run: uv run --project kit kit/run.py voice {_R.slug}")
    raw[:] = json.load(open(asset("voice/voice.words.json"), encoding="utf-8"))
    meta_path = asset("voice/voice.meta.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    _R.tempo = float(meta.get("tempo", kitpaths.settings()["own_voice_tempo"]))

    # ---------- where each line sits in the word list
    i = 0
    for key, text, _ in lines:
        n = len(text.split())
        if [norm(w["w"]) for w in raw[i:i + n]] != [norm(w) for w in text.split()]:
            sys.exit(f"Line '{key}' doesn't match the voice. The script changed after the voice was made: run the voice step again.")
        first[key], last[key] = i, i + n - 1
        i += n
    assert i == len(raw), f"{i} of {len(raw)} words placed"

    # ---------- real word timing: the transcriber's times drift, so pin them to the silences in the audio
    pcm = _pcm(wav)
    frame = 480                    # 10 ms
    env = np.sqrt(np.convolve(pcm ** 2, np.ones(frame) / frame, mode="same"))[::frame]
    quiet = env < 0.006
    gaps, k = [], 0
    while k < len(quiet):
        if quiet[k]:
            j = k
            while j < len(quiet) and quiet[j]:
                j += 1
            if j - k >= 6:         # at least 60 ms
                gaps.append((k * 0.01, j * 0.01))
            k = j
        else:
            k += 1
    voiced = np.where(~quiet)[0]
    heard_at, true_at = [raw[0]["s"], raw[-1]["e"]], [voiced[0] * 0.01, voiced[-1] * 0.01 + 0.01]
    for k in range(len(raw) - 1):
        if raw[k]["w"][-1] not in ".?!:,;":
            continue
        mid = (raw[k]["e"] + raw[k + 1]["s"]) / 2
        near = [g for g in gaps if g[1] > mid - 0.15 and g[0] < mid + 0.6]
        if near:
            g = max(near, key=lambda g: g[1] - g[0])
            heard_at += [raw[k]["e"], raw[k + 1]["s"] if raw[k + 1]["s"] > raw[k]["e"] else raw[k]["e"] + 0.001]
            true_at += [g[0], g[1]]
    order = np.argsort(heard_at)
    heard_at, true_at = np.array(heard_at)[order], np.maximum.accumulate(np.array(true_at)[order])
    pin = lambda t: float(np.interp(t, heard_at, true_at))
    for w in raw:
        w["s"], w["e"] = pin(w["s"]), pin(w["e"])

    # ---------- the voice as it plays: long silences trimmed, and sped up if it's a recorded voice
    removed = []
    E_beat = raw[last[beat_after]]["e"] if beat_after in last else None
    for a, b_ in gaps:
        keep = BEAT_GAP if E_beat is not None and abs(a - E_beat) < 0.15 else SENTENCE_GAP
        if a < voiced[0] * 0.01 + 0.01 or b_ > voiced[-1] * 0.01:
            continue
        if b_ - a > keep:
            mid = (a + b_) / 2
            removed.append((mid - (b_ - a - keep) / 2, mid + (b_ - a - keep) / 2))
    removed = [(0.0, max(0.0, voiced[0] * 0.01 - 0.03))] + removed

    def squeeze(t):
        return (t - sum(max(0.0, min(t, b_) - a) for a, b_ in removed)) / _R.tempo

    chunks, pos = [], 0
    for a, b_ in removed:
        chunks.append(pcm[pos:int(a * 48000)])
        pos = int(b_ * 48000)
    chunks.append(pcm[pos:int((voiced[-1] * 0.01 + 0.25) * 48000)])
    kept = np.concatenate([c for c in chunks if len(c)])
    timed = os.path.join(_R.dir, "renders", "voice.timed.wav")
    af = f"atempo={_R.tempo}" if abs(_R.tempo - 1) > 1e-3 else "anull"
    subprocess.run([kitpaths.ffmpeg(), "-v", "error", "-y", "-f", "f32le", "-ar", "48000", "-ac", "1", "-i", "-", "-af", af, timed],
                   input=kept.tobytes(), check=True, env=kitpaths.env())
    _R.voice_len = kitpaths.duration(timed)
    S[:] = [squeeze(w["s"]) for w in raw]
    E[:] = [squeeze(w["e"]) for w in raw]

    # ---------- cuts: every scene starts on its line's first word
    T.clear()
    T[lines[0][0]] = 0.0
    for n in range(1, len(lines)):
        T[lines[n][0]] = round(S[first[lines[n][0]]] - 0.04, 3)
    for line_, words_ in (heard or {}).items():
        for word_, at_ in words_.items():
            S[wi(line_, word_)] = at_
    NEXT.update({lines[n][0]: (lines[n + 1][0] if n + 1 < len(lines) else None) for n in range(len(lines))})
    total()


def total(at_least=0):
    """the reel's length: the voice plus 0.3 s, or longer if the last scene needs it"""
    _R.total = round(max(at_least, _R.voice_len + 0.3), 3)
    return _R.total


def wi(key, word, nth=0):
    hits = [k for k in range(first[key], last[key] + 1) if norm(raw[k]["w"]) == norm(word)]
    if not hits:
        sys.exit(f"'{word}' isn't in line '{key}'. Words there: {' '.join(raw[k]['w'] for k in range(first[key], last[key] + 1))}")
    return hits[nth]


start_of = lambda key, word, nth=0: S[wi(key, word, nth)]
end_of = lambda key, word, nth=0: E[wi(key, word, nth)]
line_start = lambda key: S[first[key]]
line_end = lambda key: E[last[key]]
end_cut = lambda key: T[NEXT[key]] if NEXT[key] else _R.total
on_frame = lambda t: round(t * VFPS) / VFPS


def sound(label, t):
    """a moment for the sound pass: "land", "hit", "scribble", "key" (transitions and cuts are added for you)"""
    EVENTS.append({"t": round(t, 3), "label": label})


def moment(t, what=""):
    """a time the self-check should look at (a mark finishing, a word landing)"""
    MOMENTS.append((round(t, 3), what))


def split_caps(text, max_words=None, max_chars=None):
    """a line cut into short caption phrases: breaks after punctuation first, then by length"""
    max_words, max_chars = max_words or CAP_MAX_WORDS, max_chars or CAP_MAX_CHARS
    words, out, cur = text.split(), [], []
    for w in words:
        cand = cur + [w]
        if cur and (len(cand) > max_words or len(" ".join(cand)) > max_chars):
            out.append(cur)
            cur = [w]
        else:
            cur = cand
        if cur and w[-1] in ".,?!:;" and len(cur) >= 2:
            out.append(cur)
            cur = []
    if cur:
        if out and len(cur) == 1 and len(out[-1]) < max_words and len(" ".join(out[-1] + cur)) <= max_chars + 4:
            out[-1] += cur                     # no lone last word
        else:
            out.append(cur)
    return [" ".join(c) for c in out]


def caps(key, chunks=None, hold=None, color=None, top=None, shadow=None):
    """captions on the words: each phrase starts on its first word, the last stays until the scene ends.
    chunks: the line split into phrases yourself, or None to split it automatically.
    The look (size, box or shadow, colour) comes from the style; color/top override it for this line."""
    if chunks is None:
        chunks = split_caps(" ".join(raw[j]["w"] for j in range(first[key], last[key] + 1)))
    k = first[key]
    if hold is None:           # the next line takes over the moment it's spoken
        hold = min(end_cut(key), S[first[NEXT[key]]] - 0.01) if NEXT[key] else end_cut(key)
    timed_chunks = []
    for c in chunks:
        n = len(c.split())
        if [norm(w) for w in c.split()] != [norm(raw[j]["w"]) for j in range(k, k + n)]:
            sys.exit(f"Caption '{c}' doesn't match the words of line '{key}' in order.")
        timed_chunks.append((c, S[k]))
        k += n
    if k != last[key] + 1:
        sys.exit(f"The captions for '{key}' stop before the end of the line.")
    for i, (c, t) in enumerate(timed_chunks):
        cid = f"{key}-c{i}"
        off = hold if i == len(timed_chunks) - 1 else timed_chunks[i + 1][1] - 0.01
        tl.append(f'tl.set("#{cid}", {{opacity: 0}}, 0); tl.set("#{cid}", {{opacity: 1}}, {t:.3f}); tl.set("#{cid}", {{opacity: 0}}, {off:.3f});')
        CAPS.append({"id": cid, "line": key, "text": c, "on": round(t, 3), "off": round(off, 3), "chars": len(c),
                     "color": color, "shadow": shadow, "top": top or CAP_TOP})


def _ground_at(t):
    for sid, s_, e, bg, _ in scenes:
        if s_ <= t < e:
            return bg
    return scenes[-1][3] if scenes else "main"


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _caption_html():
    out, kind = [], CAP.get("style", "shadow")
    for c in CAPS:
        _, fg, _ = GROUND.get(_ground_at(c["on"] + 0.05), GROUND["main"])
        if any(a_ <= c["on"] + 0.05 < b_ for a_, b_ in TAKEOVERS):
            fg = ON_ACCENT
        text = _esc(c["text"])
        if kind == "box" and c["color"] is None:
            out.append(f'<div class="cap" id="{c["id"]}" style="top:{c["top"]}px"><span class="boxed">{text}</span></div>')
            continue
        color = c["color"] or ("#FFFFFF" if kind == "outline" else fg)
        cls = {"shadow": "cap sh", "outline": "cap ol"}.get(kind, "cap")
        if c["shadow"] is True:
            cls = "cap sh"
        elif c["shadow"] is False:
            cls = "cap"
        out.append(f'<div class="{cls}" id="{c["id"]}" style="top:{c["top"]}px;color:{color}">{text}</div>')
    return "".join(out)


def photo(pid, file, t0, t1):
    """a full-frame picture from assets/f/<file>.jpg with a slow push-in"""
    if not os.path.exists(asset(f"f/{file}.jpg")):
        sys.exit(f"Picture assets/f/{file}.jpg is missing. Make it with: kit/run.py pictures use {_R.slug} {file} <number or file>")
    ft(f"#{pid}", {"scale": 1}, {"scale": 1.045, "duration": t1 - t0, "ease": "none"}, t0)
    return f'<img id="{pid}" src="assets/f/{file}.jpg" style="position:absolute;left:0;top:0;width:1080px;height:1920px">'


def grad(where, h, strength=0.72):
    """a dark fade at the top or bottom of a photo so words stay readable"""
    sh = C.get("shade", "#000000").lstrip("#")
    r, g, b = (int(sh[i:i + 2], 16) for i in (0, 2, 4))
    side = "top:0" if where == "top" else "bottom:0"
    to = "bottom" if where == "top" else "top"
    return (f'<div style="position:absolute;left:0;right:0;{side};height:{h}px;z-index:2;background:linear-gradient(to {to},'
            f'rgba({r},{g},{b},{strength}) 0%,rgba({r},{g},{b},{strength * 0.9:.3f}) 48%,rgba({r},{g},{b},0) 100%)"></div>')


def land(sel, at, noise=True, what=None):
    """words or a picture arriving: a two-step stamp (style motion "snappy") or a soft rise ("smooth")"""
    if ST.get("motion") == "smooth":
        ft(sel, {"opacity": 0, "y": 46}, {"opacity": 1, "y": 0, "duration": 0.34, "ease": "power3.out"}, at)
    else:
        ft(sel, {"opacity": 0, "scale": 1.16}, {"opacity": 1, "scale": 1, "duration": 0.12, "ease": "steps(2)"}, at)
    if noise:
        sound("land", at)
    moment(at + 0.38, what or f"{sel} landed")


def show(sel, at, until=None):
    """visible from `at` (and hidden again at `until`)"""
    tl.append(f'tl.set("{sel}", {{opacity: 0}}, 0); tl.set("{sel}", {{opacity: 1}}, {at:.3f});')
    if until is not None:
        tl.append(f'tl.set("{sel}", {{opacity: 0}}, {until:.3f});')


def carry(pid, path, t0, t1, w, h, r0, r1, fps=10):
    """move a cut-out along a path in held steps, turning as it goes"""
    pts = catmull(path, 6)
    ln = [0.0]
    for i in range(1, len(pts)):
        ln.append(ln[-1] + math.dist(pts[i - 1], pts[i]))
    n = max(2, int((t1 - t0) * fps))
    j = 0
    for k in range(n + 1):
        want = ln[-1] * k / n
        while j < len(pts) - 2 and ln[j + 1] < want:
            j += 1
        ax, ay = pts[j]
        tl.append(f'tl.set("#{pid}-m", {{x: {ax - w / 2:.1f}, y: {ay - h / 2:.1f}, rotation: {r0 + (r1 - r0) * k / n:.1f}}}, {0 if k == 0 else t0 + (t1 - t0) * k / n:.3f});')


def bubble(sk, cx, cy, rx, ry, tx, ty, color=FG, w=7):
    """a drawn speech bubble with its tail ending at (tx, ty)"""
    base_ = math.atan2((ty - cy) / ry, (tx - cx) / rx)
    gap = 0.2
    n = 42
    arc = [(cx + rx * math.cos(base_ + gap + k / n * (6.283 - 2 * gap)), cy + ry * math.sin(base_ + gap + k / n * (6.283 - 2 * gap))) for k in range(n + 1)]
    sk.add(arc, w, color, 1.4)
    sk.add([arc[-1], (tx, ty)], w, color, 0.8)
    sk.add([(tx, ty), arc[0]], w, color, 0.8)
    return sk


def video(path_, at, n):
    """footage under the scenes (a file inside renders/project/). Its scene uses the "photo" ground"""
    return (f'<video id="proof" class="clip" src="{path_}" data-start="{at:.3f}" data-duration="{n / VFPS:.3f}" '
            f'data-track-index="1" muted playsinline style="position:absolute;left:0;top:0;width:1080px;height:1920px;z-index:4"></video>')


def no_sig(a_, b_):
    """hide the signature between two times (e.g. while footage with its own text is on screen)"""
    tl.append(f'tl.set("#sig", {{opacity: 0}}, {a_:.3f}); tl.set("#sig", {{opacity: 1}}, {b_:.3f});')


def _font_stack(name):
    return f"'{name}', 'Inter', system-ui, sans-serif"


def _css():
    h, b = ST["fonts"]["headline"], ST["fonts"]["body"]
    case = {"upper": "uppercase", "lower": "lowercase"}.get(h.get("case"), "none")
    ccase = {"upper": "uppercase", "lower": "lowercase"}.get(CAP.get("case"), "none")
    size = float(CAP.get("size", 54))
    grounds = "".join(f".scene.{g}{{background:{bg};--fg:{fg};--accent:{ac}}}" for g, (bg, fg, ac) in GROUND.items())
    box = CAP.get("box", "#FFFFFF")
    return f"""
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:{C['main']}}}
#root{{position:absolute;inset:0;width:1080px;height:1920px;overflow:hidden;background:{C['main']};--fg:{C['text_on_main']};--accent:{C['accent']}}}
.scene{{position:absolute;inset:0;z-index:5;overflow:hidden}}
{grounds}
.scene.vid{{background:none;--fg:{GROUND['photo'][1]};--accent:{C['accent']}}}
#sig{{position:absolute;top:236px;left:0;right:0;text-align:center;z-index:20;font-family:{_font_stack(b['family'])};font-weight:600;font-size:26px;letter-spacing:.14em;text-transform:uppercase}}
#grain{{position:absolute;inset:0;z-index:30;background-image:url('assets/grain.png');background-size:512px 512px;opacity:.08;mix-blend-mode:overlay;pointer-events:none}}
.draw{{position:absolute;left:0;top:0;width:1080px;height:1920px;overflow:visible;pointer-events:none}}
.t{{position:absolute}}
.big{{position:absolute;left:40px;right:40px;text-align:center;font-family:{_font_stack(h['family'])};font-weight:{h.get('weight', 800)};letter-spacing:{h.get('tracking', -0.03)}em;line-height:{h.get('line', 1.0)};text-transform:{case};z-index:7}}
.heavy{{position:absolute}}
.cap{{position:absolute;left:70px;right:70px;text-align:center;font-family:{_font_stack(b['family'])};font-weight:{b.get('weight', 600)};font-size:{size}px;line-height:1.18;text-transform:{ccase};z-index:24}}
.cap.sh{{text-shadow:0 2px 14px rgba(0,0,0,.65)}}
.cap.ol{{-webkit-text-stroke:{size * 0.11:.1f}px #000;paint-order:stroke fill}}
.cap .boxed{{background:{box};color:{CAP.get('box_text', '#111111')};padding:.1em .38em;border-radius:.22em;-webkit-box-decoration-break:clone;box-decoration-break:clone;line-height:1.5}}
.note{{position:absolute;left:60px;right:60px;text-align:center;font-family:{_font_stack(b['family'])};font-weight:{b.get('weight', 600)};font-size:56px;z-index:7}}
.label{{position:absolute;left:0;right:0;text-align:center;font-family:{_font_stack(b['family'])};font-weight:700;font-size:30px;letter-spacing:.18em;text-transform:uppercase;z-index:7}}
.sent{{position:absolute;left:100px;top:330px;width:880px;font-family:{_font_stack(b['family'])};font-weight:{b.get('weight', 600)};font-size:76px;line-height:1.2;z-index:6}}
.mk{{position:relative;display:inline-block}}
.under{{position:absolute;left:-2%;top:90%;width:104%;height:24px;overflow:visible}}
.flash{{position:absolute;inset:0;z-index:26;pointer-events:none}}
#root[data-b="0"] .v1,#root[data-b="0"] .v2,#root[data-b="1"] .v0,#root[data-b="1"] .v2,#root[data-b="2"] .v0,#root[data-b="2"] .v1{{display:none}}
"""


def _transitions():
    """each "move" line's scene comes in with the style's transition"""
    kind = ST.get("transition", "cut")
    if kind not in TRANSITIONS:
        print(f"note: transition {kind!r} isn't one of {', '.join(TRANSITIONS)}; using cut")
        kind = "cut"
    moves = {round(T[k], 3) for k, _, h in _R.lines if h == "move" and T[k] > 0}
    for i, (sid, s_, e, bg, _) in enumerate(scenes):
        if i == 0 or round(s_, 3) not in moves or kind == "cut":
            continue
        sel = f"#sc-{sid}"
        if kind == "slide":
            ft(sel, {"xPercent": 100}, {"xPercent": 0, "duration": 0.3, "ease": "power3.out"}, s_)
        elif kind == "zoom":
            ft(sel, {"scale": 1.16, "opacity": 0}, {"scale": 1, "opacity": 1, "duration": 0.22, "ease": "power2.out"}, s_)
        elif kind == "fade":
            ft(sel, {"opacity": 0}, {"opacity": 1, "duration": 0.28, "ease": "none"}, s_)
        elif kind == "wipe":
            ft(sel, {"clipPath": "inset(0% 0% 0% 100%)"}, {"clipPath": "inset(0% 0% 0% 0%)", "duration": 0.3, "ease": "power2.inOut"}, s_)
        elif kind == "flash":
            fid = f"fl{i}"
            overlays.append(f'<div class="flash" id="{fid}" style="background:{C["accent"]}"></div>')
            ft(f"#{fid}", {"opacity": 0.85}, {"opacity": 0, "duration": 0.18, "ease": "power1.out"}, s_)
            tl.append(f'tl.set("#{fid}", {{opacity: 0}}, 0);')
        MOVES.append(s_)


def _lint():
    """rules checked in code. Problems are printed, not fatal: the self-check looks at them"""
    warn = []
    for c in CAPS:
        if c["chars"] > 2 * CAP_MAX_CHARS + 4:
            warn.append(f"caption '{c['text']}' is long and may wrap to three lines: split it")
    for sid, s_, e, bg, _ in scenes:
        if e - s_ < 1.2:
            warn.append(f"scene '{sid}' is only {e - s_:.2f} s long")
        if bg not in GROUND:
            warn.append(f"scene '{sid}' has ground {bg!r}: use \"main\", \"alt\" or \"photo\"")
    hits = sum(1 for e in EVENTS if e["label"] == "hit")
    if hits > 1:
        warn.append(f"{hits} takeovers: keep the full-screen accent moment for the reel's one big turn")
    return warn


def finish(events=None, under="", sig_notes=(), cut_sounds="auto"):
    """write the reel. events: extra sound moments (sound() calls are already included). under: footage from video().
    sig_notes: (seconds, colour) changes to the signature. cut_sounds: "auto" puts a very light sound on plain cuts,
    or give a list of line keys, or () for none."""
    TOTAL = _R.total
    handle = (ST.get("signature") or "").strip()
    _transitions()
    if handle:
        for sid, s_, e, bg, _ in scenes:
            tl.append(f'tl.set("#sig", {{color: "{GROUND.get(bg, GROUND["main"])[1]}"}}, {s_:.3f});')
        for a_, b_ in TAKEOVERS:
            tl.append(f'tl.set("#sig", {{color: "{ON_ACCENT}"}}, {a_ + 0.12:.3f});')
        if sig_notes:
            tl.append(" ".join(f'tl.set("#sig", {{color: "{c}"}}, {t:.3f});' for t, c in sig_notes))
    if not pen.CLEAN[0]:
        for i in range(int(TOTAL * FPS) + 1):
            tl.append(f'tl.set("#root", {{attr: {{"data-b": {i % 3}}}}}, {i / FPS:.3f});')

    scene_html = "\n".join(
        f'<div class="scene clip {bg}" id="sc-{sid}" data-start="{s_}" data-duration="{round(e - s_, 3)}" data-track-index="{i + 2}" '
        f'data-layout-allow-overlap data-layout-allow-overflow>{b}</div>' for i, (sid, s_, e, bg, b) in enumerate(scenes))

    style = open(os.path.join(kitpaths.ASSETS, "fonts", "fonts.css")).read()
    uf = project("assets/userfonts/fonts.css")
    if os.path.exists(uf):
        style += open(uf).read()
    style += _css()
    sig = f'<div id="sig">{_esc(handle)}</div>' if handle else ""
    grain = '<div id="grain"></div>' if ST.get("texture") == "grain" else ""
    page = f"""<!doctype html>
<html><head><meta charset="utf-8"><style>{style}</style></head>
<body>
<div id="root" data-b="0" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="1080" data-height="1920">
{under}
{scene_html}
  {sig}
  {"".join(overlays)}
  {_caption_html()}{"".join(rootcaps)}
  {grain}
</div>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<script>
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(tl)}
tl.set({{}}, {{}}, {TOTAL});
window.__timelines = window.__timelines || {{}};
window.__timelines["main"] = tl;
</script>
</body></html>"""
    with open(project("index.html"), "w", encoding="utf-8") as f:
        f.write(page)

    move_keys = {k for k, _, h in _R.lines if h == "move"} if ST.get("transition", "cut") != "cut" else set()
    plain = [k for n, (k, _, h) in enumerate(_R.lines) if n and k not in move_keys]
    cuts = plain if cut_sounds == "auto" else list(cut_sounds)
    ev = (EVENTS + list(events or []) + [{"t": round(t - 0.06, 3), "label": "whoosh"} for t in MOVES]
          + [{"t": round(T[k] - 0.05, 3), "label": "cut"} for k in cuts])
    if ST.get("sound", "on") == "off":
        ev = []
    with open(os.path.join(_R.dir, "renders", "sound", "events.json"), "w") as f:
        json.dump(sorted(ev, key=lambda e: e["t"]), f, indent=0)

    timing = {"reel": _R.slug, "style": ST.get("name", ""), "total": TOTAL, "voice_length": round(_R.voice_len, 3), "tempo": _R.tempo,
              "cuts": {k: float(T[k]) for k, _, _ in _R.lines}, "how": {k: how for k, _, how in _R.lines},
              "moves": [round(t, 3) for t in MOVES],
              "line_starts": {k: round(S[first[k]], 3) for k, _, _ in _R.lines},
              "line_ends": {k: round(E[last[k]], 3) for k, _, _ in _R.lines},
              "scenes": [{"id": sid, "start": s_, "end": e, "ground": bg} for sid, s_, e, bg, _ in scenes],
              "captions": [{k: v for k, v in c.items() if k in ("id", "line", "text", "on", "off", "chars")} for c in CAPS],
              "moments": [{"t": t, "what": w} for t, w in MOMENTS]}
    with open(project("timing.json"), "w") as f:
        json.dump(timing, f, indent=1)

    words = len(raw)
    print(f"built {_R.slug} in the {ST.get('name', 'starter')} look: {TOTAL:.1f} s, {len(scenes)} scenes, {len(MOVES)} transitions, "
          f"{len(CAPS)} captions, {words / _R.voice_len:.2f} words a second, {len(page) // 1024} KB")
    for w in _lint():
        print("check:", w)
