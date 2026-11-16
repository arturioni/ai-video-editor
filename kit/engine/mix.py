"""The sound pass: the voice plus the paper sounds, mixed onto the finished picture.

usage: uv run --project kit kit/run.py sound <reel>

Reads, inside work/<reel>/renders/:
  <reel>-silent.mp4      the render (its picture is copied untouched)
  voice.timed.wav        the voiceover, already on the reel's timing
  project/timing.json    {"total": seconds, ...}
  sound/events.json      [{"t": seconds, "label": "whoosh"}, ...]   (optional: without it the reel gets the voice only)

Writes renders/<reel>.mp4 (and renders/sound/effects.wav, the paper sounds on their own).

How it is mixed: the voice is brought to -17 LUFS; every event plays the next clip of its label from
kit/assets/sounds/sounds.json, at that clip's level and start offset; the paper sounds dip a little while the voice
speaks; the whole mix is then set to -14 LUFS with its peaks held near -1.5 dBTP, and the finished file is measured.
There is no music on purpose: the song is added in the app when the reel is posted.
"""
import json, math, os, re, subprocess, sys

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kitpaths

SR = 48000
VOICE_LUFS = -17.0        # the voice sits here before the mix; without it the paper comes out 3 to 5 dB too loud
MIX_LUFS = -14.0          # what Instagram, TikTok and Shorts play at
CEILING_DBTP = -1.5       # true-peak ceiling of the finished file
AAC_HEADROOM = 0.7        # the AAC encoder throws peaks up to about this far over what it was given
DUCK = "threshold=0.05:ratio=2:attack=8:release=160"       # light: the paper stays heard under the voice
SOUNDS = os.path.join(kitpaths.ASSETS, "sounds")
USAGE = "usage: uv run --project kit kit/run.py sound <reel>"


def ff(args, what):
    """run ffmpeg quietly; a failure ends in one plain sentence plus ffmpeg's own last lines"""
    r = kitpaths.run([kitpaths.ffmpeg(), "-hide_banner", "-nostats", "-y", *args], check=False, capture_output=True, text=True,
                     encoding="utf-8", errors="replace")
    if r.returncode != 0:
        tail = "\n".join(r.stderr.strip().splitlines()[-6:])
        sys.exit(f"Couldn't {what}. ffmpeg said:\n{tail}")
    return r.stderr


def measure(path):
    """(integrated loudness in LUFS, true peak in dBTP) of a file's first audio track; None where there is no reading"""
    err = ff(["-i", path, "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"], f"measure the loudness of {os.path.basename(path)}")
    summary = err[err.rfind("Summary:"):] if "Summary:" in err else ""

    def num(pattern):
        m = re.search(pattern, summary)
        try:
            v = float(m.group(1)) if m else None
        except ValueError:
            v = None
        return v if v is not None and math.isfinite(v) and v > -69.0 else None

    return num(r"\bI:\s*(-?[\d.]+|-?inf|nan)\s*LUFS"), num(r"\bPeak:\s*(-?[\d.]+|-?inf|nan)\s*dBFS")


def probe(path, stream, entry):
    r = kitpaths.run([kitpaths.ffprobe(), "-v", "error", "-select_streams", stream, "-show_entries", f"stream={entry}",
                      "-of", "csv=p=0", path], check=False, capture_output=True, text=True)
    return r.stdout.strip().splitlines()[0].strip().strip(",") if r.returncode == 0 and r.stdout.strip() else ""


def video_length(path):
    try:
        return float(probe(path, "v:0", "duration"))
    except ValueError:
        return kitpaths.duration(path)


def load_sounds():
    path = os.path.join(SOUNDS, "sounds.json")
    if not os.path.exists(path):
        sys.exit("The kit's sounds are missing (kit/assets/sounds/sounds.json). Download the kit again, or restore that folder.")
    return json.load(open(path, encoding="utf-8"))["labels"]


def load_events(path):
    if not os.path.exists(path):
        print("No sound/events.json for this reel, so it gets the voice only.")
        return []
    try:
        ev = json.load(open(path, encoding="utf-8"))
    except ValueError as e:
        sys.exit(f"sound/events.json isn't valid JSON ({e}). Build the reel's scenes again to rewrite it.")
    if not isinstance(ev, list):
        sys.exit('sound/events.json should be a list like [{"t": 1.2, "label": "land"}]. Build the reel\'s scenes again to rewrite it.')
    return ev


