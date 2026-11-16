"""The user's own look: My Style/style.json (what the engine reads), style.md and voice.md (what Claude reads).

usage: run.py style list                         the starter looks
       run.py style start <clean|bold|soft>      copy a starter into My Style/ to make it yours
       run.py style show                         the current look, with contrast checks
       run.py style set key=value ...            e.g. colors.accent=#FF3366 transition=zoom captions.style=box signature=@me
       run.py style font "<Google font>" [--for headline|body|both] [--weight 800]
       run.py style palette <picture or video>   the main colours of a reference, as hex codes
       run.py style preview                      three frames of a sample reel in the current look -> My Style/preview.jpg

Keys you can set: signature, colors.main, colors.alt, colors.text_on_main, colors.text_on_alt, colors.text_on_photo,
colors.accent, colors.accent_on_alt, colors.shade, fonts.headline.family/weight/case/tracking/line,
fonts.body.family/weight, headline_size, captions.size/y/style/box/box_text/case/max_words,
transition (cut slide zoom fade wipe flash), motion (snappy smooth), marks (hand clean), texture (none grain),
photos (color bw duotone), pace (calm normal fast), sound (on off).
"""
import json, os, re, shutil, subprocess, sys, urllib.request
import numpy as np
import kitpaths

STYLE_JSON = os.path.join(kitpaths.MY_STYLE, "style.json")
CHOICES = {"transition": ("cut", "slide", "zoom", "fade", "wipe", "flash"), "motion": ("snappy", "smooth"),
           "marks": ("hand", "clean"), "texture": ("none", "grain"), "photos": ("color", "bw", "duotone"),
           "pace": ("calm", "normal", "fast"), "sound": ("on", "off"), "captions.style": ("box", "shadow", "plain", "outline"),
           "captions.case": ("sentence", "upper", "lower"), "fonts.headline.case": ("none", "upper", "lower")}
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

STYLE_MD = """# My style

Claude keeps this page in step with style.json. It's the look in words, so every reel feels like yours.
Edit it any time, or just tell Claude what to change.

## In one line

(what the reels look and feel like)

## References

- (a reel, screenshot or account, and what to borrow from it: colours, type, captions, pace, transitions)

## Do

-

## Don't

-
"""

VOICE_MD = """# My voice

How the scripts should sound. Claude reads this before writing any reel.

## Who the reels are for

(one or two lines)

## How I talk

(e.g. friendly and direct, short sentences, a bit of humour)

## Words I use / words I avoid

-

## How I end reels

(e.g. "Follow for more", or "Comment GUIDE and I'll send it")
"""


def _load():
    if not os.path.exists(STYLE_JSON):
        sys.exit("There's no My Style yet. Start from a starter look: kit/run.py style start clean (or bold, soft)")
    return json.load(open(STYLE_JSON, encoding="utf-8"))


