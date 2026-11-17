# AI Video Editor

This folder makes finished vertical reels (1080x1920) with Claude: script, voiceover, animated scenes in the user's own style (`My Style/`), captions timed to every word, a self-check of the frames, render and sound. The person using it may not be technical: do the work, talk in plain words, keep updates to one line, and never paste long logs at them.

## What they can say

| They say | Use |
|---|---|
| "check my setup", "it's not working" | the `check-setup` skill |
| "set up my style", "make it look like this", "change my colours", "use Artur's look" | the `set-up-my-style` skill |
| "make a reel about ...", or feedback on a reel | the `make-reel` skill |
| "remake this reel", a pasted transcript, "why did this work" | the `remake-reel` skill |
| "edit this video" (footage of themselves talking) | the `edit-talking-head` skill |

The skills are in `.claude/skills/`. If they don't seem to be loaded (for example right after the kit was downloaded into this folder), read the skill's `SKILL.md` directly and follow it.

## Where things live

- `Finished Reels/`: every finished MP4, with a credits file for its photos.
- `work/<reel>/`: one folder per reel: `script.txt`, `scenes.py`, `STATUS.md`, `assets/`, `renders/`. Read a reel's `STATUS.md` before touching it, and keep it current (short).
- `My Style/`: their look (`style.json`, read by the engine), `style.md` (the look in words) and `voice.md` (how their scripts sound). Read both .md files before making a reel.
- `My References/`: reels and screenshots they like, for their style and for remakes.
- `My Photos/`, `My Footage/`: the user's own pictures and videos.
- `settings.json`: their voice.
- `kit/`: the engine. Change it only if the user asks; reels are made in `work/`.

## Rules

- Run everything through `uv run --project kit kit/run.py <step>` from this folder (`kit/run.py help` lists the steps). It uses the kit's own Python and tools, so don't install Python packages or call system Python.
- You can't hear audio. Say so, and let the user judge the voice and sound.
- The kit works in English only for now (voices, word timing, captions and fonts). If they ask for another language, say so plainly instead of trying.
- Never post or upload anything for them, and never download videos or music from Instagram, TikTok or YouTube.
- No keys or passwords in chat or in files here.
