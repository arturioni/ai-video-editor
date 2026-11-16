"""The self-check: look at the reel before anyone else does.

usage: run.py check <reel>         lint the page, then snapshot every moment that matters, on labelled sheets
       run.py check <reel> --at 3.2,7.5   just those times (after a fix)
       run.py final <reel>         after rendering: a contact sheet of the MP4, plus length, sound and loudness

The frames land in work/<reel>/renders/check/. Open the sheets and look (see make-reel/references/checks.md).
"""
import json, os, re, shutil, subprocess, sys
import kitpaths

MAX_FRAMES = 48


def plan(timing):
    """the moments worth a look, each with what to look for. Kept in order of importance when there are too many:
    each scene's first and last frame, then marks and words arriving, then transitions, then captions, then middles"""
    pts = []
    moving = {round(t, 3): t + 0.32 for t in timing.get("moves", [])}      # a scene settles once its transition is done
    for sc in timing["scenes"]:
        start = sc["start"]
        settled = moving.get(round(start, 3), start) + 0.12
        pts.append((settled, f"{sc['id']}: first clean frame", 0))
        if sc["end"] - settled > 1.4:
            pts.append(((settled + sc["end"]) / 2, f"{sc['id']}: middle", 4))
        pts.append((sc["end"] - 0.08, f"{sc['id']}: last frame before the cut", 0))
    for t in timing.get("moves", []):
        pts.append((t + 0.12, "transition in progress", 2))
    for c in timing["captions"]:
        pts.append((c["on"] + 0.06, f"caption: {c['text']}", 3))
    for m in timing["moments"]:
        pts.append((m["t"], m["what"], 1))
    total = timing["total"]
    pts = sorted((round(min(max(t, 0.02), total - 0.04), 2), w, p) for t, w, p in pts)
    merged = []
    for t, w, p in pts:
        if merged and t - merged[-1][0] < 0.18:
            merged[-1] = (t, merged[-1][1] + " / " + w, min(p, merged[-1][2]))   # the later time, so everything merged has happened
        else:
            merged.append((t, w, p))
    for level in (4, 3, 2):
        if len(merged) <= MAX_FRAMES:
            break
        extra = len(merged) - MAX_FRAMES
        drop = [i for i, m in enumerate(merged) if m[2] == level][:extra] if level == 4 else \
               [i for i, m in enumerate(merged) if m[2] == level][::2][:extra]
        merged = [m for i, m in enumerate(merged) if i not in set(drop)]
    return [(t, w) for t, w, _ in merged[:MAX_FRAMES]]


def sheets(frames, out_dir, cols=4, per_sheet=12):
    """labelled contact sheets from (time, path) frames, half size so they're quick to read"""
    font = _font()
    made = []
    for s in range(0, len(frames), per_sheet):
        chunk = frames[s:s + per_sheet]
        args, fc = [kitpaths.ffmpeg(), "-v", "error", "-y"], []
        for i, (t, p) in enumerate(chunk):
            args += ["-i", p]
            label = f"drawtext=fontfile='{font}':text='{t:.2f}s':x=12:y=12:fontsize=34:fontcolor=white:box=1:boxcolor=black@0.7:boxborderw=8," if font else ""
            fc.append(f"[{i}:v]scale=360:640,{label}setsar=1[v{i}]")
        while len(chunk) % cols:
            chunk.append(None)
            i = len(chunk) - 1
            args += ["-f", "lavfi", "-i", "color=c=black:s=360x640:d=1"]
            fc.append(f"[{i}:v]setsar=1[v{i}]")
        rows = len(chunk) // cols
        layout = "|".join(f"{(k % cols) * 360}_{(k // cols) * 640}" for k in range(len(chunk)))
        fc.append("".join(f"[v{i}]" for i in range(len(chunk))) + f"xstack=inputs={len(chunk)}:layout={layout}[out]")
        out = os.path.join(out_dir, f"sheet-{s // per_sheet + 1}.jpg")
        kitpaths.run(args + ["-filter_complex", ";".join(fc), "-map", "[out]", "-frames:v", "1", "-q:v", "3", out])
        made.append(out)
    return made


def _font():
    for p in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc",
              "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(p):
            return p.replace(":", "\\:") if os.name == "nt" else p
    return None


