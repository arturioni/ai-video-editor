# Writing scenes.py

`scenes.py` says what's on screen for each line. The engine handles timing: it knows when every word is spoken, cuts each scene on its line's first word, plays the style's transitions, and writes the HyperFrames page. The look (colours, fonts, captions, motion) comes from `My Style/style.json`, so the same scene code works in any style. You only describe scenes.

Build after every change: `uv run --project kit kit/run.py build <reel>`. Error messages say what to fix.

## The skeleton

```python
from beats import *

LINES = [                                    # (key, exact words, "cut" or "move"); together = script.txt
    ("hook", "It's not the food. It's the plane.", "cut"),
    ("dry", "At cruising height, the cabin air is drier than most deserts.", "move"),
    ("end", "Follow for more things nobody tells you.", "cut"),
]
begin(__file__, LINES)                       # optional: beat_after="turn" keeps a longer pause after that line
TOTAL = total()                              # reel length; total(at_least=x) to hold the last scene longer

# one block per line: its scene runs from T[key] to the next line's T (or TOTAL)
t0, t1 = T["hook"], T["dry"]
s = stack("hook", [("THE FOOD", fit("THE FOOD"), 640, None, None),
                   ("THE PLANE", fit("THE PLANE"), 900, "plane.", ACCENT)])
s += strike(110, 770, 970, 730, end_of("hook", "food."))
caps("hook")
scene("hook", t0, t1, "main", s)

t0, t1 = T["dry"], T["end"]                  # a "move" line: it comes in with the style's transition
s = photo("p1", "desert", t0, t1) + grad("bottom", 760, 0.85)
s += stamp("DRIER", 520, fit("DRIER"), start_of("dry", "drier"))
s += note("than most deserts", 780, start_of("dry", "deserts."))
caps("dry")
scene("dry", t0, t1, "photo", s)

t0, t1 = T["end"], TOTAL
s = stamp_words("end", [("Follow", 200, 640, True)])
s += doodle("heart", 540, 1080, 200, t0 + 0.2, color=ACCENT)
caps("end")
scene("end", t0, t1, "alt", s)

finish()
```

Rules the build checks: `LINES` words equal `script.txt`; every caption matches its line's words in order; pictures exist.

## Time

- `T[key]`: when that line's scene starts (its cut). A scene ends at the next line's `T`, or `TOTAL` for the last.
- `start_of(key, word)` / `end_of(key, word)`: when a word in that line is spoken. Add `nth=1` for its second use. Words are matched without punctuation or case.
- `line_start(key)`, `line_end(key)`: first and last word of a line.
- A `"move"` line's scene comes in with the style's transition (slide, zoom, fade, wipe or flash), which takes about 0.3 s: start its first piece on the cut or just after.

## Grounds (the 4th argument of `scene`)

`"main"` the style's main background, `"alt"` its second background (for contrast scenes), `"photo"` under a full-frame photo.

Colours follow the ground by themselves: `FG` is the text colour of the scene's ground and `ACCENT` the style's accent for that ground. Every piece uses them by default, so leave `color` out, and pass `color=ACCENT` (or the colour slot in `stack` rows) only for the accent. Fonts, caption look, motion and marks also come from the style.

## Captions

`caps(key)` puts the line on screen a short phrase at a time, each on its first spoken word, in the style's caption look. To choose the phrases yourself: `caps(key, ["At cruising height,", "the cabin air", "is drier than most deserts."])` (they must cover the whole line, in order). Every line gets captions.

## Ready-made pieces (from beats.py; each returns HTML to add to `s`)