def effects_bus(events, labels, dur):
    """every event's clip added onto one mono track of the reel's length -> (samples, how many of each label were placed)"""
    n = int(round(dur * SR))
    bus = np.zeros(n, dtype=np.float64)
    turn, placed, unknown, cache = {}, {}, {}, {}
    good = []
    for e in events:
        t = e.get("t") if isinstance(e, dict) else None
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t):
            print(f"warning: skipped a sound event without a time: {e!r}", file=sys.stderr)
            continue
        good.append((float(t), str(e.get("label", ""))))
    for t, label in sorted(good):
        if label not in labels or not labels[label].get("clips"):
            unknown[label] = unknown.get(label, 0) + 1
            continue
        if not 0 <= t < dur:
            print(f"warning: skipped '{label}' at {t:.2f}s, which is outside the reel (0 to {dur:.2f}s)", file=sys.stderr)
            continue
        clips = labels[label]["clips"]
        k = turn.get(label, 0)
        turn[label] = k + 1
        c = clips[k % len(clips)] if labels[label].get("rotate", True) else clips[0]
        name = c["clip"]
        if name not in cache:
            p = os.path.join(SOUNDS, name)
            if not os.path.exists(p):
                sys.exit(f"The sound {name} is missing from kit/assets/sounds. Download the kit again, or restore that folder.")
            x, sr = sf.read(p, dtype="float64", always_2d=True)
            if sr != SR:
                sys.exit(f"The sound {name} isn't 48 kHz. Use the clips that came with the kit.")
            cache[name] = x.mean(axis=1)
        x = cache[name] * 10 ** (float(c.get("gain_db", 0.0)) / 20.0)
        start = int(round((t + float(c.get("nudge", 0.0))) * SR))
        if start < 0:                                # it would begin before the reel does: drop that part, fade the rest in
            x = x[-start:].copy()
            f = min(len(x), int(0.004 * SR))
            x[:f] *= np.linspace(0.0, 1.0, f, endpoint=False)
            start = 0
        if start + len(x) > n:                       # it would run past the end: fade it out at the last frame
            x = x[:n - start].copy()
            f = min(len(x), int(0.03 * SR))
            if f:
                x[-f:] *= np.linspace(1.0, 0.0, f)
        bus[start:start + len(x)] += x
        placed[label] = placed.get(label, 0) + 1
    for label, count in unknown.items():
        print(f"warning: skipped {count} event(s) labelled '{label}': the kit has no sound for that. "
              f"Labels it knows: {', '.join(labels)}.", file=sys.stderr)
    return bus, placed


def premix(voice, voice_gain, fx, dur, out):
    """voice (raised, padded to the reel's length) + the paper sounds dipping under it -> one unmastered wav"""
    # ffmpeg's own mono -> stereo takes 3 dB off, so a mono voice is copied to both sides by hand
    to_stereo = "pan=stereo|c0=c0|c1=c0" if probe(voice, "a:0", "channels") == "1" else "aformat=channel_layouts=stereo"
    v = f"[0:a]aresample={SR},{to_stereo},volume={voice_gain:.2f}dB,apad=whole_dur={dur:.3f},atrim=end={dur:.3f}"
    if fx is None:
        graph, inputs = f"{v}[mix]", ["-i", voice]
    else:
        graph = (f"{v},asplit=2[v][vk];[vk]highpass=f=250,lowpass=f=3800[key];"
                 f"[1:a]aformat=sample_rates={SR}:channel_layouts=stereo[fx];[fx][key]sidechaincompress={DUCK}[fxd];"
                 f"[v][fxd]amix=inputs=2:normalize=0:dropout_transition=0:duration=first[mix]")
        inputs = ["-i", voice, "-i", fx]
    ff([*inputs, "-filter_complex", graph, "-map", "[mix]", "-t", f"{dur:.3f}", "-ar", str(SR), "-c:a", "pcm_f32le", out], "mix the voice and the sounds")


