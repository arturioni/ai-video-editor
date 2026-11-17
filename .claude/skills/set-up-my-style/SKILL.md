---
name: set-up-my-style
description: Set up or change the look and voice of the user's reels - colours, fonts, captions, transitions, photo treatment, pace, signature, and how the scripts sound - from reels or screenshots they like, or from a starter look. Use when the user says "set up my style", "make it look like this", "here are reels I like", "change my colours/font/captions", "use my brand", "it doesn't look like me", "use Artur's look", "make it look like the reel", or during first setup, even if they don't name the skill.
---

# Set up my style

Every reel is made in the user's own look, stored in `My Style/`:

| File | What it is | Who reads it |
|---|---|---|
| `My Style/style.json` | colours, fonts, caption look, transition, motion, marks, texture, photo treatment, pace, sound, signature | the engine |
| `My Style/style.md` | the look in words: references, what to borrow, do and don't | you, before every reel |
| `My Style/voice.md` | who the reels are for, how they talk, words to use or avoid, how reels end | you, before every script |
| `My Style/fonts/` | fonts downloaded from Google Fonts | the engine |
| `My References/` | reels and screenshots they like (their files) | you, while setting the style |

Commands (from the AI Video Editor folder): `uv run --project kit kit/run.py style <list|start|show|set|font|palette|preview>`. `kit/run.py style` with no step prints every key you can set.

## 1. Ask once

In one message, plainly:

1. "Do you have 1 to 3 reels or accounts whose look you like? Save the videos or screenshots in the **My References** folder (or tell me the account and describe what you like)." Never download from Instagram, TikTok or YouTube yourself.
2. "Any brand colours or fonts you already use?"
3. "Your @handle for the top of each reel, or none?"
4. "Who are your reels for, and how do you talk to them?" (for `voice.md`)

If they'd rather not bother, offer the three starter looks with their previews (`kit/styles/clean/preview.jpg`, `bold`, `soft`; `style list` describes them) and let them pick. There's a fourth, optional one, `artur`: Artur Rioni's own look (charcoal, orange, serif captions, hand marks, grain), the look of the reels that shared this kit. Offer it when they say they want "the look from the reel", and say plainly whose look it is. Set it with `style start <name>`, add the handle, done.

## 2. Study the references

For each file in `My References/`:

- A video: `uv run --project kit kit/run.py talk sheet "My References/<file>"` gives a sheet of frames; open it. `style palette "<file>"` lists its main colours as hex codes.
- A screenshot: open it, and run `style palette` on it.

Write down, for the set of references together:

- **Colours:** the main background, a second background for contrast scenes, the text colour on each, one accent. Check them against the palette numbers.
- **Type:** the feel of the big words (heavy sans, condensed, rounded, serif, handwritten), all caps or not, and the caption font. Pick the closest Google Font (fonts.google.com names).
- **Captions:** where they sit, size, box or shadow or outline, how many words at a time, caps or sentence case.
- **Movement:** cuts or transitions (slide, zoom, fade, wipe, flash), snappy or smooth arrivals, how busy.
- **Extras:** hand-drawn marks or clean lines, grain, photos in colour or black and white or duotone.
- **Sound effects:** soft whooshes and clicks (`sound=soft`, for clean looks) or paper and pen (`sound=paper`, for hand-drawn looks), or none (`sound=off`).
- **Pace:** calm, normal or fast talking.

Borrow the feel, not the identity: never copy someone's logo, mascot, watermark, exact layout or catchphrases. Mixing two or three references is better than cloning one.

## 3. Write the style

1. `style start <closest starter>` (makes `My Style/` with `style.json`, a `style.md` and a `voice.md` to fill in, and the `My References` folder).
2. Fonts: `style font "<Google font>" --for headline --weight 800`, and again `--for body` if the captions use a different one.
3. Everything else with `style set`, e.g.
   `style set colors.main=#101418 colors.alt=#F2EFE9 colors.text_on_main=#FFFFFF colors.text_on_alt=#101418 colors.accent=#FF3B6B colors.accent_on_alt=#D81E5B`
   `style set captions.style=box captions.case=upper captions.max_words=3 transition=wipe motion=snappy marks=clean photos=bw pace=fast sound=soft signature=@handle name="My style"`
   If you switch to `marks=hand`, set `sound=paper` too, so the sounds match the hand-drawn look.
   Set `accent_on_alt` whenever you change the accent, so it reads on both grounds.
4. `style show` prints the look and warns about colours that are hard to read. Fix every warning.
5. Fill in `My Style/style.md` (the look in one line, each reference and what was borrowed from it, a short do and don't list) and `My Style/voice.md` (audience, tone, words, how reels end). Keep both short and in plain words.

## 4. Show it

`style preview` makes `My Style/preview.jpg` (three frames of a sample reel in the new look; it needs setup to have run once). Open it yourself first and check it matches the references: colours, type weight, caption look. Fix and preview again, then show the user and ask what to change. Two rounds is usually enough.

## Changing it later

"Bigger captions", "less yellow", "use a serif", "slower": change only that key with `style set` (or `style font`), update `style.md` in a line, preview, and say what changed. Existing reels change only when they're built again.