def _save(s):
    with open(STYLE_JSON, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _presets():
    out = {}
    for name in sorted(os.listdir(kitpaths.STYLES)):
        p = os.path.join(kitpaths.STYLES, name, "style.json")
        if os.path.exists(p):
            out[name] = json.load(open(p, encoding="utf-8"))
    return out


def list_(argv):
    for name, s in _presets().items():
        prev = os.path.join(kitpaths.STYLES, name, "preview.jpg")
        print(f"{name:6s}  {s.get('about', '')}" + (f"\n        preview: kit/styles/{name}/preview.jpg" if os.path.exists(prev) else ""))


def start(argv):
    if not argv:
        sys.exit("usage: run.py style start <clean|bold|soft>")
    name = argv[0].lower()
    presets = _presets()
    if name not in presets:
        sys.exit(f"No starter look called {name!r}. There are: {', '.join(presets)}")
    os.makedirs(kitpaths.MY_STYLE, exist_ok=True)
    if os.path.exists(STYLE_JSON):
        shutil.copy(STYLE_JSON, os.path.join(kitpaths.MY_STYLE, "style.previous.json"))
        print("Your old style.json is saved as My Style/style.previous.json")
    s = presets[name]
    s["based_on"] = name
    _save(s)
    for fname, text in (("style.md", STYLE_MD), ("voice.md", VOICE_MD)):
        p = os.path.join(kitpaths.MY_STYLE, fname)
        if not os.path.exists(p):
            open(p, "w", encoding="utf-8").write(text)
    os.makedirs(kitpaths.MY_REFERENCES, exist_ok=True)
    print(f"My Style now starts from {s['name']}. Change it with: kit/run.py style set ...  Preview it with: kit/run.py style preview")


def _lum(hex_):
    h = hex_.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def check(s):
    """problems that would make reels hard to read"""
    warn = []
    c = s.get("colors", {})
    for k, v in c.items():
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(v)):
            warn.append(f"colors.{k} should be a hex colour like #1A2B3C, not {v!r}")
    if warn:
        return warn
    pairs = [("text_on_main", "main", 4.5), ("text_on_alt", "alt", 4.5), ("accent", "main", 3.0),
             (c.get("accent_on_alt") and "accent_on_alt" or "accent", "alt", 3.0)]
    for fg, bg, need in pairs:
        if fg in c and bg in c:
            r = contrast(c[fg], c[bg])
            if r < need:
                warn.append(f"{fg} on {bg} is hard to read (contrast {r:.1f}, needs {need}+): make one lighter or darker")
    for key, allowed in CHOICES.items():
        v = s
        for part in key.split("."):
            v = v.get(part, {}) if isinstance(v, dict) else None
        if v not in ({}, None) and v not in allowed:
            warn.append(f"{key} is {v!r}; choose one of: {', '.join(allowed)}")
    return warn


def show(argv):
    s, own = kitpaths.style()
    if not own:
        print("No My Style yet: reels use the neutral Clean starter. Run: kit/run.py style start <clean|bold|soft>")
    c, h, b, cap = s["colors"], s["fonts"]["headline"], s["fonts"]["body"], s["captions"]
    print(f"{s.get('name', 'My style')} (based on {s.get('based_on', 'clean')})")
    print(f"  colours: main {c['main']}, alt {c['alt']}, text {c['text_on_main']} / {c['text_on_alt']}, accent {c['accent']}")
    print(f"  headline: {h['family']} {h.get('weight')} {h.get('case', 'none')} case, size {s.get('headline_size')}")
    print(f"  captions: {b['family']} {b.get('weight')}, {cap.get('size')} px at y={cap.get('y')}, {cap.get('style')}, {cap.get('case')} case")
    print(f"  transition {s.get('transition')}, motion {s.get('motion')}, marks {s.get('marks')}, texture {s.get('texture')}, "
          f"photos {s.get('photos')}, pace {s.get('pace')}, sound {s.get('sound')}, signature {s.get('signature') or '(none)'}")
    for w in check(s):
        print("check:", w)


def _value(v):
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d*\.\d+", v):
        return float(v)
    return v


def set_(argv):
    if not argv:
        sys.exit(__doc__)
    s = _load()
    for item in argv:
        if "=" not in item:
            sys.exit(f"{item!r} should look like key=value, e.g. colors.accent=#FF3366")
        key, v = item.split("=", 1)
        parts, node = key.split("."), s
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = _value(v)
        print(f"{key} = {v}")
    _save(s)
    for w in check(s):
        print("check:", w)


def _fonts_css():
    d = os.path.join(kitpaths.MY_STYLE, "fonts")
    rules = []
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        m = re.fullmatch(r"(.+)-(\d{3})(-italic)?\.woff2", f)
        if m:
            fam = m.group(1).replace("_", " ")
            rules.append(f"@font-face{{font-family:'{fam}';font-style:{'italic' if m.group(3) else 'normal'};font-weight:{m.group(2)};"
                         f"font-display:block;src:url('assets/userfonts/{f}') format('woff2');}}")
    open(os.path.join(d, "fonts.css"), "w").write("\n".join(rules) + "\n")


