"""The voiceover: script.txt becomes assets/voice/voice.wav plus a time for every word.

usage: run.py voice <reel> [--voice am_michael] [--speed 1.1]
       run.py voice samples            (writes a short sample of every voice to kit/voice-samples/)

Two ways in:
  - Default: a free voice made on this computer (Kokoro). Each sentence is spoken separately, so sentence
    edges are exact.
  - Your own recording: put it in the reel's assets/voice/ folder as take.m4a (or .mp3, .wav, .mov, .mp4)
    reading script.txt word for word. It's used instead, and sped up a touch (own_voice_tempo in settings.json).
Either way the words are timed by a speech-to-text model (faster-whisper) and lined up with the script's own
words, so captions are spelled exactly as written.

Respellings: if the voice says a word wrong, add it to work/<reel>/say.json, e.g. {"GIF": "jiff"}.
The voice reads the respelling; captions keep the script's spelling.
"""
import difflib, json, os, re, sys, tempfile
import numpy as np
import kitpaths

CACHE = os.path.join(os.path.expanduser("~"), ".cache", "hyperframes", "tts")
MODEL = os.path.join(CACHE, "models", "kokoro-v1.0.onnx")
VOICES = os.path.join(CACHE, "voices", "voices-v1.0.bin")
ENGLISH = {"am_michael": "American man", "am_adam": "American man, deeper", "af_heart": "American woman, warm",
           "af_nova": "American woman, bright", "af_sky": "American woman, light", "bm_george": "British man",
           "bf_emma": "British woman", "bf_isabella": "British woman, softer"}
GAP = 0.7                      # between sentences; the reel engine trims it to what each cut needs
TAKE_EXT = (".m4a", ".mp3", ".wav", ".aac", ".mov", ".mp4", ".caf", ".aiff")
norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())


def ensure_model():
    """the Kokoro model (about 340 MB) arrives on the first use of HyperFrames' own voice command"""
    if os.path.exists(MODEL) and os.path.exists(VOICES):
        return
    print("Downloading the voice model, about 340 MB, once...")
    out = os.path.join(tempfile.gettempdir(), "aive-voice-warmup.wav")
    kitpaths.run(kitpaths.hyperframes("tts", "Ready.", "-o", out, "--json"), capture_output=True)
    if not (os.path.exists(MODEL) and os.path.exists(VOICES)):
        sys.exit("The voice model didn't download. Check the internet connection and run: kit/run.py setup")


def kokoro():
    ensure_model()
    import kokoro_onnx
    return kokoro_onnx.Kokoro(MODEL, VOICES)


def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


def write_wav(path, samples, rate):
    import soundfile as sf
    sf.write(path, samples, rate)


def to48k(src, dst, loud=False):
    af = ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"] if loud else []
    kitpaths.run([kitpaths.ffmpeg(), "-v", "error", "-y", "-i", src, *af, "-ar", "48000", "-ac", "1", dst])


_whisper = [None]


def whisper(model="base.en"):
    if _whisper[0] is None:
        os.environ.setdefault("CT2_VERBOSE", "-1")      # hush ctranslate2's tips
        from faster_whisper import WhisperModel
        _whisper[0] = WhisperModel(model, device="cpu", compute_type="int8")
    return _whisper[0]


