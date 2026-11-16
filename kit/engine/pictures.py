"""Find free-to-use pictures for a reel, and finish the chosen one the way the user's style says.

usage:
  pictures search <reel> <slot> "<2-3 words>" [--n 12]
  pictures use <reel> <slot> <NN | path to a photo> [--focus X,Y] [--zoom Z] [--gamma G] [--color | --bw | --duotone]
  pictures credits <reel>

search   looks in Openverse, then Wikimedia Commons, for public-domain and CC0 pictures only,
         saves them to work/<reel>/assets/candidates/<slot>/ with a numbered sheet.jpg to pick from.
use      crops the pick to 1080x1920 and finishes it the way My Style says ("photos": color, bw or duotone;
         a flag overrides it). Writes work/<reel>/assets/f/<slot>.jpg and records the credit.
credits  prints the credit lines for the reel.
"""
import html, json, os, re, shutil, sys, tempfile, time, urllib.error, urllib.parse, urllib.request, zlib

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kitpaths

UA = "AI-Video-Editor-kit/1.0"
W, H = 1080, 1920
# what matters on screen is how many source pixels the 9:16 crop is across (it gets stretched to 1080)
GOOD_CROP = 840            # a landscape photo 1,500 px high gives this: stays sharp
MIN_CROP = 500             # anything thinner is skipped at search
SOFT_SHORT = 1000          # `use` warns when the short side is under this
MAX_BYTES = 60 * 1024 * 1024
MAX_SIDE = 4000            # saved candidates are scaled down to this on the long side
COLS, TILE_W, TILE_H = 4, 270, 480
OPENVERSE = "https://api.openverse.org/v1/images/"
COMMONS = "https://commons.wikimedia.org/w/api.php"

# what a downloaded file really is, from its first bytes -> the ffmpeg reader to force.
# Forcing the reader means a file that only pretends to be a picture is never opened as anything else.
MAGIC = ((b"\xff\xd8\xff", "jpeg_pipe"), (b"\x89PNG\r\n\x1a\n", "png_pipe"), (b"GIF8", "gif"),
         (b"II*\x00", "tiff_pipe"), (b"MM\x00*", "tiff_pipe"), (b"BM", "bmp_pipe"))

_last = {}


def _cropw(w, h):
    """how many pixels wide the widest 9:16 crop of a w x h picture is"""
    return min(w, h * W / H)


class Offline(Exception):
    pass


class Busy(Exception):
    pass


SLOW = {"upload.wikimedia.org": 3.0, "thumb.wikimedia.org": 3.0}   # their file servers refuse nameless apps that go faster