def font(argv):
    if not argv:
        sys.exit('usage: run.py style font "<Google font name>" [--for headline|body|both] [--weight 800]')
    family = argv[0]
    role = argv[argv.index("--for") + 1] if "--for" in argv else "both"
    weights = sorted({400, 500, 600, 700, 800, 900})
    want = int(argv[argv.index("--weight") + 1]) if "--weight" in argv else None
    url = f"https://fonts.googleapis.com/css2?family={family.replace(' ', '+')}:wght@{';'.join(map(str, weights))}&display=block"
    try:
        css = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": BROWSER_UA}), timeout=30).read().decode()
    except Exception:
        # some families don't have every weight: ask for the family's default
        try:
            css = urllib.request.urlopen(urllib.request.Request(f"https://fonts.googleapis.com/css2?family={family.replace(' ', '+')}&display=block",
                                                                headers={"User-Agent": BROWSER_UA}), timeout=30).read().decode()
        except Exception as e:
            sys.exit(f"Couldn't get {family!r} from Google Fonts ({e}). Check the spelling on fonts.google.com.")
    d = os.path.join(kitpaths.MY_STYLE, "fonts")
    os.makedirs(d, exist_ok=True)
    got = []
    for block in re.findall(r"/\*\s*latin\s*\*/\s*(@font-face\s*{[^}]+})", css):
        w = re.search(r"font-weight:\s*(\d+)", block).group(1)
        style_ = "-italic" if "italic" in re.search(r"font-style:\s*(\w+)", block).group(1) else ""
        src = re.search(r"url\((https://[^)]+\.woff2)\)", block)
        if not src:
            continue
        name = f"{family.replace(' ', '_')}-{w}{style_}.woff2"
        with urllib.request.urlopen(urllib.request.Request(src.group(1), headers={"User-Agent": BROWSER_UA}), timeout=60) as r, open(os.path.join(d, name), "wb") as f:
            f.write(r.read())
        got.append(int(w))
    if not got:
        sys.exit(f"Google Fonts sent no Latin files for {family!r}.")
    _fonts_css()
    s = _load()
    for r_ in (("headline", "body") if role == "both" else (role,)):
        s["fonts"][r_]["family"] = family
        if want:
            s["fonts"][r_]["weight"] = min(got, key=lambda x: abs(x - want))
        elif s["fonts"][r_].get("weight") not in got:
            s["fonts"][r_]["weight"] = min(got, key=lambda x: abs(x - s["fonts"][r_].get("weight", 600)))
    _save(s)
    print(f"{family}: weights {', '.join(map(str, sorted(set(got))))} saved in My Style/fonts/, used for {role}.")
    print("Fonts on Google Fonts are free to use (Open Font License or Apache).")


