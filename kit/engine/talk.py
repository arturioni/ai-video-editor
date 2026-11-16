"""Edit a raw talking-to-camera recording into a finished 9:16 reel.

Usage (from the kit root):  uv run --project kit kit/run.py talk <step> <video> [options]

  probe      <video>                           length, size, frame rate, rotation, sound - in plain words
  transcribe <video> [--model small.en|base.en]  every word with its time -> work/<name>/transcript.json + transcript.txt
  cut        <video> [--keep "a-b,c-d"]        keep only these ranges (seconds); no --keep reads work/<name>/keep.txt
  tighten    <video> [--max-gap 0.25]          shorten every pause longer than max-gap
  fit        <video> [--mode auto|crop|blur] [--x 0.5]   1080x1920, 30 fps
  captions   <video> [--words-per 3] [--y 1340] [--use captions.json]   burn word-timed captions (+ cards.txt)
  level      <video>                           sound to -14 LUFS, -1.5 dBTP
  sheet      <video> [--every 1] [--at T] [--safe]   pictures of the video for checking
  finish     <video> [--name NAME]             copy into Finished Reels/

Every step writes a new file into work/<name>/ (01-cut.mp4, 02-tight.mp4, 03-fit.mp4, 04-captions.mp4,
05-level.mp4) and never changes the original recording.
"""
import argparse, html, json, os, re, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kitpaths as kp

W, H, FPS = 1080, 1920, 30
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi")
X264 = ["-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p"]
AAC = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
FADE = 0.012                      # seconds of fade on each side of a join, so cuts don't click
RUN = "uv run --project kit kit/run.py talk"


# ---------------------------------------------------------------- small helpers

def _slug(name):
    return re.sub(r"[^a-z0-9_]+", "-", name.lower()).strip("-") or "video"


def _find(video):
    """the video the user means: a path, or a file name inside My Footage/"""
    for p in (video, os.path.join(kp.ROOT, video), os.path.join(kp.MY_FOOTAGE, video)):
        if os.path.isfile(p):
            return os.path.abspath(p)
    here = sorted(f for f in os.listdir(kp.MY_FOOTAGE) if f.lower().endswith(VIDEO_EXT)) if os.path.isdir(kp.MY_FOOTAGE) else []
    sys.exit(f"I can't find the video {video!r}. Put it in the My Footage folder and give its file name. "
             f"Videos there now: {', '.join(here) or 'none'}.")


def _work(video):
    """work/<name>/ for this video: the folder it already sits in, or one named after the file"""
    work = os.path.abspath(kp.WORK)
    d = os.path.dirname(os.path.abspath(video))
    if os.path.dirname(d) == work:
        return d
    d = os.path.join(work, _slug(os.path.splitext(os.path.basename(video))[0]))
    os.makedirs(d, exist_ok=True)
    return d


def _rel(path):
    """a path the user can paste back, relative to the kit root, quoted when it has spaces"""
    try:
        r = os.path.relpath(path, kp.ROOT)
    except ValueError:
        r = path
    r = path if r.startswith("..") else r.replace(os.sep, "/")
    return f'"{r}"' if " " in r else r


def _next(step, path, extra=""):
    print(f"Next:  {RUN} {step} {_rel(path)}{extra}")


def _ff(args, what, capture=False):
    """run ffmpeg quietly; on failure say what went wrong in plain words"""
    cmd = [kp.ffmpeg(), "-hide_banner", "-nostdin", "-y", "-v", "error"] + [str(a) for a in args]
    try:
        r = kp.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    except FileNotFoundError:
        sys.exit("ffmpeg isn't installed yet. Run the kit's setup step first, then try again.")
    if r.returncode != 0:
        tail = "\n".join((r.stderr or "").strip().splitlines()[-6:])
        sys.exit(f"Couldn't {what}. ffmpeg said:\n{tail}\nCheck that the video file plays normally, then try again.")
    return r if capture else None


