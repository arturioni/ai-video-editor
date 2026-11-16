---
name: make-reel
description: Make a finished vertical reel (1080x1920, for Instagram, TikTok or Shorts) from one line - writes the script in the user's voice, records the voiceover, animates every scene in the user's own style, times the captions to every word, checks its own frames before anyone sees them, renders and adds sound effects. Use when the user says "make a reel about...", "make a video about...", "new reel", "turn this into a reel", or gives feedback on a reel they made here ("this feels off", "change the hook", "make it shorter", "different picture"), even if they don't name the skill. Not for editing video they filmed of themselves (that's edit-talking-head).
---

# Make a reel

The user types one line and gets a finished MP4 in their own look and voice. Go straight through without stopping to ask, unless they said "script first" or setup isn't done. Keep them posted with one short line per stage ("Script written, making the voice now."), and show the script in the chat when it's written so they can stop you if they want.

All commands run from this folder (the one with `kit/` in it):

```
uv run --project kit kit/run.py <step> <reel>
```

Read these when you reach the stage that needs them: `references/script.md`, `references/craft.md`, `references/scenes.md`, `references/pictures.md`, `references/checks.md`, `references/voice.md`. The worked example of a whole reel is `kit/examples/airplane-food/`.

## 0. Ready?

1. `uv run --project kit kit/run.py doctor`. All ✓: carry on. Any ✗: follow the `check-setup` skill first, then come back. If `uv` isn't found, see check-setup step 2.
2. **Their look and voice.** Read `My Style/style.md` and `My Style/voice.md`, and run `style show`. If there's no `My Style/style.json` yet, say in one line that the reel will use the neutral Clean starter look and that "set up my style" makes it theirs, then go on (don't stop to set it up unless they ask).

## 1. Start the reel

Pick a short name in lowercase with hyphens (`airplane-food`), then:

```
uv run --project kit kit/run.py new airplane-food "Why airplane food tastes so bland"
```

This makes `work/airplane-food/` with an empty `script.txt`, a starter `scenes.py` and `STATUS.md`. If the name exists, it's an earlier reel: read its `STATUS.md` and ask whether to continue it or start a new one.

## 2. Script

Follow `references/script.md` and their `My Style/voice.md`: their audience, their tone, their words, their usual ending. In short: 60 to 95 words (about 18 to 28 seconds), a hook under 8 words, one idea per sentence, spoken English, only claims you're sure are true, and a last line that tells people what to do. Write it to `script.txt` as plain text, then paste it in the chat with its word count.

## 3. Voice

```
uv run --project kit kit/run.py voice airplane-food
```

Uses the voice in `settings.json` at the pace in their style. To use the user's own recording instead, see `references/voice.md`. If a word is mispronounced, add a respelling to `work/<reel>/say.json` and run it again.

## 4. Plan the scenes

Split the script into lines (one sentence each, or two short ones). For each line decide, in a few words, what's on screen and why it carries the line: a photo, or a drawn scene (big words, a number, marks, a doodle). Rules from `references/craft.md` and their `style.md`:

- Every picture shows what the line says. Ask: would someone with the sound off get it?
- At most 3 or 4 photos in a short reel; the rest drawn. Alternate the two grounds (`main`, `alt`) so cuts are felt.
- Mark lines as `"move"` (comes in with the style's transition) or `"cut"` (plain cut). Use moves on the lines where the topic shifts, 2 to 4 in a 25-second reel.
- At most one `takeover` (the accent fills the frame) per reel, on its biggest turn.

Write the plan into `STATUS.md` (one line per scene).

## 5. Pictures

For each photo scene: search, look at the sheet, check the candidate, use it. Full guide: `references/pictures.md`. Photos are finished the way their style says (colour, black and white or duotone).

```
uv run --project kit kit/run.py pictures search airplane-food cabin "airliner cabin"
uv run --project kit kit/run.py pictures use airplane-food cabin 03 --focus 0.5,0.45
```

Open the finished `work/<reel>/assets/f/<slot>.jpg` to check it. Photos the user put in `My Photos/` come first if they fit. If nothing good turns up after two searches, make that scene a drawn one.

## 6. Write scenes.py

Fill in `work/<reel>/scenes.py` with `references/scenes.md` open and the worked example `kit/examples/airplane-food/scenes.py` beside it. `LINES` must match `script.txt` word for word. Use the ready-made pieces (`stack`, `count`, `takeover`, `strike`, `circle`, `doodle`, `typed`, `stamp_words`...) and `caps(key)` for captions on every line. Colours, fonts and caption looks come from their style by themselves; pass `color=ACCENT` only for the accent.

## 7. Build and check it yourself

```
uv run --project kit kit/run.py build airplane-food
uv run --project kit kit/run.py check airplane-food
```

`build` prints the reel's length and pace, and `check:` lines for rules it can test in code; fix those. `check` snapshots every moment that matters onto labelled sheets in `work/<reel>/renders/check/`. Open every sheet and go through `references/checks.md`, and compare with their `style.md`. Fix what's wrong in `scenes.py`, build, and re-check just those moments with `check <reel> --at 3.2,7.5`. At most two rounds of fixes; if something still bothers you, mention it when you deliver.

## 8. Render, sound, final look

```
uv run --project kit kit/run.py render airplane-food      (1 to 3 minutes: run it in the background)
uv run --project kit kit/run.py sound airplane-food
uv run --project kit kit/run.py final airplane-food
uv run --project kit kit/run.py finish airplane-food
```

`sound` mixes the voice with light paper-and-pen sound effects on transitions, arrivals and marks (or none, if their style says `"sound": "off"`), at a steady loudness for phones. There's no music: people add a trending song in the app when they post. `final` makes a one-frame-a-second contact sheet and prints the length and loudness: open the sheet and confirm nothing broke in the render. `finish` copies it to `Finished Reels/` (a new version never overwrites an old one) with a credits file for the photos.

## 9. Hand it over

Tell the user, briefly: where the file is, how long it is, what's in it (one line), and that you can't hear audio, so they should play it and judge the voice and sound themselves. Suggest adding a song in Instagram or TikTok when posting. Then update `STATUS.md` (what was made, the version, anything left).

## Feedback

"If something feels off, just tell me, like you would a real editor." Treat their words the way an editor would:

- **Vague** ("feels off", "boring"): look at the final sheet, name your two best guesses in one line each, and fix the likelier one.
- **Wording** ("change the hook", "shorter"): edit `script.txt`, then voice, then update `LINES` and the scenes the change touches, then build, check, render, sound, finish.
- **Look for this reel** ("different picture", "bigger words"): change only `scenes.py` (or the picture), then build, check those moments, render, sound, finish.
- **Look for every reel** ("I want my colours", "captions always at the top"): that's their style: follow `set-up-my-style`, then rebuild this reel.
- **Voice** ("sounds robotic", "different voice"): try another voice in `settings.json` or offer their own recording (`references/voice.md`).

Every new version goes to `Finished Reels/` as `<reel>-v2.mp4`, `-v3`... Record each note and what you changed in `STATUS.md`.

## Don't

- Don't post anywhere or upload the video. The user posts it.
- Don't download videos or music from Instagram, TikTok or YouTube.
- Don't use a photo of a real, recent, identifiable person unless the user gave it to you.
- Don't copy another creator's look wholesale, their logo, mascot or catchphrases, even when they're the user's reference.
