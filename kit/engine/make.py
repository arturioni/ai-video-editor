"""Start, build, render and deliver one reel. Each reel lives in work/<reel>/ and never touches another.

usage: run.py new <reel> ["one line on what it's about"]
       run.py build <reel>      scenes.py -> renders/project/ (the HyperFrames page), timing and sound moments
       run.py render <reel>     renders/<reel>-silent.mp4 (1 to 3 minutes)
       run.py finish <reel>     copies the finished reel to "Finished Reels/" (never overwrites: -v2, -v3...)
       run.py all <reel>        voice (if missing), build, render, sound, finish
       run.py count             how many files the kit itself has
"""
import datetime, filecmp, json, os, re, shutil, subprocess, sys
import kitpaths


def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:48] or "reel"


def new(argv):
    if not argv:
        sys.exit('usage: run.py new <reel-name> ["what it is about"]')
    slug = slugify(argv[0])
    about = argv[1] if len(argv) > 1 else ""
    d = os.path.join(kitpaths.WORK, slug)
    if os.path.exists(d):
        sys.exit(f"work/{slug} already exists, so nothing was changed. Pick another name, or keep working on that one.")
    for sub in ("assets/voice", "assets/f", "renders"):
        os.makedirs(os.path.join(d, sub))
    starter = os.path.join(kitpaths.KIT, "starter")
    fill = {"slug": slug, "about": about or "(one line on what this reel is about)", "date": datetime.date.today().isoformat()}
    for name in ("scenes.py", "STATUS.md"):
        text = open(os.path.join(starter, name), encoding="utf-8").read()
        for k, v in fill.items():
            text = text.replace("{" + k + "}", v)
        open(os.path.join(d, name), "w", encoding="utf-8").write(text)
    open(os.path.join(d, "script.txt"), "w").close()
    print(f"work/{slug}")


def build(d):
    env = kitpaths.env()
    env["PYTHONPATH"] = kitpaths.ENGINE + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONUNBUFFERED"] = "1"
    r = subprocess.run([sys.executable, "scenes.py"], cwd=d, env=env)
    if r.returncode:
        sys.exit("The build stopped (see the message above). Fix scenes.py, then build again.")


def render(d):
    slug = os.path.basename(d)
    proj = os.path.join(d, "renders", "project")
    if not os.path.exists(os.path.join(proj, "index.html")):
        sys.exit(f"Nothing to render yet. Run: kit/run.py build {slug}")
    out = os.path.join(d, "renders", f"{slug}-silent.mp4")
    print("Rendering every frame (1 to 3 minutes; it waits its turn if another render is running)...")
    r = kitpaths.run(kitpaths.hyperframes("render", "-o", out, "--quiet"), cwd=proj, capture_output=True, text=True, check=False)
    if r.returncode or not os.path.exists(out):
        print("\n".join(((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-25:]))
        sys.exit("The render failed (the renderer's last lines are above). Run: kit/run.py doctor")
    print(f"rendered {out}")
    return out


def finish(d):
    """copy the finished reel (with sound, else silent) to Finished Reels/, never overwriting a different file"""
    slug = os.path.basename(d)
    src = os.path.join(d, "renders", f"{slug}.mp4")
    if not os.path.exists(src):
        src = os.path.join(d, "renders", f"{slug}-silent.mp4")
    if not os.path.exists(src):
        sys.exit(f"No render yet. Run: kit/run.py render {slug}")
    os.makedirs(kitpaths.FINISHED, exist_ok=True)
    out, n = os.path.join(kitpaths.FINISHED, f"{slug}.mp4"), 1
    while os.path.exists(out) and not filecmp.cmp(src, out, shallow=False):
        n += 1
        out = os.path.join(kitpaths.FINISHED, f"{slug}-v{n}.mp4")
    shutil.copy2(src, out)
    credits = os.path.join(d, "credits.json")
    if os.path.exists(credits):
        import pictures
        data = pictures._read_credits(credits)
        if data:
            text = "Pictures\n" + "\n".join(f"{slot}: {pictures._line(data[slot])}" for slot in sorted(data))
            text += "\n\nSound effects: Freesound, CC0 (see kit/assets/sounds/CREDITS.md)\n"
            open(out[:-4] + " - credits.txt", "w", encoding="utf-8").write(text)
    print(f"finished: {out}")
    return out


SKIP_DIRS = {".venv", "tools", "__pycache__", ".git", "node_modules", ".hyperframes", "voice-samples-tmp"}


def count(argv=()):
    """the files that ship with the kit: no reels, renders, downloads or caches"""
    n, by = 0, {}
    user_dirs = ("work", "Finished Reels", "My Photos", "My Footage", "My Style", "My References")
    for top, dirs, files in os.walk(kitpaths.ROOT):
        rel = os.path.relpath(top, kitpaths.ROOT)
        user = rel.split(os.sep)[0] in user_dirs
        dirs[:] = [] if user else [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            if f in (".DS_Store", "uv.lock.tmp") or f.endswith(".pyc") or (user and f != "README.txt"):
                continue
            n += 1
            key = rel.split(os.sep)[0] if rel != "." else "(top)"
            by[key] = by.get(key, 0) + 1
    for k in sorted(by):
        print(f"{by[k]:4d}  {k}")
    print(f"{n} files in the kit")
    return n


def main(argv):
    step = argv[0]
    if step == "new":
        return new(argv[1:])
    if step == "count":
        return count(argv[1:])
    if len(argv) < 2:
        sys.exit(f"usage: run.py {step} <reel>")
    d = kitpaths.reel_dir(argv[1])
    if step == "build":
        return build(d)
    if step == "render":
        return render(d)
    if step == "finish":
        return finish(d)
    if step == "all":
        import voice, mix
        if not os.path.exists(os.path.join(d, "assets", "voice", "voice.words.json")):
            voice.main([d])
        build(d)
        render(d)
        mix.main([d])
        return finish(d)
    sys.exit(__doc__)