| Piece | What it does |
|---|---|
| `stack(key, [(text, size, top, word or None, colour or None), ...])` | Rows of big words in the headline font, each arriving on its word (None = on the cut) |
| `stamp(text, top, size, at)` | One row of big words arriving at a time |
| `fit(text, most=None)` | The biggest size that keeps `text` on one row. Use it for sizes |
| `count(key, ["100%", "90%", "80%", "70%"], "-33%", "third", top=700, final_color=ACCENT)` | Numbers flick from the cut, the final one arrives on its word |
| `takeover(key, [(text, size, top, word or None), ...])` | The accent colour fills the frame, words arrive on it. Once per reel, on the turn |
| `strike(x1, y1, x2, y2, at)` | A pen line struck through something |
| `circle(cx, cy, rx, ry, at)` | A drawn ring around something |
| `underline(x1, x2, y, at)` | A pen underline |
| `pen_arrow([(x, y), (x, y), (x, y)], at)` | A curved arrow, head at the last point |
| `tick(x, y, at)` | A tick mark |
| `rays(cx, cy, r0, r1, at)` | Burst lines: something just happened here |
| `doodle(name, cx, cy, size, at)` | A drawn icon: sun, cloud, plane, shaker, glass, nose, smell, ear, waves, clock, bulb, heart, drop, phone, x, star |
| `label(text, top, at)` | Small spaced capitals ("STEP 2 OF 5") |
| `note(text, top, at)` | A quieter line in the body font, next to big words |
| `typed(key, "exact words from the line", top=330, marks=("word",))` | A sentence typed letter by letter as it's spoken, marked words underlined |
| `stamp_words(key, [(word, size, top, accent?), ...])` | Words of the call to action arriving as they're spoken |
| `photo(id, slot, t0, t1)` | The picture `assets/f/<slot>.jpg`, full frame with a slow push-in |
| `grad("bottom" or "top", height, strength)` | A dark fade so captions or words stay readable on a photo |

Marks are hand-drawn or clean lines depending on the style's `marks`; words stamp or rise softly depending on its `motion`.

Lower level, from the engine: `big(html, top, size, color)`, `land("#id", at)`, `show("#id", at, until)`, `Sk().add(points, width, colour).play(t0, t1)` for any pen drawing (`ellipse(cx, cy, rx, ry)` and `catmull(points)` make point lists), `bubble(...)`, `burst(...)`, `sound(label, t)` and `moment(t, what)`. Any HTML with absolute positioning works inside a scene, and `ft("#id", from, to, at)` animates it with GSAP.

## What a good scene has

- **One idea in big words**, the word or number the line turns on ("DRIER", "-33%", "IS SMELL"). Never the whole caption again in big type: the caption already says it.
- **A drawing or a photo**, not words alone. A drawn scene gets a doodle or marks that show the idea (a nose and scent lines for "flavor is smell", a salt shaker with rays for "extra salt").
- **Things arriving on their words**, about one new thing every half second, the first one on the cut so no scene opens empty.

The worked example `kit/examples/airplane-food/scenes.py` does all three; copy its patterns.

## Layout cheats

- The safe area for anything important is y=240 to y=1560. Captions sit at 1455, so big words belong between about 450 and 1300. Centre a scene's main block around y=850, not at the top.
- Heavy rows: `top` is the top edge of the row; leave about `size` pixels plus 20 between rows. Use `fit()` so rows never run off the sides.
- Centre of the frame is x=540. A doodle's `size` is its width in pixels; 200 to 340 reads well.
- On a photo, put words where the photo is calm (sky, wall, table) and add `grad()` under captions.
- Space things out in time too: one new thing every half second or so, each on a word.

## Sound

Transitions, arrivals (`stamp`, `stack`, `count`, `stamp_words`), strikes, circles, doodles, the takeover and typing add their own light sounds; plain cuts get a very light one. Add more with `sound("land", t)`; labels: land, hit, scribble, key, whoosh, cut. The style's `"sound"` picks the set: `soft` (whooshes and clicks), `paper` (paper and pen, for hand-drawn looks) or `off` (none).

## When the build says

- "LINES and script.txt don't match": a word differs (often punctuation-only words or a changed line). Make them identical.
- "Line 'x' doesn't match the voice": the script changed after the voice was made. Run `voice` again.
- "'word' isn't in line 'x'": `start_of` names a word that line doesn't contain; it lists the words it has.
- `check:` lines: rule warnings (long captions, short scenes, more than one takeover). Fix them unless you have a reason.