def _graph(pre, graph, post, what):
    """run ffmpeg with a filter graph; a very long graph goes through a file (Windows has a command-length limit)"""
    if len(graph) < 20000:
        return _ff(pre + ["-filter_complex", graph] + post, what)
    path = os.path.join(os.path.dirname(post[-1]), "_graph.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(graph)
    try:
        for flag in ("-/filter_complex", "-filter_complex_script"):       # new and old spelling
            cmd = [kp.ffmpeg(), "-hide_banner", "-nostdin", "-y", "-v", "error"] + [str(a) for a in pre + [flag, path] + post]
            r = kp.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
            if r.returncode == 0:
                return
        sys.exit(f"Couldn't {what}. ffmpeg said:\n" + "\n".join((r.stderr or "").strip().splitlines()[-6:]))
    finally:
        if os.path.exists(path):
            os.remove(path)


def _info(video):
    """what ffprobe knows about the file, tidied: display size, fps, rotation, sound"""
    try:
        r = kp.run([kp.ffprobe(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", video],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    except FileNotFoundError:
        sys.exit("ffprobe isn't installed yet. Run the kit's setup step first, then try again.")
    if r.returncode != 0:
        sys.exit(f"I can't read {os.path.basename(video)} as a video. Is it a finished recording (mp4 or mov)?")
    data = json.loads(r.stdout)
    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video" and s.get("disposition", {}).get("attached_pic", 0) == 0), None)
    a = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not v:
        sys.exit(f"{os.path.basename(video)} has no picture in it, only sound. This step needs a video.")

    def rate(s):
        try:
            n, d = s.split("/")
            return float(n) / float(d) if float(d) else 0.0
        except (ValueError, AttributeError):
            return 0.0
    rot = 0
    for sd in v.get("side_data_list", []):
        if "rotation" in sd:
            rot = int(round(float(sd["rotation"])))
    if not rot and v.get("tags", {}).get("rotate"):
        rot = int(v["tags"]["rotate"])
    w, h = int(v["width"]), int(v["height"])
    if abs(rot) % 180 == 90:
        w, h = h, w
    fps = rate(v.get("avg_frame_rate")) or rate(v.get("r_frame_rate")) or 30.0
    dur = float(data.get("format", {}).get("duration") or v.get("duration") or 0)
    return {
        "duration": dur, "w": w, "h": h, "fps": fps, "rotation": rot,
        "vfr": abs(rate(v.get("r_frame_rate")) - fps) > 0.5,
        "vcodec": v.get("codec_name", "?"),
        "hdr": v.get("color_transfer") in ("arib-std-b67", "smpte2084"),
        "audio": None if not a else {"codec": a.get("codec_name", "?"), "channels": int(a.get("channels", 0)),
                                     "rate": int(a.get("sample_rate", 0) or 0)},
        "size_mb": float(data.get("format", {}).get("size", 0)) / 1e6,
    }


def _need_audio(info, video):
    if not info["audio"]:
        sys.exit(f"{os.path.basename(video)} has no sound, so there's nothing to listen to. Use the recording with your voice in it.")


_FILTERS = None


def _has_filter(name):
    global _FILTERS
    if _FILTERS is None:
        r = kp.run([kp.ffmpeg(), "-hide_banner", "-filters"], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        _FILTERS = {ln.split()[1] for ln in r.stdout.splitlines() if len(ln.split()) > 2}
    return name in _FILTERS


def _sdr(info):
    """filters that turn an HDR phone recording into normal colours; empty for ordinary video"""
    if not info["hdr"]:
        return "", []
    if _has_filter("zscale") and _has_filter("tonemap"):
        return ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
                "zscale=t=bt709:m=bt709:r=tv,format=yuv420p,setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709,"), ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
    print("Note: this recording is HDR and this ffmpeg can't convert it, so colours may look washed out. "
          "Record with HDR video switched off in the phone's camera settings to avoid it.")
    return "", []


def _std_fps(fps):
    """the nearest ordinary frame rate (phones record a wobbly 29.97-ish), as a number and as ffmpeg writes it"""
    table = [(24000 / 1001, "24000/1001"), (24.0, "24"), (25.0, "25"), (30000 / 1001, "30000/1001"), (30.0, "30"),
             (50.0, "50"), (60000 / 1001, "60000/1001"), (60.0, "60")]
    if fps >= 60:
        return table[-1]
    near = min(table, key=lambda r: abs(r[0] - fps))
    if abs(near[0] - fps) < 0.6:
        return near
    r = max(1, round(fps))
    return float(r), str(r)


def _mmss(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


# ---------------------------------------------------------------- probe

def probe(argv):
    ap = argparse.ArgumentParser(prog="talk probe")
    ap.add_argument("video")
    a = ap.parse_args(argv)
    video = _find(a.video)
    i = _info(video)
    shape = "upright (9:16)" if abs(i["w"] / i["h"] - 9 / 16) < 0.01 else "upright" if i["h"] > i["w"] else "square" if i["h"] == i["w"] else "sideways (landscape)"
    print(f"{os.path.basename(video)}")
    print(f"  Length      {_mmss(i['duration'])} ({i['duration']:.1f} seconds), {i['size_mb']:.0f} MB")
    print(f"  Picture     {i['w']} x {i['h']}, {shape}, {i['vcodec']}")
    print(f"  Frame rate  {i['fps']:.2f} frames a second" + (" (it varies, which is normal for phones; cut evens it out)" if i["vfr"] else ""))
    print(f"  Rotation    " + (f"stored turned {i['rotation']} degrees; the size above is how it plays" if i["rotation"] else "none"))
    if i["audio"]:
        au = i["audio"]
        print(f"  Sound       yes: {au['codec']}, {'stereo' if au['channels'] == 2 else 'mono' if au['channels'] == 1 else str(au['channels']) + ' channels'}, {au['rate']} Hz")
    else:
        print("  Sound       none. Transcribing, tightening and levelling need a recording with sound.")
    if i["hdr"]:
        print("  Colour      HDR. The cut step converts it to normal colours.")
    if abs(i["w"] / i["h"] - 9 / 16) >= 0.01:
        print(f"  Shape       not 9:16 yet. The fit step will {'put it on a blurred background' if i['w'] > i['h'] else 'crop it'}.")
    _next("transcribe", video)


# ---------------------------------------------------------------- transcribe

def _whisper(video, model_name):
    """word-level timestamps with faster-whisper; returns [{'w','s','e','p'}]"""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("The speech-to-text part isn't installed. Run the kit's setup step, then try again.")
    try:
        model = WhisperModel(model_name, device="cpu", compute_type="int8", local_files_only=True)
    except Exception:
        size = {"tiny.en": "75 MB", "base.en": "150 MB", "small.en": "480 MB", "medium.en": "1.5 GB"}.get(model_name, "a few hundred MB")
        print(f"Downloading the speech model '{model_name}' (about {size}). This happens once; after that it works offline.")
        try:
            model = WhisperModel(model_name, device="cpu", compute_type="int8")
        except Exception as e:
            sys.exit(f"Couldn't download the speech model '{model_name}' ({type(e).__name__}). Check the internet connection and try again.")
    print(f"Listening to {os.path.basename(video)} ...")
    try:                                                       # ffmpeg reads the sound, so any video ffmpeg can open works
        import numpy as np
        sound = np.concatenate([_pcm(video), np.zeros(8000, dtype=np.float32)])   # half a second of quiet helps the last word
        segments, _ = model.transcribe(sound, word_timestamps=True, condition_on_previous_text=False,
                                       beam_size=5, vad_filter=False, language="en" if model_name.endswith(".en") else None)
        words = []
        for seg in segments:
            for w in seg.words or []:
                t = w.word.strip()
                if t:
                    words.append({"w": t, "s": round(float(w.start), 3), "e": round(float(w.end), 3), "p": round(float(w.probability), 2)})
    except Exception as e:
        sys.exit(f"Couldn't read the sound in {os.path.basename(video)} ({type(e).__name__}: {e}). Check that the video plays with sound.")
    if not words:
        sys.exit("I didn't hear any words in this video. Check that it has speech and that the sound isn't muted.")
    return words


def _sentences(words):
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        gap = words[i + 1]["s"] - w["e"] if i + 1 < len(words) else 9
        if w["w"][-1] in ".?!" or gap > 0.8:
            out.append({"start": cur[0]["s"], "end": cur[-1]["e"], "text": " ".join(x["w"] for x in cur)})
            cur = []
    return out


def _key(text):
    return " ".join(re.sub(r"[^a-z0-9 ]", "", text.lower()).split()[:3])


def transcribe(argv):
    ap = argparse.ArgumentParser(prog="talk transcribe")
    ap.add_argument("video")
    ap.add_argument("--model", default="small.en", help="small.en (default) hears words well; base.en is quicker on a slow computer; medium.en is slowest and best with names")
    a = ap.parse_args(argv)
    video = _find(a.video)
    info = _info(video)
    _need_audio(info, video)
    work = _work(video)
    stem = os.path.splitext(os.path.basename(video))[0]
    base = "transcript" if os.path.dirname(video) != work else f"transcript-{stem}"
    words = _whisper(video, a.model)
    sents = _sentences(words)
    with open(os.path.join(work, base + ".json"), "w", encoding="utf-8") as f:
        json.dump({"video": os.path.basename(video), "duration": round(info["duration"], 3), "model": a.model,
                   "sentences": sents, "words": [{"word": w["w"], "start": w["s"], "end": w["e"], "confidence": w["p"]} for w in words]},
                  f, indent=1, ensure_ascii=False)
    lines = [f"# {os.path.basename(video)}  -  {info['duration']:.1f} s  -  times are seconds from the start",
             "# 'said again' marks a line that starts the same way later on: usually the earlier one is a retake to drop.", ""]
    for n, s in enumerate(sents):
        if n and s["start"] - sents[n - 1]["end"] >= 0.7:
            lines.append(f"                     ... pause {s['start'] - sents[n - 1]['end']:.1f} s ...")
        again = next((t for t in sents[n + 1:] if _key(t["text"]) == _key(s["text"]) and len(_key(s["text"]).split()) >= 2), None)
        lines.append(f"[{s['start']:7.2f} - {s['end']:7.2f}]  {s['text']}" + (f"    <- said again at {again['start']:.2f}" if again else ""))
    with open(os.path.join(work, base + ".txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Heard {len(words)} words in {len(sents)} lines.")
    print(f"Wrote {_rel(os.path.join(work, base + '.txt'))} (easy to read) and {_rel(os.path.join(work, base + '.json'))} (every word with its time).")
    print(f"Next:  read the transcript, write the ranges to keep into {_rel(os.path.join(work, 'keep.txt'))} (one START-END per line), then")
    print(f"       {RUN} cut {_rel(video)}")


# ---------------------------------------------------------------- cut / tighten (both join kept ranges)

def _join(video, info, segs, out, what):
    """re-encode only the kept ranges, joined; each range starts and ends on a whole frame"""
    fps, fps_s = _std_fps(info["fps"])
    snapped = []
    for s, e in segs:
        s, e = round(s * fps) / fps, round(e * fps) / fps
        if e - s >= 2 / fps:
            snapped.append((s, e))
    if not snapped:
        sys.exit("Nothing would be left after this cut. Check the ranges: each is START-END in seconds, like 3.2-7.9.")
    sdr, tags = _sdr(info)
    parts, labels = [], ""
    has_a = bool(info["audio"])
    for n, (s, e) in enumerate(snapped):
        d = e - s
        parts.append(f"[0:v]trim=start={s:.5f}:end={e:.5f},setpts=PTS-STARTPTS[v{n}]")
        labels += f"[v{n}]"
        if has_a:
            f = min(FADE, d / 4)
            parts.append(f"[0:a]atrim=start={s:.5f}:end={e:.5f},asetpts=PTS-STARTPTS,"
                         f"afade=t=in:d={f:.4f},afade=t=out:st={d - f:.5f}:d={f:.4f}[a{n}]")
            labels += f"[a{n}]"
    parts.append(f"{labels}concat=n={len(snapped)}:v=1:a={1 if has_a else 0}[vj]" + ("[aj]" if has_a else ""))
    parts.append(f"[vj]{sdr}fps={fps_s},format=yuv420p[vo]")
    post = ["-map", "[vo]"] + (["-map", "[aj]"] + AAC if has_a else []) + X264 + tags + ["-movflags", "+faststart", out]
    _graph(["-i", video], ";".join(parts), post, what)
    return snapped


def _parse_ranges(text):
    segs = []
    for raw in ",".join(ln.split("#")[0] for ln in text.splitlines()).split(","):
        item = raw.strip()
        if not item:
            continue
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:-|to|\s)\s*(\d+(?:\.\d+)?)", item)
        if not m:
            sys.exit(f"I can't read the range {item!r}. Write each one as START-END in seconds, like 3.2-7.9.")
        s, e = float(m.group(1)), float(m.group(2))
        if e <= s:
            sys.exit(f"The range {item!r} ends before it starts. Write START-END in seconds, like 3.2-7.9.")
        segs.append((s, e))
    return segs


def cut(argv):
    ap = argparse.ArgumentParser(prog="talk cut")
    ap.add_argument("video")
    ap.add_argument("--keep", help='ranges to keep in seconds, in the order they should play: "3.2-7.9,12-18.4". Without it, work/<name>/keep.txt is used')
    ap.add_argument("--pad", type=float, default=0.1, help="time added on each side of a range when no quiet moment is found nearby (default 0.1)")
    ap.add_argument("--exact", action="store_true", help="cut exactly at the times given, without moving each edge to the nearest quiet moment")
    ap.add_argument("-o", "--out")
    a = ap.parse_args(argv)
    video = _find(a.video)
    info = _info(video)
    work = _work(video)
    keep_file = os.path.join(work, "keep.txt")
    if a.keep and os.path.isfile(a.keep):
        keep_file, a.keep = a.keep, None
    if a.keep:
        segs = _parse_ranges(a.keep)
        with open(os.path.join(work, "keep.txt"), "w", encoding="utf-8") as f:
            f.write("".join(f"{s:g}-{e:g}\n" for s, e in segs))
    elif os.path.isfile(keep_file):
        segs = _parse_ranges(open(keep_file, encoding="utf-8").read())
    else:
        sys.exit(f"Tell me what to keep: add --keep \"3.2-7.9,12-18.4\" or write the ranges into {_rel(keep_file)}, one START-END per line.")
    if not segs:
        sys.exit(f"{_rel(keep_file)} has no ranges in it. Write one START-END per line, in seconds.")
    dur = info["duration"]
    quiet = None if a.exact or not info["audio"] else _quiet_map(video)
    padded = []
    for n, (s, e) in enumerate(segs):
        if s >= dur:
            sys.exit(f"The range {s:g}-{e:g} starts after the video ends ({dur:.1f} s).")
        s2, e2 = (s, e) if a.exact else _breathe(quiet, s, e, a.pad)
        s2, e2 = max(0.0, s2), min(dur, e2)
        if n and segs[n - 1][1] <= s:                       # don't let padding pull back in what the last range dropped
            s2 = max(s2, min(s, (segs[n - 1][1] + s) / 2))
        if n + 1 < len(segs) and e <= segs[n + 1][0]:
            e2 = min(e2, max(e, (e + segs[n + 1][0]) / 2))
        padded.append((s2, e2))
    if not a.exact:                                            # let the very last word ring out
        padded[-1] = (padded[-1][0], min(dur, padded[-1][1] + 0.2))
    out = a.out or os.path.join(work, "01-cut.mp4")
    print(f"Cutting {len(padded)} piece{'s' if len(padded) != 1 else ''} out of {os.path.basename(video)} ...")
    kept = _join(video, info, padded, out, "cut the video")
    total = sum(e - s for s, e in kept)
    print(f"Wrote {_rel(out)}: {total:.1f} s kept out of {dur:.1f} s ({len(kept)} piece{'s' if len(kept) != 1 else ''}, joined with tiny sound fades so the cuts don't click).")
    _next("tighten", out)


def _pcm(video, rate=16000):
    import numpy as np
    r = kp.run([kp.ffmpeg(), "-hide_banner", "-nostdin", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", str(rate), "-f", "s16le", "-"],
               capture_output=True, check=False)
    if r.returncode != 0 or not r.stdout:
        sys.exit(f"Couldn't read the sound in {os.path.basename(video)}. Check that the video plays with sound.")
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def _peaks(x, ms):
    """the loudest moment of each `ms`-long slice, in dB (peaks, because that's what ffmpeg's pause finder compares)"""
    import numpy as np
    n = 16 * ms
    if len(x) < n * 10:
        return np.full(1, -35.0, dtype=np.float32)
    return 20 * np.log10(np.abs(x[: len(x) // n * n].reshape(-1, n)).max(axis=1) + 1e-7)


def _auto_threshold(video, x=None):
    """a silence level between the room's hum and the voice, in dB"""
    import numpy as np
    db = _peaks(_pcm(video) if x is None else x, 20)
    if len(db) < 10:
        return -35.0
    floor, voice = float(np.percentile(db, 8)), float(np.percentile(db, 92))
    return float(min(-22.0, max(-55.0, floor + max(6.0, (voice - floor) * 0.3))))


def _quiet_map(video):
    """for every 10 ms of the video: is it quiet (no speech)?"""
    x = _pcm(video)
    return _peaks(x, 10) < _auto_threshold(video, x)


def _breathe(quiet, s, e, pad):
    """move a range's edges out to the nearest quiet moment, because speech-to-text often ends a word a little early"""
    if quiet is None or len(quiet) < 20:
        return s - pad, e + pad
    s2, e2 = s - pad, e + pad
    i0 = int(e * 100)
    for i in range(i0, min(i0 + 50, len(quiet) - 6)):          # up to half a second later
        if quiet[i: i + 6].all():
            e2 = (i + 8) / 100
            break
    j0 = int(s * 100)
    for j in range(j0, max(j0 - 40, 6), -1):                   # up to 0.4 s earlier
        if quiet[j - 6: j].all():
            s2 = (j - 5) / 100
            break
    return s2, e2


def tighten(argv):
    ap = argparse.ArgumentParser(prog="talk tighten")
    ap.add_argument("video")
    ap.add_argument("--max-gap", type=float, default=0.25, help="the longest pause left in, in seconds (default 0.25)")
    ap.add_argument("--threshold", default="auto", help="how quiet counts as a pause, in dB (default: worked out from the recording; -40 quiet room, -30 noisy)")
    ap.add_argument("-o", "--out")
    a = ap.parse_args(argv)
    video = _find(a.video)
    info = _info(video)
    _need_audio(info, video)
    work = _work(video)
    gap = max(0.08, a.max_gap)
    try:
        thr = _auto_threshold(video) if a.threshold == "auto" else float(a.threshold)
    except ValueError:
        sys.exit("--threshold is a number of dB like -35, or the word auto.")
    r = _ff(["-i", video, "-vn", "-af", f"silencedetect=noise={thr:.1f}dB:d={gap:.3f}", "-v", "info", "-f", "null", "-"], "listen for pauses", capture=True)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", r.stderr)]
    dur = info["duration"]
    silences = [(max(0.0, s), ends[n] if n < len(ends) else dur) for n, s in enumerate(starts)]
    out = a.out or os.path.join(work, "02-tight.mp4")
    after, before = gap * 0.4, gap * 0.6                       # breath left after a word, and before the next one
    segs, t = [], 0.0
    for s, e in silences:
        if s <= 0.05:                                          # silence before the first word
            t = max(0.0, e - 0.15)
            continue
        if e >= dur - 0.05:                                    # silence after the last word
            dur = min(dur, s + 0.3)
            continue
        if (e - before) - (s + after) > 0.02:
            segs.append((t, s + after))
            t = e - before
    segs.append((t, dur))
    removed = info["duration"] - sum(e - s for s, e in segs)
    if removed < 0.05:
        shutil.copyfile(video, out)
        print(f"No pauses longer than {gap:g} s found (pause level {thr:.0f} dB), so {_rel(out)} is a plain copy.")
        print("If there clearly are pauses, the room is noisy: try --threshold -30. If words got cut before, try --threshold -45.")
    else:
        print(f"Shortening {len(segs) - 1 if len(segs) > 1 else 1} pause{'s' if len(segs) != 2 else ''} (pause level {thr:.0f} dB) ...")
        _join(video, info, segs, out, "shorten the pauses")
        print(f"Wrote {_rel(out)}: {kp.duration(out):.1f} s, {removed:.1f} s of pauses removed. Pauses are now at most {gap:g} s.")
    _next("fit", out)


# ---------------------------------------------------------------- fit

def fit(argv):
    ap = argparse.ArgumentParser(prog="talk fit")
    ap.add_argument("video")
    ap.add_argument("--mode", choices=["auto", "crop", "blur"], default="auto", help="crop fills the frame; blur shows the whole picture on a blurred copy (auto: blur for sideways video, crop otherwise)")
    ap.add_argument("--x", type=float, default=0.5, help="for crop: where the person is, 0 = far left, 0.5 = centre, 1 = far right")
    ap.add_argument("-o", "--out")
    a = ap.parse_args(argv)
    video = _find(a.video)
    info = _info(video)
    work = _work(video)
    out = a.out or os.path.join(work, "03-fit.mp4")
    x = min(1.0, max(0.0, a.x))
    mode = a.mode if a.mode != "auto" else ("blur" if info["w"] > info["h"] else "crop")
    already = info["w"] == W and info["h"] == H and abs(info["fps"] - FPS) < 0.01 and not info["hdr"] and info["vcodec"] == "h264"
    if already and a.mode == "auto":
        shutil.copyfile(video, out)
        print(f"Already {W}x{H} at {FPS} frames a second, so {_rel(out)} is a plain copy.")
        _next("captions", out)
        return
    sdr, tags = _sdr(info)
    if mode == "crop":
        graph = (f"[0:v]{sdr}scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
                 f"crop={W}:{H}:(iw-{W})*{x:.4f}:(ih-{H})/2,setsar=1,fps={FPS},format=yuv420p[vo]")
        said = f"cropped to fill the frame (person at x = {x:g})"
    else:
        graph = (f"[0:v]{sdr}split[b0][f0];"
                 f"[b0]scale={W // 4}:{H // 4}:force_original_aspect_ratio=increase,crop={W // 4}:{H // 4},gblur=sigma=10,"
                 f"scale={W}:{H}:flags=bicubic,eq=brightness=-0.10:saturation=0.9[bg];"
                 f"[f0]scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,scale=trunc(iw/2)*2:trunc(ih/2)*2[fg];"
                 f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,fps={FPS},format=yuv420p[vo]")
        said = "whole picture kept, on a blurred copy of itself"
    audio = []
    if info["audio"]:
        audio = ["-map", "0:a:0"] + (["-c:a", "copy"] if info["audio"]["codec"] == "aac" else AAC)
    print(f"Fitting {info['w']}x{info['h']} into {W}x{H} ...")
    _graph(["-i", video], graph, ["-map", "[vo]"] + audio + X264 + tags + ["-movflags", "+faststart", out], "fit the video to 9:16")
    print(f"Wrote {_rel(out)}: {W}x{H}, {FPS} frames a second, {said}.")
    if mode == "blur":
        print(f"To fill the frame instead:  {RUN} fit {_rel(video)} --mode crop --x 0.5   (move --x toward 0 or 1 to follow the person)")
    _next("captions", out)


# ---------------------------------------------------------------- captions (+ cards)

def _group(words, per):
    """short clauses: up to `per` words, breaking early at punctuation or a pause"""
    caps, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        last = i + 1 == len(words)
        gap = 9 if last else words[i + 1]["s"] - w["e"]
        clause_end = w["w"][-1] in ".?!,;:" or gap > 0.5
        nxt_ends = (not last) and (words[i + 1]["w"][-1] in ".?!,;:" or i + 2 == len(words) or words[i + 2]["s"] - words[i + 1]["e"] > 0.5)
        if clause_end or (len(cur) >= per and not (nxt_ends and len(cur) == per and not clause_end)):
            caps.append({"start": cur[0]["s"], "end": cur[-1]["e"], "text": " ".join(x["w"] for x in cur)})
            cur = []
    if cur:
        caps.append({"start": cur[0]["s"], "end": cur[-1]["e"], "text": " ".join(x["w"] for x in cur)})
    for n, c in enumerate(caps):                               # hold each one a moment, but never over the next
        nxt = caps[n + 1]["start"] if n + 1 < len(caps) else c["end"] + 0.4
        c["end"] = round(min(max(c["end"] + 0.25, c["start"] + 0.35), nxt), 3)
        c["start"] = round(c["start"], 3)
    return caps


def _read_cards(path, dur):
    """cards.txt: one card per line,  START-END | words | top / middle / bottom or a y number | size in px (optional)"""
    cards = []
    for raw in open(path, encoding="utf-8").read().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            sys.exit(f"I can't read this line in cards.txt: {line!r}. Write it as  0-2.2 | The words | top")
        (s, e), = _parse_ranges(parts[0])
        where = parts[2].lower() if len(parts) > 2 and parts[2] else "top"
        y = {"top": 0.20, "middle": 0.45, "bottom": 0.62}.get(where)
        if y is None:
            try:
                y = float(where) / H
            except ValueError:
                sys.exit(f"In cards.txt the place must be top, middle, bottom or a number of pixels from the top, not {where!r}.")
        try:
            size = float(parts[3]) if len(parts) > 3 and parts[3] else (84.0 if not cards else 68.0)
        except ValueError:
            sys.exit(f"In cards.txt the size must be a number of pixels like 72, not {parts[3]!r}.")
        if s < dur:
            cards.append({"start": s, "end": min(e, dur), "text": parts[1], "y": y, "size": size})
    if len(cards) > 3:
        print(f"Note: cards.txt has {len(cards)} cards. Two or three is plenty for a short reel; more starts to look like a template.")
    return cards


PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><style>
@font-face{font-family:'KitInter';font-style:normal;font-weight:100 900;font-display:block;src:url('assets/fonts/inter-latin.woff2') format('woff2');}
html,body{margin:0;background:transparent;}
#root{position:relative;width:%(w)dpx;height:%(h)dpx;overflow:hidden;background:transparent;}
.t{position:absolute;left:%(left)dpx;width:%(width)dpx;transform:translateY(-50%%);text-align:center;text-wrap:balance;
  font-family:'KitInter',system-ui,sans-serif;color:#fff;letter-spacing:-0.005em;}
.cap{font-weight:500;line-height:1.25;text-shadow:0 %(s2)dpx %(s14)dpx rgba(0,0,0,.55),0 1px %(s3)dpx rgba(0,0,0,.65);}
.card{font-weight:600;line-height:1.12;letter-spacing:-0.02em;text-shadow:0 %(s3)dpx %(s24)dpx rgba(0,0,0,.6),0 1px %(s3)dpx rgba(0,0,0,.6);}
</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="%(n)d" data-width="%(w)d" data-height="%(h)d" data-fps="1" data-no-timeline>
%(clips)s
</div></body></html>
"""


def _render_text(build, items, w, h, width):
    """one transparent PNG per caption or card, drawn by HyperFrames (a real browser, so the kit font and wrapping are exact)"""
    if os.path.isdir(build):
        shutil.rmtree(build)
    os.makedirs(os.path.join(build, "assets", "fonts"))
    font = os.path.join(kp.ASSETS, "fonts", "inter-latin.woff2")
    if not os.path.isfile(font):
        sys.exit("The kit's caption font is missing (kit/assets/fonts/inter-latin.woff2). Download the kit again or put the file back.")
    shutil.copyfile(font, os.path.join(build, "assets", "fonts", "inter-latin.woff2"))
    k = h / H
    clips = "\n".join(
        f'  <div id="t{n}" class="clip t {it["kind"]}" data-start="{n + 1}" data-duration="1" data-track-index="1" '
        f'style="top:{it["y"] * h:.0f}px;font-size:{it["size"] * k:.1f}px">{html.escape(it["text"])}</div>'
        for n, it in enumerate(items))
    page = PAGE % {"w": w, "h": h, "left": (w - width) // 2, "width": width, "n": len(items) + 1, "clips": clips,
                   "s2": max(1, round(2 * k)), "s3": max(1, round(3 * k)), "s14": round(14 * k), "s24": round(24 * k)}
    # the user's own look (My Style): their body font and caption case, when they've set one up
    st, own = kp.style()
    fam = st["fonts"]["body"].get("family", "Inter")
    user_fonts = os.path.join(kp.MY_STYLE, "fonts")
    extra = ""
    if own and fam != "Inter" and os.path.isfile(os.path.join(user_fonts, "fonts.css")):
        shutil.copytree(user_fonts, os.path.join(build, "assets", "userfonts"), dirs_exist_ok=True)
        extra += open(os.path.join(user_fonts, "fonts.css"), encoding="utf-8").read()
        page = page.replace("font-family:'KitInter',system-ui", f"font-family:'{fam}','KitInter',system-ui")
    if own and st["captions"].get("case") == "upper":
        extra += ".cap{text-transform:uppercase}"
    page = page.replace("</style>", extra + "</style>", 1)
    with open(os.path.join(build, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    frames = os.path.join(build, "frames")
    try:
        r = kp.run(kp.hyperframes("render", build, "--format", "png-sequence", "--fps", "1", "--output", frames),
                   capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, cwd=build)
    except FileNotFoundError:
        sys.exit("Captions are drawn with HyperFrames, which needs Node.js. Run the kit's setup step, then try again.")
    pngs = sorted(f for f in os.listdir(frames) if f.endswith(".png")) if os.path.isdir(frames) else []
    if r.returncode != 0 or len(pngs) < len(items) + 1:
        tail = "\n".join(((r.stderr or "") + (r.stdout or "")).strip().splitlines()[-8:])
        sys.exit(f"Couldn't draw the captions. HyperFrames said:\n{tail}\n"
                 "The first run downloads a browser, so check the internet connection, then try again.")
    return [os.path.join(frames, p) for p in pngs]             # [0] is empty, [n + 1] is items[n]


def captions(argv):
    ap = argparse.ArgumentParser(prog="talk captions")
    ap.add_argument("video")
    ap.add_argument("--words-per", type=int, default=3, help="most words on screen at once (default 3)")
    ap.add_argument("--y", type=float, default=1340, help="middle of the caption, pixels from the top of a 1920-tall frame (default 1340: lower third, above Instagram's buttons)")
    ap.add_argument("--size", type=float, default=44, help="letter size in pixels at 1080x1920 (default 44)")
    ap.add_argument("--width", type=float, default=800, help="widest a caption may be, in pixels at 1080 wide (default 800)")
    ap.add_argument("--model", default="small.en", help="speech model, as in transcribe")
    ap.add_argument("--use", help="burn this captions.json as it is (after fixing a word in it) instead of listening again")
    ap.add_argument("--cards", help="a cards.txt to burn as well (default: work/<name>/cards.txt when it exists)")
    ap.add_argument("--no-cards", action="store_true")
    ap.add_argument("-o", "--out")
    a = ap.parse_args(argv)
    video = _find(a.video)
    info = _info(video)
    work = _work(video)
    dur, w, h = info["duration"], info["w"], info["h"]
    out = a.out or os.path.join(work, "04-captions.mp4")
    cap_file = os.path.join(work, "captions.json")
    if a.use:
        src = a.use if os.path.isfile(a.use) else os.path.join(work, a.use)
        if not os.path.isfile(src):
            sys.exit(f"I can't find {a.use}. The captions file is usually {_rel(cap_file)}.")
        try:
            caps = json.load(open(src, encoding="utf-8"))
            caps = [{"start": float(c["start"]), "end": float(c["end"]), "text": str(c["text"]).strip()} for c in caps if str(c["text"]).strip()]
        except (ValueError, KeyError, TypeError):
            sys.exit(f"{_rel(src)} isn't a list of captions any more. Each one looks like {{\"start\": 1.2, \"end\": 2.0, \"text\": \"Words here\"}}.")
    else:
        _need_audio(info, video)
        caps = _group(_whisper(video, a.model), max(1, a.words_per))
        with open(cap_file, "w", encoding="utf-8") as f:
            json.dump(caps, f, indent=1, ensure_ascii=False)
    caps = sorted((c for c in caps if c["start"] < dur), key=lambda c: c["start"])
    for n, c in enumerate(caps):
        c["end"] = min(c["end"], dur, caps[n + 1]["start"] if n + 1 < len(caps) else dur)
    cards_file = a.cards or os.path.join(work, "cards.txt")
    if a.cards and not os.path.isfile(a.cards):
        sys.exit(f"I can't find the cards file {a.cards}.")
    cards = _read_cards(cards_file, dur) if os.path.isfile(cards_file) and not a.no_cards else []
    if not caps and not cards:
        sys.exit("There are no captions or cards to add.")
    if abs(w / h - 9 / 16) > 0.01:
        print(f"Note: this video is {w}x{h}, not 9:16. Captions are placed for an upright reel, so run the fit step first.")

    items = [{"kind": "cap", "text": c["text"], "y": a.y / H, "size": a.size} for c in caps] + \
            [{"kind": "card", "text": c["text"], "y": c["y"], "size": c["size"]} for c in cards]
    print(f"Drawing {len(caps)} captions" + (f" and {len(cards)} card{'s' if len(cards) != 1 else ''}" if cards else "") + " ...")
    build = os.path.join(work, "captions-build")
    pngs = _render_text(build, items, w, h, round(a.width * w / W))

    fps, fps_s = _std_fps(info["fps"])
    q = lambda t: round(t * fps) / fps                        # captions change on whole frames
    lines, t = ["ffconcat version 1.0"], 0.0
    def add(png, d):
        lines.append(f"file 'frames/{os.path.basename(png)}'")
        lines.append(f"duration {d:.5f}")
    for n, c in enumerate(caps):
        s, e = q(c["start"]), q(c["end"])
        if e - s < 1 / fps:
            continue
        if s > t + 1e-6:
            add(pngs[0], s - t)
        add(pngs[n + 1], e - s)
        t = e
    add(pngs[0], max(dur - t, 1 / fps) + 1.0)
    lines.append(f"file 'frames/{os.path.basename(pngs[0])}'")
    with open(os.path.join(build, "captions.ffconcat"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    pre = ["-i", video, "-f", "concat", "-safe", "0", "-i", os.path.join(build, "captions.ffconcat")]
    parts = [f"[1:v]fps={fps_s},format=rgba[cap]", "[0:v][cap]overlay=0:0:eof_action=pass:format=auto[v0]"]
    cur = "v0"
    for n, c in enumerate(cards):
        d = max(c["end"] - c["start"], 0.9)
        pre += ["-loop", "1", "-framerate", fps_s, "-t", f"{d:.3f}", "-i", pngs[len(caps) + n + 1]]
        parts.append(f"[{n + 2}:v]format=rgba,fade=t=in:st=0:d=0.4:alpha=1,fade=t=out:st={d - 0.35:.3f}:d=0.35:alpha=1,"
                     f"setpts=PTS+{c['start']:.3f}/TB[k{n}]")
        parts.append(f"[{cur}][k{n}]overlay=0:0:eof_action=pass:format=auto:enable='between(t,{c['start']:.3f},{c['start'] + d:.3f})'[c{n}]")
        cur = f"c{n}"
    parts.append(f"[{cur}]format=yuv420p[vo]")
    audio = (["-map", "0:a:0"] + (["-c:a", "copy"] if info["audio"]["codec"] == "aac" else AAC)) if info["audio"] else []
    _graph(pre, ";".join(parts), ["-map", "[vo]"] + audio + X264 + ["-t", f"{dur:.3f}", "-movflags", "+faststart", out], "burn the captions in")
    print(f"Wrote {_rel(out)} with {len(caps)} captions" + (f" and {len(cards)} card{'s' if len(cards) != 1 else ''}" if cards else "")
          + f" (Inter Medium, {a.size:g} px, white with a soft shadow, middle at y = {a.y:g}).")
    print(f"The words are in {_rel(cap_file)}. To fix a misheard word, edit it there, then:")
    print(f"       {RUN} captions {_rel(video)} --use captions.json")
    _next("level", out)


# ---------------------------------------------------------------- level

def _loud(video, chain=None):
    """integrated loudness (LUFS) and true peak (dBTP) of a file, optionally after a filter chain"""
    af = (chain + "," if chain else "") + "ebur128=peak=true"
    r = _ff(["-i", video, "-vn", "-af", af, "-v", "info", "-f", "null", "-"], "measure the loudness", capture=True)
    tail = r.stderr[r.stderr.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", tail)
    p = re.search(r"Peak:\s+(-?[\d.]+) dBFS", tail)
    return (float(i.group(1)) if i else -70.0), (float(p.group(1)) if p else 0.0)


def level(argv):
    ap = argparse.ArgumentParser(prog="talk level")
    ap.add_argument("video")
    ap.add_argument("--lufs", type=float, default=-14.0, help="how loud, in LUFS (default -14, what Instagram plays at)")
    ap.add_argument("--peak", type=float, default=-1.5, help="highest peak allowed, in dBTP (default -1.5)")
    ap.add_argument("-o", "--out")
    a = ap.parse_args(argv)
    video = _find(a.video)
    info = _info(video)
    _need_audio(info, video)
    work = _work(video)
    out = a.out or os.path.join(work, "05-level.mp4")
    # phone sound: cut the rumble, even out loud and quiet words a little, then gain + a limiter to land on the target
    clean = "highpass=f=80,acompressor=threshold=-20dB:ratio=2.5:attack=15:release=200:knee=4:makeup=1.5"
    print("Measuring the sound ...")
    before, _ = _loud(video)
    if before < -60:
        sys.exit("This video is all but silent, so there's nothing to level. Check the recording has sound.")
    start, _ = _loud(video, clean)
    gain, ceil = a.lufs - start, a.peak - 0.5

    def chain():
        return f"{clean},volume={gain:.2f}dB,alimiter=limit={10 ** (ceil / 20):.4f}:attack=3:release=80:level=false,aresample=48000"

    for _ in range(4):                                         # the limiter takes a little loudness back, so home in
        lufs, peak = _loud(video, chain())
        if abs(lufs - a.lufs) <= 0.15:
            break
        gain += a.lufs - lufs
    for attempt in range(3):                                   # then encode, and check what actually landed in the file
        _ff(["-i", video, "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy", "-af", chain()] + AAC + ["-movflags", "+faststart", out], "level the sound")
        lufs, peak = _loud(out)
        if peak <= a.peak + 0.05 and abs(lufs - a.lufs) <= 0.4:
            break
        if peak > a.peak + 0.05:
            ceil -= peak - a.peak + 0.1
        gain += a.lufs - lufs
    print(f"Wrote {_rel(out)}: loudness {lufs:.1f} LUFS (aim {a.lufs:g}; it was {before:.1f}), highest peak {peak:.1f} dBTP (limit {a.peak:g}). "
          "Low rumble removed and loud and quiet words evened out a little; the picture wasn't touched.")
    _next("sheet", out)


# ---------------------------------------------------------------- sheet

GLYPHS = {"0": "111101101101111", "1": "010110010010111", "2": "111001111100111", "3": "111001111001111", "4": "101101111001001",
          "5": "111100111001111", "6": "111100111101111", "7": "111001010010010", "8": "111101111101111", "9": "111101111001111",
          ":": "000010000010000", ".": "000000000000010", " ": "000000000000000"}


def _label(canvas, text, x, y, scale=4):
    """draw a time like 0:07 with a tiny built-in digit font (no font file needed, same on every computer)"""
    for ch in text:
        g = GLYPHS.get(ch, GLYPHS[" "])
        for r in range(5):
            for c in range(3):
                if g[r * 3 + c] == "1":
                    canvas[y + r * scale: y + (r + 1) * scale, x + c * scale: x + (c + 1) * scale] = (255, 255, 255)
        x += 4 * scale


def sheet(argv):
    import numpy as np
    ap = argparse.ArgumentParser(prog="talk sheet")
    ap.add_argument("video")
    ap.add_argument("--every", type=float, default=1.0, help="seconds between pictures (default 1)")
    ap.add_argument("--at", type=float, help="instead of a sheet, save one full-size picture at this second")
    ap.add_argument("--safe", action="store_true", help="draw lines where Instagram's caption (bottom) and buttons (right) sit")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float)
    a = ap.parse_args(argv)
    video = _find(a.video)
    info = _info(video)
    work = _work(video)
    stem = _slug(os.path.splitext(os.path.basename(video))[0])
    if a.at is not None:
        t = min(max(0.0, a.at), max(0.0, info["duration"] - 0.05))
        out = os.path.join(work, f"frame-{stem}-{t:.1f}s.jpg")
        _ff(["-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", "-q:v", "2", "-update", "1", out], "save that picture")
        print(f"Wrote {_rel(out)} (the picture at {t:.1f} s, full size). Open it to check the details.")
        return
    every = max(0.1, a.every)
    end = min(a.end or info["duration"], info["duration"])
    portrait = info["h"] >= info["w"]
    tw = 360 if portrait else 480
    th = int(round(tw * info["h"] / info["w"] / 2)) * 2
    cols, rows = (4, 3) if portrait else (3, 4)
    r = kp.run([kp.ffmpeg(), "-hide_banner", "-nostdin", "-v", "error", "-ss", f"{a.start:.3f}", "-t", f"{max(0.1, end - a.start):.3f}", "-i", video,
                "-vf", f"select='gte(t+0.001,selected_n*{every:.4f})',setpts=N/FRAME_RATE/TB,scale={tw}:{th}:flags=bicubic", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
               capture_output=True, check=False)
    n = len(r.stdout) // (tw * th * 3)
    if r.returncode != 0 or n == 0:
        sys.exit(f"Couldn't take pictures from {os.path.basename(video)}. Check that the video plays normally.")
    frames = np.frombuffer(r.stdout[: n * tw * th * 3], dtype=np.uint8).reshape(n, th, tw, 3).copy()
    if a.safe and portrait:
        frames[:, int(th * 0.80): int(th * 0.80) + 2, :] = (255, 80, 60)       # Instagram's caption starts about here
        frames[:, int(th * 0.52): int(th * 0.80), int(tw * 0.86): int(tw * 0.86) + 2] = (255, 80, 60)   # like / comment buttons
        frames[:, int(th * 0.10): int(th * 0.10) + 2, :] = (255, 80, 60)       # top bar
    bar, pad, per = 30, 6, cols * rows
    outs = []
    pages = (n + per - 1) // per
    for p in range(pages):
        chunk = frames[p * per: (p + 1) * per]
        used_rows = (len(chunk) + cols - 1) // cols
        canvas = np.full((used_rows * (th + bar + pad) + pad, cols * (tw + pad) + pad, 3), 22, dtype=np.uint8)
        for k, fr in enumerate(chunk):
            x, y = pad + (k % cols) * (tw + pad), pad + (k // cols) * (th + bar + pad)
            t = a.start + (p * per + k) * every
            label = f"{int(t // 60)}:{int(t % 60):02d}" + (f".{int(round(t % 1 * 10)) % 10}" if every % 1 else "")
            _label(canvas, label, x + 4, y + 5)
            canvas[y + bar: y + bar + th, x: x + tw] = fr
        out = os.path.join(work, f"sheet-{stem}" + (f"-{p + 1}" if pages > 1 else "") + ".jpg")
        hh, ww = canvas.shape[:2]
        e = kp.run([kp.ffmpeg(), "-hide_banner", "-nostdin", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ww}x{hh}", "-i", "-",
                    "-frames:v", "1", "-q:v", "3", "-update", "1", out], input=canvas.tobytes(), capture_output=True, check=False)
        if e.returncode != 0:
            sys.exit("Couldn't save the sheet. Check there's free space on the disk.")
        outs.append(out)
    print(f"Wrote {len(outs)} sheet{'s' if len(outs) != 1 else ''} with {n} pictures, one every {every:g} s, each labelled with its time:")
    for o in outs:
        print(f"  {_rel(o)}")
    print(f"Look at them. For one moment at full size:  {RUN} sheet {_rel(video)} --at 12.5")
    _next("finish", video)


# ---------------------------------------------------------------- finish

def finish(argv):
    ap = argparse.ArgumentParser(prog="talk finish")
    ap.add_argument("video")
    ap.add_argument("--name", help="file name for the finished reel (default: the work folder's name)")
    a = ap.parse_args(argv)
    video = _find(a.video)
    info = _info(video)
    work = _work(video)
    name = re.sub(r'[<>:"/\\|?*]+', "-", a.name).strip(" .") if a.name else os.path.basename(work)
    name = (name[:-4] if name.lower().endswith(".mp4") else name) or os.path.basename(work)
    os.makedirs(kp.FINISHED, exist_ok=True)
    out = os.path.join(kp.FINISHED, name + ".mp4")
    if os.path.abspath(out) == os.path.abspath(video):
        sys.exit("That file is already in Finished Reels.")
    shutil.copyfile(video, out)
    print(f"Finished: {_rel(out)}  ({_mmss(info['duration'])}, {info['w']}x{info['h']}, {os.path.getsize(out) / 1e6:.1f} MB)")
    if (info["w"], info["h"]) != (W, H):
        print(f"Note: it is {info['w']}x{info['h']}, not {W}x{H}. Run the fit step if it's meant for Reels, TikTok or Shorts.")
    print(f"The working files stay in {_rel(work)} in case you want changes; delete that folder when you're happy.")


STEPS = {"probe": probe, "transcribe": transcribe, "cut": cut, "tighten": tighten, "fit": fit,
         "captions": captions, "level": level, "sheet": sheet, "finish": finish}


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return
    step = STEPS.get(argv[0])
    if not step:
        sys.exit(f"There's no talk step called {argv[0]!r}. The steps are: {', '.join(STEPS)}.")
    try:
        step(argv[1:])
    except subprocess.CalledProcessError as e:
        sys.exit(f"A tool the kit uses stopped with an error ({os.path.basename(str(e.cmd[0]))}). Run the kit's setup step, then try again.")
    except KeyboardInterrupt:
        sys.exit("Stopped.")


if __name__ == "__main__":
    main(sys.argv[1:])
