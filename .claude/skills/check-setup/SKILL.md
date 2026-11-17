---
name: check-setup
description: Check and install everything the AI Video Editor needs (the video renderer, a voice, ffmpeg, Python), pick a voice, make a 3-second test reel, then hand over to setting up the user's own look. Use when the user says "check my setup", "set me up", "install", "is everything ready", "it's not working", "something broke", or before the first reel if setup hasn't passed yet.
---

# Check my setup

The user may not be technical. Do the work yourself and talk in plain words: say what you're doing in one line, never paste long logs at them, and only hand them a step when a computer genuinely needs a person (a password, a click on a system prompt).

Everything runs from this folder (the one with `kit/` and `README.md` in it) through one command:

```
uv run --project kit kit/run.py <step>
```

## 0. Is the kit in this folder?

Look for `kit/run.py` in the current folder.

- **There:** go on.
- **Missing, and this skill came from the plugin:** the kit sits three folders above this SKILL.md (the plugin's root, which has `kit/`, `README.md`, `CLAUDE.md`, `settings.json`). Copy `kit/`, `README.md`, `CLAUDE.md`, `CREDITS.md`, `LICENSE`, `settings.json` and the folders `Finished Reels/`, `My Photos/`, `My Footage/`, `My References/`, `My Style/`, `work/` into the current folder (skip `kit/.venv` and `kit/tools` if present), then go on. Tell the user this folder is now their AI Video Editor folder.
- **Missing, no plugin:** the kit hasn't been downloaded. Use the paste line from the README: download `https://github.com/arturioni/ai-video-editor/archive/refs/heads/main.zip`, unzip it, and move everything inside `ai-video-editor-main/` (hidden files too) into this folder.

## 1. Tell them what's coming

One short message: "I'll check what's installed and add what's missing. The first time downloads about 1 GB (a voice, a speech model, a headless browser) and takes 5 to 15 minutes. Nothing needs a password or an account. You'll see a few permission requests while I work: click Allow each time."

## 1b. Is this computer new enough?

On a Mac, run `sw_vers -productVersion`. The kit needs **macOS 13.5 (Ventura) or newer**, on Apple Silicon or Intel: its voice and speech parts and the renderer aren't built for anything older. If the version is lower, stop and say so plainly: "This kit needs macOS 13.5 or newer, and this Mac has <version>. If it can update (Apple menu > System Settings > General > Software Update), update it and say check my setup again." Don't try to work around it.

The kit is English only for now (the voices, the word timing and the captions). If they ask for another language, tell them plainly.

## 2. Make sure `uv` is there

`uv` brings its own Python, so the kit never depends on what Python the computer has. Check with `uv --version`.

If it's missing, install it (no password needed):

- Mac or Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

The installer puts `uv` in `~/.local/bin` (Windows: `%USERPROFILE%\.local\bin`). If `uv` still isn't found in this chat, call it by that full path, e.g. `~/.local/bin/uv run --project kit kit/run.py doctor`. A new chat will find it normally.

## 3. Look, then install

1. `uv run --project kit kit/run.py doctor` shows what's ready (✓) and what isn't (✗). The first run also builds the kit's own Python in `kit/.venv` (a minute or two).
2. **While it works, ask which voice they'd like:** "There are English voice samples in `kit/voice-samples/` you can click to hear: am_michael (American man, the default), am_adam, af_heart, af_nova, af_sky, bm_george, bf_emma, bf_isabella. You can also record your own voice for any reel later." Save it in `settings.json` (`voice`). Don't wait for the answer before going on.
3. `uv run --project kit kit/run.py setup` installs whatever is missing, then runs `doctor` again and makes a 3-second test reel through the whole chain (voice, timing, drawing, rendering, sound). Run it in the background if your tools allow; it can take several minutes the first time. What it installs, all inside this folder or the usual download caches:
   - Node.js, if the computer has none (or it's older than version 22): unpacked into `kit/tools/node`.
   - ffmpeg and ffprobe, if missing: a ready-built copy in `kit/tools/ffmpeg`.
   - The headless Chrome the renderer draws frames with.
   - The voice model (about 340 MB) and the word-timing model (about 145 MB).
4. Open the test reel's frames to confirm it looks right: `uv run --project kit kit/run.py final setup-test`, then look at the contact sheet it names.

`setup` is safe to run again any time; it only fills gaps.

## 4. If something fails

Read the ✗ line and fix that one thing, then run `doctor` again. Common cases:

- **No internet, or a work network blocks downloads:** say so plainly; the downloads come from github.com, nodejs.org, huggingface.co, pypi.org and the HyperFrames registry.
- **A download stopped halfway:** just run `setup` again.
- **The first `uv run` stops with "no wheels with a matching platform tag" or "has no usable wheels":** the Mac is older than macOS 13.5 (see 1b). Say so plainly.
- **The Mac asks to install "command line developer tools":** that's macOS offering git; it isn't needed. They can click Cancel.
- **Windows asks "Do you want to allow this app to make changes?":** they click Yes.
- **Rendering fails with a Chrome error:** run `uv run --project kit kit/run.py setup` again (it fetches the headless Chrome), then try the render again.
- **Very old computer or little disk space:** the kit needs about 2 GB free.

If you're stuck after two tries on the same error, tell the user what failed in one sentence and what you'd try next.

## 5. Their look

Once setup passes, the reels need a look of their own. Follow the `set-up-my-style` skill: it asks for reels they like (saved in `My References/`), their handle and how they talk, and builds `My Style/`. If they want to skip it for now, run `uv run --project kit kit/run.py style start clean` (or `bold`, `soft`: previews in `kit/styles/*/preview.jpg`) so reels have a neutral look until they set their own.

## 6. Report

A short tick list in plain words (Node, ffmpeg, voice, word timing, renderer, test reel), where the test reel is (`Finished Reels/setup-test.mp4`), then:

"You're ready. Type what your reel is about in one line, like: make a reel about why airplane food tastes so bland."