def lint(proj):
    r = subprocess.run(kitpaths.hyperframes("lint", "--json"), cwd=proj, capture_output=True, text=True, env=kitpaths.env())
    try:
        d = json.loads(r.stdout)
    except ValueError:
        print("lint: no readable result", (r.stderr or "")[-300:])
        return
    found = d.get("findings") or d.get("issues") or []
    benign = ("timeline element that contains nested", "Initial hidden state", "composition file has")   # how every reel here is built; harmless
    errs = [f for f in found if str(f.get("severity", "")).lower() in ("error", "warning")
            and not any(b in str(f.get("message", "")) for b in benign)]
    print(f"lint: {len(errs)} errors or warnings" + ("" if errs else " (clean)"))
    for f in errs[:12]:
        print("  -", f.get("severity"), f.get("message") or f.get("code"))


def check(d, argv):
    slug = os.path.basename(d)
    proj = os.path.join(d, "renders", "project")
    tpath = os.path.join(proj, "timing.json")
    if not os.path.exists(tpath):
        sys.exit(f"Build first: kit/run.py build {slug}")
    timing = json.load(open(tpath))
    if "--at" in argv:
        pts = [(float(x), "requested") for x in argv[argv.index("--at") + 1].split(",")]
    else:
        lint(proj)
        pts = plan(timing)
    out = os.path.join(d, "renders", "check")
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    at = ",".join(f"{t:.2f}" for t, _ in pts)
    print(f"Snapshotting {len(pts)} moments...")
    kitpaths.run(kitpaths.hyperframes("snapshot", "--at", at, "--no-end", "-o", out, "--keep"), cwd=proj, capture_output=True)
    frames = []
    for t, w in pts:
        name = f"at-{('%.3f' % t).rstrip('0').rstrip('.')}s.png"
        p = os.path.join(out, name)
        if os.path.exists(p):
            frames.append((t, p))
    if not frames:
        sys.exit("No frames came back from the snapshot. Run the check again; if it repeats, run: kit/run.py doctor")
    made = sheets(frames, out)
    with open(os.path.join(out, "moments.txt"), "w") as f:
        for t, w in pts:
            f.write(f"{t:6.2f}s  {w}\n")
    print("Look at these sheets, in order:")
    for m in made:
        print(" ", m)
    print("What each time shows:")
    for t, w in pts:
        print(f"  {t:6.2f}s  {w}")


def final(d):
    slug = os.path.basename(d)
    src = os.path.join(d, "renders", f"{slug}.mp4")
    if not os.path.exists(src):
        src = os.path.join(d, "renders", f"{slug}-silent.mp4")
    if not os.path.exists(src):
        sys.exit(f"No render yet: kit/run.py render {slug}")
    out = os.path.join(d, "renders", "check")
    os.makedirs(out, exist_ok=True)
    length = kitpaths.duration(src)
    sheet = os.path.join(out, "final-sheet.jpg")
    cols = 6
    n = int(length) + 1
    rows = (n + cols - 1) // cols
    font = _font()
    label = f",drawtext=fontfile='{font}':text='%{{pts\\:hms}}':x=8:y=8:fontsize=26:fontcolor=white:box=1:boxcolor=black@0.7" if font else ""
    kitpaths.run([kitpaths.ffmpeg(), "-v", "error", "-y", "-i", src, "-vf", f"fps=1,scale=270:480{label},tile={cols}x{rows}", "-frames:v", "1", "-q:v", "3", sheet])
    probe = subprocess.run([kitpaths.ffprobe(), "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate", "-of", "json", src],
                           capture_output=True, text=True, env=kitpaths.env())
    streams = json.loads(probe.stdout).get("streams", [])
    vid = next((s for s in streams if s["codec_type"] == "video"), {})
    has_audio = any(s["codec_type"] == "audio" for s in streams)
    loud = ""
    if has_audio:
        e = subprocess.run([kitpaths.ffmpeg(), "-hide_banner", "-nostats", "-i", src, "-af", "ebur128=peak=true", "-f", "null", "-"],
                           capture_output=True, text=True, env=kitpaths.env()).stderr
        i_ = re.findall(r"I:\s+(-?[\d.]+) LUFS", e)
        tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)
        loud = f", loudness {i_[-1]} LUFS, peak {tp[-1]} dBTP" if i_ and tp else ""
    print(f"{os.path.basename(src)}: {length:.1f} s, {vid.get('width')}x{vid.get('height')}, "
          f"{'sound' if has_audio else 'NO SOUND'}{loud}")
    print(f"Contact sheet (one frame a second): {sheet}")


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    d = kitpaths.reel_dir(argv[1])
    return final(d) if argv[0] == "final" else check(d, argv[2:])