def _open(url, timeout, again=2):
    """one polite request: at most one a second per site, generic User-Agent, patient retries when told to slow down"""
    host = urllib.parse.urlsplit(url).netloc
    site = ".".join(host.split(".")[-2:])          # upload.wikimedia.org and thumb.wikimedia.org share one clock
    wait = _last.get(site, 0) + SLOW.get(host, 1.05) - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last[site] = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code in (429, 503):
            try:
                pause = float(e.headers.get("Retry-After") or 5)
            except ValueError:
                pause = 5
            if again and pause <= 20:
                time.sleep(max(pause, 2) + 1)
                return _open(url, timeout, again - 1)
            raise Busy(f"{host} says too many requests (HTTP {e.code})")
        raise OSError(f"{host} answered HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise Offline(f"{host}: {getattr(e, 'reason', e)}")


def _json(url, params):
    with _open(url + "?" + urllib.parse.urlencode(params), 25) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _text(s, limit=200):
    s = html.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


# ---------------------------------------------------------------- sources

def openverse(query):
    data = _json(OPENVERSE, {"q": query, "license": "cc0,pdm", "page_size": 20, "mature": "false"})
    out = []
    for r in data.get("results", []):
        lic = (r.get("license") or "").lower()
        if lic not in ("cc0", "pdm") or (r.get("filetype") or "").lower() in ("svg", "gif"):
            continue
        out.append({"title": _text(r.get("title")) or "Untitled", "author": _text(r.get("creator")) or "Unknown",
                    "licence": "CC0" if lic == "cc0" else "Public Domain Mark",
                    "licence_url": r.get("license_url") or "", "source": r.get("foreign_landing_url") or "",
                    "original": r.get("url") or "", "download": r.get("url") or "",
                    "width": r.get("width") or 0, "height": r.get("height") or 0, "date": "",
                    "description": "", "found_on": "Openverse" + (f" ({r['source']})" if r.get("source") else "")})
    return out


def _free(meta):
    """True only for public domain or CC0, read from the file's own licence fields on Commons"""
    code = _text(meta.get("License", {}).get("value")).lower()
    short = _text(meta.get("LicenseShortName", {}).get("value")).lower()
    if code == "cc0" or code.startswith("cc0-") or code == "pd" or code.startswith("pd-"):
        return True
    return short.startswith("public domain") or short.startswith("cc0") or short.startswith("pd-") or short == "pd"


def commons(query, offset=0):
    data = _json(COMMONS, {"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
                           "gsrsearch": query + " filetype:bitmap", "gsrlimit": 50, "gsroffset": offset,
                           "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 3840})
    pages = sorted((data.get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    out = []
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata") or {}
        if not ii.get("url") or not _free(meta) or ii.get("mime") in ("image/gif", "image/svg+xml"):
            continue
        title = re.sub(r"\.\w{2,5}$", "", (p.get("title") or "").removeprefix("File:"))
        out.append({"title": _text(title) or "Untitled", "author": _text(meta.get("Artist", {}).get("value")) or "Unknown",
                    "licence": _text(meta.get("LicenseShortName", {}).get("value")) or "Public domain",
                    "licence_url": _text(meta.get("LicenseUrl", {}).get("value")),
                    "source": ii.get("descriptionurl") or "", "original": ii["url"],
                    "download": ii.get("thumburl") or ii["url"],
                    "width": ii.get("width") or 0, "height": ii.get("height") or 0,
                    "date": _text(re.split(r"\bdate QS:", _text(meta.get("DateTimeOriginal", {}).get("value")))[0], 60),
                    "description": _text(meta.get("ImageDescription", {}).get("value"), 300),
                    "found_on": "Wikimedia Commons"})
    return out


# ---------------------------------------------------------------- files

def _probe(path, fmt=None):
    """(width, height) as the picture is shown, after any phone rotation; None if ffmpeg can't read it"""
    cmd = [kitpaths.ffprobe(), "-v", "error"] + (["-f", fmt] if fmt else []) + [
        "-select_streams", "v:0", "-show_entries", "stream=width,height:stream_side_data=rotation", "-of", "json", path]
    r = kitpaths.run(cmd, capture_output=True, text=True, check=False)
    try:
        s = json.loads(r.stdout)["streams"][0]
        w, h = int(s["width"]), int(s["height"])
    except (ValueError, KeyError, IndexError):
        return None
    rot = next((d.get("rotation") for d in s.get("side_data_list", []) if "rotation" in d), 0)
    try:
        if abs(int(float(rot))) % 180 == 90:
            w, h = h, w
    except (TypeError, ValueError):
        pass
    return w, h


def _fetch(url, dest):
    """download to dest; returns the ffmpeg reader for the file type, or None if it isn't a picture we accept"""
    with _open(url, 60) as r, open(dest, "wb") as f:
        size = 0
        while chunk := r.read(1 << 16):
            size += len(chunk)
            if size > MAX_BYTES:
                return None
            f.write(chunk)
    with open(dest, "rb") as f:
        head = f.read(16)
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp_pipe"
    return next((fmt for magic, fmt in MAGIC if head.startswith(magic)), None)


def _to_jpg(src, fmt, dest):
    scale = (f"scale=w='if(gte(iw,ih),min(iw,{MAX_SIDE}),-2)':h='if(gte(iw,ih),-2,min(ih,{MAX_SIDE}))':flags=lanczos,"
             "scale=trunc(iw/2)*2:trunc(ih/2)*2")
    r = kitpaths.run([kitpaths.ffmpeg(), "-v", "error", "-y", "-f", fmt, "-i", src, "-frames:v", "1", "-vf", scale,
                      "-pix_fmt", "yuvj420p", "-q:v", "2", dest], capture_output=True, text=True, check=False)
    return r.returncode == 0 and os.path.exists(dest)


# seven-segment digits drawn with plain boxes: works on every computer, no font needed
SEGS = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd", "6": "afgedc", "7": "abc",
        "8": "abcdefg", "9": "abcdfg"}


def _digits(text, x0, y0, dw=18, dh=30, t=4, gap=6):
    half = (dh - t) // 2
    box = {"a": (0, 0, dw, t), "g": (0, half, dw, t), "d": (0, dh - t, dw, t), "f": (0, 0, t, half + t),
           "b": (dw - t, 0, t, half + t), "e": (0, half, t, dh - half), "c": (dw - t, half, t, dh - half)}
    out = [f"drawbox=x={x0 - 8}:y={y0 - 8}:w={len(text) * (dw + gap) - gap + 16}:h={dh + 16}:color=black:t=fill"]
    for i, ch in enumerate(text):
        for seg in SEGS[ch]:
            x, y, w, h = box[seg]
            out.append(f"drawbox=x={x0 + i * (dw + gap) + x}:y={y0 + y}:w={w}:h={h}:color=white:t=fill")
    return ",".join(out)


def make_sheet(folder, numbers):
    """numbered 9:16 black-and-white centre crops, 4 across"""
    sheet = os.path.join(folder, "sheet.jpg")
    with tempfile.TemporaryDirectory() as tmp:
        for i, nn in enumerate(numbers, 1):
            vf = (f"scale={TILE_W}:{TILE_H}:force_original_aspect_ratio=increase:flags=lanczos,crop={TILE_W}:{TILE_H},"
                  f"format=gray,{_digits(nn, 14, 14)}")
            kitpaths.run([kitpaths.ffmpeg(), "-v", "error", "-y", "-i", os.path.join(folder, nn + ".jpg"), "-frames:v", "1",
                          "-vf", vf, os.path.join(tmp, f"t_{i:03d}.png")])
        rows = -(-len(numbers) // COLS)
        kitpaths.run([kitpaths.ffmpeg(), "-v", "error", "-y", "-framerate", "1", "-start_number", "1",
                      "-i", os.path.join(tmp, "t_%03d.png"), "-frames:v", "1",
                      "-vf", f"tile={COLS}x{rows}:margin=10:padding=10:color=0x1c1c1c", "-q:v", "3", sheet])
    return sheet


# ---------------------------------------------------------------- commands

def _slot(name):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,40}", name):
        sys.exit(f"The slot name {name!r} won't work as a file name. Use letters, numbers and dashes, like s03 or hook.")
    return name


def _flags(argv, spec):
    """split argv into positionals and --flags; spec maps a flag to True when it takes a value"""
    pos, opt, i = [], {}, 0
    while i < len(argv):
        a = argv[i]
        if a in spec:
            if spec[a]:
                if i + 1 >= len(argv):
                    sys.exit(f"{a} needs a value after it.")
                opt[a] = argv[i + 1]
                i += 1
            else:
                opt[a] = True
        elif a.startswith("--"):
            sys.exit(f"Unknown option {a}.\n{__doc__}")
        else:
            pos.append(a)
        i += 1
    return pos, opt


def search(argv):
    pos, opt = _flags(argv, {"--n": True})
    if len(pos) != 3:
        sys.exit('usage: pictures search <reel> <slot> "<2-3 words>" [--n 12]')
    reel, slot, query = kitpaths.reel_dir(pos[0]), _slot(pos[1]), pos[2].strip()
    try:
        n = max(1, min(24, int(opt.get("--n", 12))))
    except ValueError:
        sys.exit("--n needs a number, like --n 12.")
    if len(query.split()) > 4:
        print("note: short searches of 2 or 3 words find far more than long ones.")

    found, notes = [], []
    sources = (("Openverse", openverse), ("Wikimedia Commons", commons),
               ("Wikimedia Commons", lambda q: commons(q, 50)))      # a second page only when still short
    for name, source in sources:
        if any(name in note for note in notes):     # that source already failed: don't ask it again
            continue
        if len([c for c in found if _cropw(c["width"], c["height"]) >= GOOD_CROP]) >= n:
            break
        try:
            got = source(query)
        except Busy as e:
            notes.append(f"{name} is rate-limiting right now ({e}). Wait a few minutes before searching again.")
            continue
        except Offline as e:
            notes.append(f"Couldn't reach {name} ({e}).")
            continue
        except (OSError, ValueError) as e:
            notes.append(f"{name} gave an answer that couldn't be read ({e}).")
            continue
        seen = {c["original"] for c in found}
        found += [c for c in got if c["original"] and c["original"] not in seen]
    for note in dict.fromkeys(notes):
        print("note:", note)
    if not found and len(notes) >= 2:
        sys.exit("No picture source could be reached. Check the internet connection and try again in a minute.")

    # known-tiny pictures out; big ones first, the source's own order kept inside each group
    found = [c for c in found if not (c["width"] and c["height"]) or _cropw(c["width"], c["height"]) >= MIN_CROP]
    found.sort(key=lambda c: 0 if _cropw(c["width"], c["height"]) >= GOOD_CROP else 1)
    if not found:
        sys.exit(f"Nothing free to use came back for {query!r}. Try 2 or 3 plainer words, or a different word for the same thing.")

    final = os.path.join(reel, "assets", "candidates", slot)
    folder = final + ".new"                       # built beside the old sheet, so a failed search loses nothing
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder)

    kept, busy = [], {}
    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, "download.bin")
        for c in found:
            if len(kept) >= n:
                break
            site = ".".join(urllib.parse.urlsplit(c["download"]).netloc.split(".")[-2:])
            if busy.get(site, 0) >= 2:              # this site is refusing us: leave it alone for now
                continue
            nn = f"{len(kept) + 1:02d}"
            dest = os.path.join(folder, nn + ".jpg")
            try:
                fmt = _fetch(c["download"], raw)
            except Busy:
                busy[site] = busy.get(site, 0) + 1
                continue
            except (Offline, OSError):
                continue
            if not fmt or not _to_jpg(raw, fmt, dest):
                continue
            size = _probe(dest)
            if not size or _cropw(*size) < MIN_CROP:
                if os.path.exists(dest):
                    os.remove(dest)
                continue
            if max(size) < MAX_SIDE or not (c["width"] and c["height"]):
                c["width"], c["height"] = size      # the file itself is the truth; listings sometimes overstate it
            kept.append({"number": nn, "file": nn + ".jpg", "title": c["title"], "author": c["author"],
                         "licence": c["licence"], "licence_url": c["licence_url"], "source": c["source"],
                         "original": c["original"], "width": c["width"], "height": c["height"], "date": c["date"],
                         "description": c["description"], "found_on": c["found_on"]})
    for site in busy:
        print(f"note: {site} refused some downloads (too many requests), so this sheet is shorter than it could be. "
              "Wait a few minutes before searching again.")
    if not kept:
        shutil.rmtree(folder, ignore_errors=True)
        sys.exit(f"Found pictures for {query!r} but none could be downloaded. Try again in a minute, or try other words.")

    with open(os.path.join(folder, "candidates.json"), "w", encoding="utf-8") as f:
        json.dump({"query": query, "slot": slot, "candidates": kept}, f, indent=2, ensure_ascii=False)
        f.write("\n")
    make_sheet(folder, [c["number"] for c in kept])
    os.makedirs(final, exist_ok=True)
    for f in os.listdir(final):                   # the new search replaces the old candidates for this slot
        if re.fullmatch(r"\d\d\.jpg|sheet\.jpg|candidates\.json", f):
            os.remove(os.path.join(final, f))
    for f in os.listdir(folder):
        shutil.move(os.path.join(folder, f), os.path.join(final, f))
    shutil.rmtree(folder, ignore_errors=True)
    sheet = os.path.join(final, "sheet.jpg")

    print(f"{len(kept)} pictures for {query!r}. Look at the sheet (numbers run left to right, top to bottom):")
    print(" ", os.path.relpath(sheet, kitpaths.ROOT))
    for c in kept:
        soft = "" if _cropw(c["width"], c["height"]) >= GOOD_CROP else "  (small, may look soft)"
        when = f", {c['date']}" if c["date"] else ""
        print(f"  {c['number']}  {c['width']}x{c['height']}  {c['licence']}  {c['title'][:70]}{when}{soft}")
    print("Details (author, source page, description) are in candidates.json next to the sheet.")


def _levels(src, crop):
    """black and white points of the cropped picture, ignoring the darkest and brightest 0.5% (0..1)"""
    r = kitpaths.run([kitpaths.ffmpeg(), "-v", "error", "-i", src, "-frames:v", "1", "-vf", f"{crop},scale=270:480,format=gray",
                      "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=False)
    px = np.frombuffer(r.stdout, dtype=np.uint8)
    if r.returncode != 0 or px.size == 0:
        return None
    lo, hi = np.percentile(px, (0.5, 99.5))
    if hi - lo < 8:
        return 0.0, 1.0
    return float(lo) / 255, float(hi) / 255


def _candidate(path):
    """the candidates.json entry for a downloaded picture, or None when the file isn't one"""
    try:
        with open(os.path.join(os.path.dirname(path), "candidates.json"), encoding="utf-8") as f:
            return next(c for c in json.load(f)["candidates"] if c["file"] == os.path.basename(path))
    except (OSError, ValueError, KeyError, TypeError, StopIteration):
        return None


def use(argv):
    pos, opt = _flags(argv, {"--focus": True, "--zoom": True, "--gamma": True, "--color": False, "--bw": False, "--duotone": False})
    if len(pos) != 3:
        sys.exit("usage: pictures use <reel> <slot> <NN | path to a photo> [--focus X,Y] [--zoom Z] [--gamma G] [--color | --bw | --duotone]")
    style_ = kitpaths.style()[0]
    look_name = next((k[2:] for k in ("--color", "--bw", "--duotone") if opt.get(k)), style_.get("photos", "color"))
    reel, slot, pick = kitpaths.reel_dir(pos[0]), _slot(pos[1]), pos[2]
    try:
        fx, fy = (min(1.0, max(0.0, float(v))) for v in opt.get("--focus", "0.5,0.5").split(","))
        zoom = max(1.0, float(opt.get("--zoom", 1)))
        gamma = min(3.0, max(0.3, float(opt.get("--gamma", 1))))
    except ValueError:
        sys.exit("--focus needs two numbers from 0 to 1 like 0.3,0.5 (across, down); --zoom and --gamma need one number like 1.2.")

    if re.fullmatch(r"\d{1,2}", pick):
        nn = f"{int(pick):02d}"
        src = os.path.join(reel, "assets", "candidates", slot, nn + ".jpg")
        c = _candidate(src)
        if not c or not os.path.exists(src):
            sys.exit(f"There's no picture number {nn} for the slot {slot!r}. Run the search for this slot first, then pick a number from its sheet.")
        credit = {"title": c["title"], "author": c["author"], "licence": c["licence"], "licence_url": c["licence_url"],
                  "source": c["source"]}
    else:
        tries = [pick, os.path.join(kitpaths.ROOT, pick), os.path.join(kitpaths.MY_PHOTOS, pick)]
        src = next((os.path.abspath(p) for p in tries if os.path.isfile(p)), None)
        if not src:
            sys.exit(f"Couldn't find the photo {pick!r}. Put it in the My Photos folder and give its file name.")
        c = _candidate(src)                  # a downloaded candidate given by path keeps its real credit
        credit = {"title": os.path.basename(src), "author": "", "licence": "your own photo", "licence_url": "", "source": ""}
        if c:
            credit = {k: c[k] for k in ("title", "author", "licence", "licence_url", "source")}

    size = _probe(src)
    if not size:
        sys.exit(f"{os.path.basename(src)} couldn't be opened as a picture. Save it as a JPG or PNG and try again.")
    w, h = size
    ch = min(h, w * H / W) / zoom
    cw = ch * W / H
    x = min(w - cw, max(0.0, fx * w - cw / 2))
    y = min(h - ch, max(0.0, fy * h - ch / 2))
    crop = f"crop={int(cw)}:{int(ch)}:{int(x)}:{int(y)}"
    if min(w, h) < SOFT_SHORT or cw < 560:
        print(f"warning: this picture is small ({w}x{h}, the crop uses {int(cw)} px across). It will look soft full-screen; "
              "a bigger picture or less zoom will look sharper.")

    lv = _levels(src, crop)
    if lv is None:
        sys.exit(f"{os.path.basename(src)} couldn't be read. Save it as a JPG or PNG and try again.")
    lo, hi = lv
    base = f"{crop},scale={W}:{H}:flags=lanczos"
    if look_name not in ("bw", "duotone"):
        look_name = "color"
        look = (f"{base},format=gbrp,colorlevels=rimin={lo:.4f}:gimin={lo:.4f}:bimin={lo:.4f}:"
                f"rimax={hi:.4f}:gimax={hi:.4f}:bimax={hi:.4f},eq=gamma={1 / gamma:.3f}")
    else:
        # levels -> gamma -> a little extra contrast around mid grey, then light grain
        curve = f"clip(255*((pow(clip((val-{lo * 255:.2f})/{(hi - lo) * 255:.2f},0,1),{gamma:.3f})-0.5)*1.15+0.5),0,255)"
        seed = zlib.crc32(slot.encode()) % 100000
        look = f"{base},format=gray,lut=y='{curve}',noise=c0s=8:c0f=0:c0_seed={seed},format=gbrp"
        if look_name == "duotone":     # shadows in the style's second colour, highlights in its main colour
            dark, light = style_["colors"]["alt"].lstrip("#"), style_["colors"]["main"].lstrip("#")
            ch_ = lambda hx, i: int(hx[i:i + 2], 16)
            look += ",lutrgb=" + ":".join(f"{c}='{ch_(dark, i)}+({ch_(light, i)}-{ch_(dark, i)})*val/255'" for c, i in (("r", 0), ("g", 2), ("b", 4)))
    out_dir = os.path.join(reel, "assets", "f")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, slot + ".jpg")
    r = kitpaths.run([kitpaths.ffmpeg(), "-v", "error", "-y", "-i", src, "-frames:v", "1", "-vf", look,
                      "-pix_fmt", "yuvj444p", "-q:v", "2", out], capture_output=True, text=True, check=False)
    if r.returncode != 0 or _probe(out) != (W, H):
        sys.exit(f"The picture couldn't be finished. ffmpeg said: {r.stderr.strip()[-300:] or 'nothing'}")

    path = os.path.join(reel, "credits.json")
    credits_ = _read_credits(path)
    credits_[slot] = credit
    with open(path, "w", encoding="utf-8") as f:
        json.dump(credits_, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"saved {os.path.relpath(out, kitpaths.ROOT)} ({W}x{H}, {dict(color='colour', bw='black and white', duotone='duotone')[look_name]})")
    print("credit:", _line(credit))


def _read_credits(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _line(c):
    if c.get("licence") == "your own photo":
        return f"{c.get('title', 'Photo')}: your own photo"
    author = c.get("author") or "Unknown"
    bits = [f"\"{c.get('title', 'Untitled')}\" by {author}", c.get("licence") or "Public domain"]
    return ", ".join(bits) + (f". {c['source']}" if c.get("source") else "")


def credits(argv):
    if len(argv) != 1:
        sys.exit("usage: pictures credits <reel>")
    data = _read_credits(os.path.join(kitpaths.reel_dir(argv[0]), "credits.json"))
    if not data:
        print("No picture credits yet for this reel.")
        return
    print("Pictures")
    for slot in sorted(data):
        print(f"{slot}: {_line(data[slot])}")


def main(argv):
    steps = {"search": search, "use": use, "credits": credits}
    if not argv or argv[0] not in steps:
        sys.exit(__doc__)
    if not shutil.which(os.path.basename(kitpaths.ffmpeg()), path=kitpaths.env()["PATH"]):
        sys.exit("ffmpeg isn't installed yet. Run the kit's setup step first.")
    steps[argv[0]](argv[1:])


if __name__ == "__main__":
    main(sys.argv[1:])