def palette(argv):
    if not argv:
        sys.exit("usage: run.py style palette <picture or video>")
    src = next((p for p in (argv[0], os.path.join(kitpaths.MY_REFERENCES, argv[0]), os.path.join(kitpaths.ROOT, argv[0])) if os.path.isfile(p)), None)
    if not src:
        sys.exit(f"Couldn't find {argv[0]!r}. Put it in My References/ and give its file name.")
    try:
        n = 1 if src.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".heic")) else 8
        dur = kitpaths.duration(src) if n > 1 else 0
    except Exception:
        n, dur = 1, 0
    px = []
    for k in range(n):
        t = dur * (k + 0.5) / n if n > 1 else 0
        seek = ["-ss", f"{t:.2f}"] if n > 1 else []          # seeking a still picture drops its only frame
        r = kitpaths.run([kitpaths.ffmpeg(), "-v", "error", *seek, "-i", src, "-frames:v", "1", "-vf", "scale=90:160",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=False)
        if r.stdout:
            px.append(np.frombuffer(r.stdout, dtype=np.uint8).reshape(-1, 3))
    if not px:
        sys.exit(f"{os.path.basename(src)} couldn't be read as a picture or video.")
    X = np.concatenate(px).astype("float32")
    rng = np.random.default_rng(1)
    cent = X[rng.choice(len(X), 6, replace=False)]
    for _ in range(20):
        lab = np.argmin(((X[:, None, :] - cent[None]) ** 2).sum(-1), axis=1)
        cent = np.array([X[lab == i].mean(0) if np.any(lab == i) else cent[i] for i in range(len(cent))])
    share = np.bincount(lab, minlength=len(cent)) / len(lab)
    print(f"Main colours in {os.path.basename(src)} (most used first):")
    for i in np.argsort(-share):
        r_, g, b = (int(v) for v in cent[i])
        print(f"  #{r_:02X}{g:02X}{b:02X}  {share[i]:5.0%}")


PREVIEW_SCENES = '''from beats import *
LINES = [("ready", "Your setup is ready.", "cut"), ("go", "Let's make a reel.", "move")]
begin(__file__, LINES)
TOTAL = total(at_least=3.4)
t0, t1 = T["ready"], T["go"]
s = label("YOUR STYLE", 560, t0 + 0.02)
s += stack("ready", [("SETUP", fit("SETUP", 160), 640, None, None), ("READY", fit("READY"), 820, "ready.", ACCENT)])
s += underline(300, 780, 1080, start_of("ready", "ready.") + 0.05)
caps("ready")
scene("ready", t0, t1, "main", s)
t0, t1 = T["go"], TOTAL
s = stack("go", [("LET'S GO", fit("LET'S GO"), 680, None, None)])
s += doodle("star", 540, 1060, 200, t0 + 0.05, color=ACCENT)
caps("go")
scene("go", t0, t1, "alt", s)
finish()
'''


def preview(argv):
    voice = os.path.join(kitpaths.WORK, "setup-test", "assets", "voice")
    if not os.path.exists(os.path.join(voice, "voice.words.json")):
        sys.exit("Run the setup first (it makes the voice the preview uses): kit/run.py setup")
    d = os.path.join(kitpaths.WORK, "_style-preview")
    os.makedirs(os.path.join(d, "assets"), exist_ok=True)
    shutil.copytree(voice, os.path.join(d, "assets", "voice"), dirs_exist_ok=True)
    open(os.path.join(d, "script.txt"), "w").write("Your setup is ready. Let's make a reel.\n")
    open(os.path.join(d, "scenes.py"), "w").write(PREVIEW_SCENES)
    import make
    make.build(d)
    proj = os.path.join(d, "renders", "project")
    tim = json.load(open(os.path.join(proj, "timing.json")))
    go = tim["cuts"]["go"]
    times = [min(go - 0.1, 1.15), go + 0.5, tim["total"] - 0.1]
    snap = os.path.join(d, "renders", "snap")
    kitpaths.run(kitpaths.hyperframes("snapshot", "--at", ",".join(f"{t:.2f}" for t in times), "--no-end", "-o", snap, "--keep"),
                 cwd=proj, capture_output=True)
    frames = [os.path.join(snap, f"at-{('%.3f' % t).rstrip('0').rstrip('.')}s.png") for t in times]
    frames = [f for f in frames if os.path.exists(f)]
    if not frames:
        sys.exit("The preview frames didn't come out. Run: kit/run.py doctor")
    out = os.path.join(kitpaths.MY_STYLE if os.path.isdir(kitpaths.MY_STYLE) else d, "preview.jpg")
    args = [kitpaths.ffmpeg(), "-v", "error", "-y"]
    for f in frames:
        args += ["-i", f]
    fc = "".join(f"[{i}:v]scale=360:640[v{i}];" for i in range(len(frames))) + "".join(f"[v{i}]" for i in range(len(frames))) + f"hstack={len(frames)}"
    kitpaths.run(args + ["-filter_complex", fc, "-q:v", "3", out])
    print(f"Preview: {out}")


def main(argv):
    steps = {"list": list_, "start": start, "show": show, "set": set_, "font": font, "palette": palette, "preview": preview}
    if not argv or argv[0] not in steps:
        sys.exit(__doc__)
    steps[argv[0]](argv[1:])
