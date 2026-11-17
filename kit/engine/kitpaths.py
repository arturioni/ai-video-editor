"""Where everything lives, the user's settings, and the tools every step shells out to.

Every engine module imports this instead of guessing paths. The kit runs from the user's
"AI Video Editor" folder (ROOT); the engine sits in ROOT/kit. All commands go through
`uv run --project kit kit/run.py <step>`, so this file always runs inside the kit's own
Python 3.12 (kit/.venv), never the system Python.
"""
import json, os, shutil, subprocess, sys

ENGINE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(ENGINE)
ROOT = os.path.dirname(KIT)
ASSETS = os.path.join(KIT, "assets")
WORK = os.path.join(ROOT, "work")
FINISHED = os.path.join(ROOT, "Finished Reels")
MY_PHOTOS = os.path.join(ROOT, "My Photos")
MY_FOOTAGE = os.path.join(ROOT, "My Footage")
MY_STYLE = os.path.join(ROOT, "My Style")              # the user's own look: style.json, style.md, voice.md, fonts/
MY_REFERENCES = os.path.join(ROOT, "My References")    # reels and screenshots the user likes the look of
STYLES = os.path.join(KIT, "styles")                    # neutral starter looks to begin from
TOOLS = os.path.join(KIT, "tools")              # Node and ffmpeg land here when the computer has none
SETTINGS = os.path.join(ROOT, "settings.json")

HYPERFRAMES = "hyperframes@0.9.19"              # pinned: a newer version could change how a reel renders
WIN = os.name == "nt"

DEFAULTS = {"voice": "am_michael", "own_voice_tempo": 1.08}
PACE = {"calm": 1.0, "normal": 1.1, "fast": 1.2}          # the generated voice's speed for each style pace


def settings():
    s = dict(DEFAULTS)
    if os.path.exists(SETTINGS):
        try:
            s.update(json.load(open(SETTINGS, encoding="utf-8")))
        except ValueError:
            print("warning: settings.json isn't valid JSON, so the defaults are used", file=sys.stderr)
    return s


def save_settings(**changes):
    s = settings()
    s.update(changes)
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
        f.write("\n")
    return s


def _merge(base, over):
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def style():
    """the look reels are made in: My Style/style.json over the "clean" starter (which fills anything missing).
    Returns (style, is_users_own)."""
    base = json.load(open(os.path.join(STYLES, "clean", "style.json"), encoding="utf-8"))
    path = os.path.join(MY_STYLE, "style.json")
    if not os.path.exists(path):
        return base, False
    try:
        return _merge(base, json.load(open(path, encoding="utf-8"))), True
    except ValueError as e:
        sys.exit(f"My Style/style.json isn't valid JSON ({e}). Fix it, or run: kit/run.py style show")


SOUND_SETS = ("soft", "paper")       # kit/assets/sounds/sounds.json: soft whooshes and clicks, or paper and pen


def sound_set(st=None):
    """which sound effects a look gets: its "sound" key ("soft", "paper" or "off"); "on" (older styles) follows the
    marks: hand-drawn marks get paper and pen, clean lines get soft whooshes and clicks. None means no effects."""
    st = style()[0] if st is None else st
    s = st.get("sound", "on")
    if s == "off":
        return None
    if s in SOUND_SETS:
        return s
    return "paper" if st.get("marks") == "hand" else "soft"


def voice_speed():
    s = settings()
    if "voice_speed" in s:
        return float(s["voice_speed"])
    return PACE.get(style()[0].get("pace", "normal"), 1.1)


def _tool_dirs():
    """kit/tools/node(/bin) and the static ffmpeg, when they were installed by setup"""
    out = []
    node = os.path.join(TOOLS, "node")
    if os.path.isdir(node):
        out.append(node if WIN else os.path.join(node, "bin"))
    ff = os.path.join(TOOLS, "ffmpeg")
    if os.path.isdir(ff):
        out.append(ff)
    return out


def env():
    """the environment every subprocess gets: kit tools first on PATH, and the kit's Python for the voice"""
    e = dict(os.environ)
    e["PATH"] = os.pathsep.join(_tool_dirs() + [e.get("PATH", "")])
    e["HYPERFRAMES_PYTHON"] = sys.executable
    e.setdefault("HYPERFRAMES_SKIP_SKILLS", "1")
    e.setdefault("HYPERFRAMES_NO_TELEMETRY", "1")
    return e


def which(name):
    return shutil.which(name, path=env()["PATH"])


def ffmpeg():
    return which("ffmpeg") or "ffmpeg"


def ffprobe():
    return which("ffprobe") or "ffprobe"


def npx():
    """the npx command as a list (npx.cmd on Windows)"""
    return [which("npx.cmd" if WIN else "npx") or "npx", "--yes"]


def hyperframes(*args):
    return npx() + [HYPERFRAMES, *args]


def run(cmd, **kw):
    """subprocess.run with the kit's environment; check=True unless told otherwise"""
    kw.setdefault("env", env())
    kw.setdefault("check", True)
    return subprocess.run([str(c) for c in cmd], **kw)


def duration(path):
    out = run([ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True).stdout
    return float(out.strip())


def reel_dir(name):
    """a reel's folder from its name (work/<name>) or a path"""
    d = os.path.abspath(name) if os.path.isdir(name) else os.path.join(WORK, name)
    if not os.path.isdir(d):
        sys.exit(f"There's no reel called {name!r} in work/. Folders there: {', '.join(sorted(os.listdir(WORK))) if os.path.isdir(WORK) else 'none'}")
    return d
