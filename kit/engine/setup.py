"""Check what the AI Video Editor needs, and install what's missing.

usage: run.py doctor [--json]      look only, change nothing
       run.py setup [--skip-test]  install what's missing (safe to run again), then make a 3-second test reel

Everything lands inside this folder (kit/.venv, kit/tools) or in the usual download caches in your home
folder (~/.cache). Nothing needs a password, and no account or key is needed.
"""
import glob, json, os, platform, re, shutil, subprocess, sys, tarfile, tempfile, urllib.request, zipfile
import kitpaths

UA = {"User-Agent": "AI-Video-Editor-kit/1.0"}
WHISPER_MODEL = "base.en"


def _ver(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, env=kitpaths.env(), timeout=60)
        return (out.stdout or out.stderr).strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def check_node():
    node = kitpaths.which("node")
    if not node:
        return False, "not found"
    v = _ver([node, "--version"])
    m = re.match(r"v(\d+)", v)
    if not m or int(m.group(1)) < 22:
        return False, f"{v or 'unknown version'} is too old (needs 22 or newer)"
    return True, f"{v} at {node}"


def check_ffmpeg():
    ff, fp = kitpaths.which("ffmpeg"), kitpaths.which("ffprobe")
    if not ff or not fp:
        return False, "ffmpeg or ffprobe not found"
    v = _ver([ff, "-version"]).splitlines()
    return True, (v[0][:60] if v else "found")


def check_python():
    missing = []
    for mod in ("numpy", "kokoro_onnx", "soundfile", "faster_whisper"):
        try:
            __import__(mod)
        except Exception:
            missing.append(mod)
    if missing:
        return False, f"missing {', '.join(missing)}"
    return True, f"Python {platform.python_version()} in kit/.venv"


def check_chrome():
    if not check_node()[0]:
        return False, "needs Node first"
    try:
        out = subprocess.run(kitpaths.hyperframes("doctor", "--json"), capture_output=True, text=True, env=kitpaths.env(), timeout=300)
        d = json.loads(out.stdout)
    except Exception as e:
        return False, f"couldn't ask HyperFrames ({type(e).__name__})"
    c = {x["name"]: x for x in d.get("checks", [])}
    ch = c.get("Chrome", {})
    return bool(ch.get("ok")), ("ready" if ch.get("ok") else ch.get("hint") or ch.get("detail", "missing"))


def check_voice_model():
    import voice
    ok = os.path.exists(voice.MODEL) and os.path.exists(voice.VOICES)
    return ok, "downloaded" if ok else "not downloaded yet (about 340 MB)"


def _hf_cache():
    return os.environ.get("HF_HUB_CACHE") or os.path.join(os.environ.get("HF_HOME", os.path.join(os.path.expanduser("~"), ".cache", "huggingface")), "hub")


def check_whisper_model():
    hits = glob.glob(os.path.join(_hf_cache(), f"models--Systran--faster-whisper-{WHISPER_MODEL}", "snapshots", "*", "model.bin"))
    return bool(hits), "downloaded" if hits else "not downloaded yet (about 145 MB)"


def check_settings():
    s = kitpaths.settings()
    if not os.path.exists(kitpaths.SETTINGS):
        return False, "settings.json missing"
    st, own = kitpaths.style()
    return True, f"voice: {s['voice']}, look: {st.get('name', 'Clean') if own else 'starter Clean (say: set up my style)'}"


CHECKS = [("Python and its parts", check_python), ("Node.js (runs the video renderer)", check_node),
          ("ffmpeg (cuts and joins video and sound)", check_ffmpeg), ("Headless Chrome (draws each frame)", check_chrome),
          ("Voice model", check_voice_model), ("Word-timing model", check_whisper_model), ("Your settings", check_settings)]


def doctor(argv=()):
    results = []
    for name, fn in CHECKS:
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"check failed: {e}"
        results.append({"name": name, "ok": ok, "detail": detail})
    if "--json" in argv:
        print(json.dumps({"ok": all(r["ok"] for r in results), "checks": results}, indent=1))
    else:
        for r in results:
            print(f"{'✓' if r['ok'] else '✗'} {r['name']}: {r['detail']}")
        print("Ready." if all(r["ok"] for r in results) else "Not ready yet: run  uv run --project kit kit/run.py setup")
    return results