def pcm16k(path):
    """the audio as 16 kHz mono floats, decoded by ffmpeg (faster-whisper's own decoder breaks with some PyAV versions)"""
    r = kitpaths.run([kitpaths.ffmpeg(), "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", "16000", "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype="float32").copy()


def heard_words(wav):
    segs, _ = whisper().transcribe(pcm16k(wav), language="en", word_timestamps=True, vad_filter=False, beam_size=5)
    return [{"w": w.word.strip(), "s": float(w.start), "e": float(w.end)} for s in segs for w in (s.words or [])]


def align(text_words, heard):
    """the script's words with the transcriber's times (the transcriber may hear "Claude" as "cloud")"""
    a, b = [norm(w) for w in text_words], [norm(w["w"]) for w in heard]
    t = [None] * len(text_words)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                t[i1 + k] = (heard[j1 + k]["s"], heard[j1 + k]["e"])
        elif tag == "replace":
            s0, e0 = heard[j1]["s"], heard[j2 - 1]["e"]
            for k in range(i2 - i1):
                t[i1 + k] = (s0 + (e0 - s0) * k / (i2 - i1), s0 + (e0 - s0) * (k + 1) / (i2 - i1))
    return t


def fill(t, lo, hi):
    """words the transcriber missed get times spread between their neighbours, inside [lo, hi]"""
    n = len(t)
    for i in range(n):
        if t[i] is None:
            j = i
            while j < n and t[j] is None:
                j += 1
            a = t[i - 1][1] if i else lo
            b = t[j][0] if j < n else hi
            for k in range(i, j):
                f0, f1 = (k - i) / (j - i), (k - i + 1) / (j - i)
                t[k] = (a + (b - a) * f0, a + (b - a) * f1)
    return [(max(lo, min(s, hi)), max(lo, min(e, hi))) for s, e in t]


def respell(sentence, say):
    if not say:
        return sentence
    out = []
    for w in sentence.split():
        core = re.sub(r"^\W+|\W+$", "", w)
        if core in say:
            w = w.replace(core, say[core])
        out.append(w)
    return " ".join(out)


def from_kokoro(reel, v, voice, speed):
    text = open(os.path.join(reel, "script.txt"), encoding="utf-8").read().strip()
    say_path = os.path.join(reel, "say.json")
    say = json.load(open(say_path, encoding="utf-8")) if os.path.exists(say_path) else {}
    model = kokoro()
    pieces, spans, t = [], [], 0.0
    rate = 24000
    for sent in sentences(text):
        samples, rate = model.create(respell(sent, say), voice=voice, speed=speed, lang="en-us" if voice[0] == "a" else "en-gb")
        samples = np.asarray(samples, dtype="float32")
        # Kokoro leaves a little silence at each end; trim it so the gaps between sentences are ours
        loud = np.where(np.abs(samples) > 0.004)[0]
        if len(loud):
            samples = samples[max(0, loud[0] - int(0.03 * rate)): loud[-1] + int(0.06 * rate)]
        pieces.append(samples)
        spans.append((sent, t, t + len(samples) / rate))
        t += len(samples) / rate
        pieces.append(np.zeros(int(GAP * rate), dtype="float32"))
        t += GAP
    raw = os.path.join(v, "voice.kokoro.wav")
    write_wav(raw, np.concatenate(pieces[:-1]), rate)
    to48k(raw, os.path.join(v, "voice.wav"))
    heard = heard_words(os.path.join(v, "voice.wav"))
    words = []
    for sent, s0, s1 in spans:
        inside = [h for h in heard if h["s"] < s1 + 0.05 and h["e"] > s0 - 0.05]
        tw = sent.split()
        times = fill(align(tw, inside), s0, s1)
        words += [{"w": w, "s": round(s, 3), "e": round(e, 3)} for w, (s, e) in zip(tw, times)]
    meta = {"source": "kokoro", "voice": voice, "speed": speed, "tempo": 1.0}
    return text, words, meta


def from_take(reel, v, take):
    text = open(os.path.join(reel, "script.txt"), encoding="utf-8").read().strip()
    wav = os.path.join(v, "voice.wav")
    to48k(take, wav, loud=True)
    heard = heard_words(wav)
    if not heard:
        sys.exit(f"No speech found in {os.path.basename(take)}. Is it the right file?")
    tw = text.split()
    times = fill(align(tw, heard), max(0.0, heard[0]["s"] - 0.1), heard[-1]["e"] + 0.1)
    words = [{"w": w, "s": round(s, 3), "e": round(e, 3)} for w, (s, e) in zip(tw, times)]
    matched = sum(1 for h in heard if norm(h["w"]) in {norm(w) for w in tw}) / max(1, len(heard))
    if matched < 0.7:
        print(f"warning: only {matched:.0%} of what was heard matches script.txt. Read the script word for word, or edit script.txt to what you said.")
    meta = {"source": "recording", "file": os.path.basename(take), "tempo": kitpaths.settings()["own_voice_tempo"]}
    return text, words, meta


def samples():
    out = os.path.join(kitpaths.KIT, "voice-samples")
    os.makedirs(out, exist_ok=True)
    model = kokoro()
    for voice, desc in ENGLISH.items():
        s, rate = model.create("Here's how this reel will sound with my voice.", voice=voice, speed=1.1, lang="en-us" if voice[0] == "a" else "en-gb")
        tmp = os.path.join(out, f"{voice}.wav")
        write_wav(tmp, s, rate)
        kitpaths.run([kitpaths.ffmpeg(), "-v", "error", "-y", "-i", tmp, "-ac", "1", "-b:a", "96k", os.path.join(out, f"{voice}.mp3")])
        os.remove(tmp)
        print(f"{voice}.mp3  {desc}")


def main(argv):
    if not argv:
        sys.exit(__doc__)
    if argv[0] == "samples":
        return samples()
    reel = kitpaths.reel_dir(argv[0])
    s = kitpaths.settings()
    voice = argv[argv.index("--voice") + 1] if "--voice" in argv else s["voice"]
    speed = float(argv[argv.index("--speed") + 1]) if "--speed" in argv else kitpaths.voice_speed()
    v = os.path.join(reel, "assets", "voice")
    os.makedirs(v, exist_ok=True)
    if not os.path.exists(os.path.join(reel, "script.txt")) or not open(os.path.join(reel, "script.txt"), encoding="utf-8").read().strip():
        sys.exit("script.txt is empty. Write the script first.")
    takes = [os.path.join(v, f) for f in sorted(os.listdir(v)) if f.startswith("take") and f.lower().endswith(TAKE_EXT)]
    if takes:
        print(f"Using your recording: {os.path.basename(takes[0])}")
        text, words, meta = from_take(reel, v, takes[0])
    else:
        if voice not in ENGLISH:
            print(f"note: {voice} isn't one of the tested English voices ({', '.join(ENGLISH)})")
        text, words, meta = from_kokoro(reel, v, voice, speed)
    assert len(words) == len(text.split())
    json.dump(words, open(os.path.join(v, "voice.words.json"), "w"), indent=0)
    json.dump(meta, open(os.path.join(v, "voice.meta.json"), "w"), indent=1)
    length = kitpaths.duration(os.path.join(v, "voice.wav"))
    print(f"voice ready: {len(words)} words, {meta['source']}. The build prints the reel's real pace (about 3.2 to 3.6 words a second is right).")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main(sys.argv[1:])