def master(video, mix, gain, limit_db, dur, out):
    """picture copied; audio = the mix, gained, limited, AAC 48 kHz stereo, cut to the picture's length"""
    chain = f"[1:a]volume={gain:.2f}dB,alimiter=limit={10 ** (limit_db / 20.0):.5f}:level=0:latency=1,atrim=end={dur:.3f}[a]"
    ff(["-i", video, "-i", mix, "-filter_complex", chain, "-map", "0:v:0", "-map", "[a]", "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2", "-t", f"{dur:.3f}", "-movflags", "+faststart", out], "write the finished reel")


def main(argv):
    argv = list(argv)
    if len(argv) == 2 and argv[0] == "sound":
        argv = argv[1:]
    if len(argv) != 1 or argv[0].startswith("-"):
        sys.exit(USAGE)
    d = kitpaths.reel_dir(argv[0])
    slug = os.path.basename(d)
    r = os.path.join(d, "renders")
    video = os.path.join(r, f"{slug}-silent.mp4")
    voice = os.path.join(r, "voice.timed.wav")
    timing = os.path.join(r, "project", "timing.json")
    if not os.path.exists(video):
        sys.exit(f"There's no picture yet for {slug} (renders/{slug}-silent.mp4). Render the reel first, then run the sound step.")
    if not os.path.exists(voice):
        sys.exit(f"There's no voice yet for {slug} (renders/voice.timed.wav). Make the voice first, then run the sound step.")
    dur = video_length(video)
    if os.path.exists(timing):
        try:
            total = float(json.load(open(timing, encoding="utf-8"))["total"])
            if abs(total - dur) > 0.25:
                print(f"note: timing.json says {total:.2f}s but the render is {dur:.2f}s long; the sound follows the render")
        except (ValueError, KeyError, TypeError):
            print("warning: project/timing.json has no readable \"total\"; the sound follows the render's length", file=sys.stderr)
    else:
        print("warning: no project/timing.json; the sound follows the render's length", file=sys.stderr)

    sdir = os.path.join(r, "sound")
    os.makedirs(sdir, exist_ok=True)
    labels = load_sounds()
    bus, placed = effects_bus(load_events(os.path.join(sdir, "events.json")), labels, dur)
    fx = None
    if placed:
        fx = os.path.join(sdir, "effects.wav")
        sf.write(fx, np.column_stack([bus, bus]), SR, subtype="PCM_24")
        print("sounds placed: " + ", ".join(f"{placed[k]} {k}" for k in labels if k in placed))

    v_lufs, _ = measure(voice)
    if v_lufs is None:
        sys.exit("The voice file is silent or too short to measure (renders/voice.timed.wav). Make the voice again.")
    voice_gain = VOICE_LUFS - v_lufs
    print(f"voice: {v_lufs:.1f} LUFS, moved {voice_gain:+.1f} dB to {VOICE_LUFS:.0f}")

    pre = os.path.join(sdir, "premix.wav")
    premix(voice, voice_gain, fx, dur, pre)
    pre_lufs, _ = measure(pre)
    out = os.path.join(r, f"{slug}.mp4")
    gain = MIX_LUFS - pre_lufs
    limit_db = CEILING_DBTP - AAC_HEADROOM
    lufs = peak = None
    for attempt in range(5):                         # set the level, encode, measure the real file, correct, repeat
        master(video, pre, gain, limit_db, dur, out)
        lufs, peak = measure(out)
        if lufs is None or peak is None:
            sys.exit("Couldn't measure the finished reel's loudness. Run the sound step again.")
        over = peak - CEILING_DBTP
        off = MIX_LUFS - lufs
        if abs(off) <= 0.3 and over <= 0.3:
            break
        if over > 0.3:
            limit_db -= over
        if abs(off) > 0.3:
            gain += off
    os.remove(pre)

    alen = probe(out, "a:0", "duration")
    print(f"loudness: {lufs:.1f} LUFS integrated, true peak {peak:.1f} dBTP (aim {MIX_LUFS:.0f} LUFS, {CEILING_DBTP} dBTP)")
    print(f"length: picture {video_length(out):.3f}s, sound {float(alen):.3f}s" if alen else f"length: {kitpaths.duration(out):.3f}s")
    if abs(lufs - MIX_LUFS) > 1.0 or peak > -1.0:
        print("warning: the mix didn't reach its target loudness. The voice may have very loud moments; make the voice again or tell Claude.", file=sys.stderr)
    print(f"done: {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