# ---------------------------------------------------------------- installers

def _get(url, dest):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def install_node():
    """the current long-term-support Node, unpacked into kit/tools/node (no installer, no password)"""
    sysname = {"Darwin": "darwin", "Windows": "win", "Linux": "linux"}[platform.system()]
    arch = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64", "AMD64": "x64"}.get(platform.machine(), "x64")
    with urllib.request.urlopen(urllib.request.Request("https://nodejs.org/dist/index.json", headers=UA), timeout=60) as r:
        releases = json.load(r)
    rel = next(x for x in releases if x.get("lts") and int(x["version"][1:].split(".")[0]) >= 22)
    v = rel["version"]
    ext = "zip" if sysname == "win" else "tar.gz"
    name = f"node-{v}-{sysname}-{arch}"
    url = f"https://nodejs.org/dist/{v}/{name}.{ext}"
    print(f"Downloading Node {v} ({sysname} {arch})...")
    tmp = tempfile.mkdtemp()
    arc = os.path.join(tmp, f"node.{ext}")
    _get(url, arc)
    if ext == "zip":
        with zipfile.ZipFile(arc) as z:
            z.extractall(tmp)
    else:
        with tarfile.open(arc) as t:
            t.extractall(tmp, filter="data")
    dest = os.path.join(kitpaths.TOOLS, "node")
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(kitpaths.TOOLS, exist_ok=True)
    shutil.move(os.path.join(tmp, name), dest)
    shutil.rmtree(tmp, ignore_errors=True)


def install_ffmpeg():
    """a ready-built ffmpeg and ffprobe for this computer, copied into kit/tools/ffmpeg"""
    print("Downloading ffmpeg...")
    from static_ffmpeg import run as sf
    ff, fp = sf.get_or_fetch_platform_executables_else_raise()
    dest = os.path.join(kitpaths.TOOLS, "ffmpeg")
    os.makedirs(dest, exist_ok=True)
    for src in (ff, fp):
        out = os.path.join(dest, os.path.basename(src))
        shutil.copy2(src, out)
        os.chmod(out, 0o755)


def install_chrome():
    print("Getting the headless Chrome the renderer draws with...")
    kitpaths.run(kitpaths.hyperframes("browser", "ensure"))


def install_voice_model():
    import voice
    voice.ensure_model()


def install_whisper_model():
    print(f"Downloading the word-timing model ({WHISPER_MODEL}, about 145 MB)...")
    from faster_whisper import WhisperModel
    WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")


def install_settings():
    kitpaths.save_settings()


FIXES = {"Node.js (runs the video renderer)": install_node, "ffmpeg (cuts and joins video and sound)": install_ffmpeg,
         "Headless Chrome (draws each frame)": install_chrome, "Voice model": install_voice_model,
         "Word-timing model": install_whisper_model, "Your settings": install_settings}


def test_reel():
    """a 3-second reel through the whole chain: voice, timing, build, render, sound"""
    import make
    slug = "setup-test"
    d = os.path.join(kitpaths.WORK, slug)
    if os.path.exists(d):
        shutil.rmtree(d)
    shutil.copytree(os.path.join(kitpaths.KIT, "starter", "setup-test"), d)
    import voice
    voice.main([slug])
    make.build(d)
    make.render(d)
    import mix
    mix.main([slug])
    out = make.finish(d)
    return out


def setup(argv=()):
    results = doctor()
    print()
    for r in results:
        if r["ok"]:
            continue
        fix = FIXES.get(r["name"])
        if r["name"] == "Python and its parts":
            sys.exit("The kit's Python parts are missing. Run this from the AI Video Editor folder: uv run --project kit kit/run.py setup")
        if fix:
            try:
                fix()
            except Exception as e:
                print(f"✗ Couldn't install {r['name']}: {e}")
    print()
    results = doctor()
    if not all(r["ok"] for r in results):
        sys.exit("Some parts still aren't ready (marked ✗ above).")
    if "--skip-test" not in argv:
        print("\nMaking a 3-second test reel to prove everything works together...")
        out = test_reel()
        print(f"\n✓ Test reel: {out}")
    print("\nReady. Type: make a reel about why airplane food tastes so bland")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    (setup if sys.argv[1:2] == ["setup"] else doctor)(sys.argv[2:])
