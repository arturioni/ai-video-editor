---
name: edit-talking-head
description: Edit a raw talking-to-camera recording into a finished 9:16 reel - keeps the best take of each line, cuts pauses and filler, adds clean word-timed captions and a few text cards, levels the sound. Use when the user gives a video file of themselves talking (or drops one in My Footage/) and says "edit this", "cut this", "tighten", "add captions", even if they don't name the skill.
---

# Edit a talking-head video

The goal: the reel should feel like the person filmed it on their phone and a sharp human editor cut it. Easy and natural on the surface, well edited underneath. It must never look like an ad or a template. Read `style.md` next to this file before you choose any words or placement for the screen. Its rules beat every default below.

Everything runs on this computer. Run every command from the kit's main folder (the one with `kit/` and `My Footage/` in it):

```
uv run --project kit kit/run.py talk <step> <video> [options]
```

`<video>` is a path, or just the file name of a video in `My Footage/`. Each step writes a new file into `work/<name>/` and prints the next command to run. The original recording is never changed. Two things download themselves the first time and work offline after that: the speech model (about 480 MB) and the small browser that draws the captions. Tell the user if a first run is slow for that reason.

## Before starting, ask once

One message, all three questions together:

1. What the video is about and who it's for, in one line (skip this if the file name makes it obvious).
2. Is there a word people should comment to get something? If yes, it goes on a closing card.
3. Keep it at its natural length, or aim for a length?

Then don't ask anything else. Go straight through to a finished reel and show that.

## Steps

1. **Look at the file.** `talk probe <video>` tells you the length, size, frame rate, rotation and whether it has sound.

2. **Get the words.** `talk transcribe <video>` writes `work/<name>/transcript.txt` (each line with its start and end time, pauses marked, repeated lines flagged "said again") and `transcript.json` (every word with its time). If names or unusual words come out wrong, run it again with `--model medium.en`. On a slow computer `--model base.en` is quicker.

3. **Pick the takes.** Read `transcript.txt`. People repeat a line until they like it, so:
   - Where a line is said more than once, keep the **last complete, confident take** and drop the earlier ones.
   - Drop false starts, lines abandoned halfway, and asides like "wait, let me do that again".
   - Drop filler words on their own ("um", "so, yeah") when they sit between two lines. For a filler inside a line, look up the word times in `transcript.json` and end one range before it and start the next after it.
   - If the user asked for a length, also drop the weakest lines until it fits. Never drop the hook or the ending.

   Write what you keep to `work/<name>/keep.txt`, one `START-END` per line in seconds, in the order it should play. A `#` starts a note:

   ```
   7.44-12.44    # hook, second take
   13.94-21.40   # the how-to and the ending
   ```

   Use the line times from the transcript as they are. The cut step moves each edge to the nearest quiet moment by itself, so words don't get clipped.

4. **Cut.** `talk cut <video>` reads `keep.txt` and writes `01-cut.mp4`.

5. **Tighten.** `talk tighten work/<name>/01-cut.mp4` shortens every pause to a quarter of a second, which keeps the breaths so it doesn't sound machine-cut. Writes `02-tight.mp4`. If it says it found no pauses but there clearly are some, the room is noisy: add `--threshold -30`. If it clips the ends of words, add `--threshold -45`. For a calmer pace use `--max-gap 0.4`.

6. **Fit to 9:16.** `talk fit work/<name>/02-tight.mp4` writes `03-fit.mp4` at 1080x1920, 30 frames a second. An upright video is cropped around the centre. A sideways video keeps its whole picture on a blurred copy of itself; to fill the frame instead use `--mode crop --x 0.5`, moving `--x` toward 0 (left) or 1 (right) until the person is in the middle.

7. **Captions.** `talk captions work/<name>/03-fit.mp4` listens to the tightened cut again (so the timing is right), writes the words to `work/<name>/captions.json`, and burns them in as `04-captions.mp4`. Read `captions.json`. If a word was misheard, or a caption breaks in an awkward place, fix the text there (you can also merge or split entries, keeping the times in order). Options: `--words-per 3` (words on screen at once), `--y 1340` (how far down, see step 10), `--size 44`.

8. **Text cards (optional, three at most).** See "Text cards" below. If the reel should have any, write `work/<name>/cards.txt`, taking the times from `captions.json`. Then, if you wrote cards or fixed any caption, burn again without listening again: `talk captions work/<name>/03-fit.mp4 --use captions.json`. It picks up `cards.txt` by itself.

9. **Level the sound.** `talk level work/<name>/04-captions.mp4` writes `05-level.mp4` and prints the loudness it reached. It should say about -14 LUFS with the peak at or under -1.5.

10. **Look at it.** `talk sheet work/<name>/05-level.mp4 --safe` writes one picture a second with the time on each, and red lines where Instagram puts its own caption (bottom) and buttons (right). Open every sheet and check:
    - No caption or card sits on the person's face, or below the bottom red line, or under the buttons on the right.
    - The person is in frame the whole way through.
    - No picture shows a leftover retake or a strange jump.

    For one moment at full size: `talk sheet <video> --at 12.5`.

11. **Fix what you saw**, then run the later steps again:
    - Caption on the face or too low: `talk captions work/<name>/03-fit.mp4 --use captions.json` with a different `--y` (1340 is the lower third; a smaller number moves it up; keep it under 1500).
    - Card on the face: change its place in `cards.txt`, then the same command.
    - Person off-centre: step 6 again with `--mode crop --x ...`, then steps 7 to 10 (step 7 with `--use captions.json`).
    - A bad take or a clipped word: change `keep.txt`, then steps 4 to 10.

12. **Finish.** `talk finish work/<name>/05-level.mp4` copies it to `Finished Reels/<name>.mp4`.

Then show the user: where the finished file is, how long it is, what you cut (in a line or two), and the words on any cards. Ask what they'd like changed. Apply their notes from the step they touch, and finish again. The working files stay in `work/<name>/` until they're happy.

## Text cards

Cards are the few big lines of text that make an edit feel made by a person. Captions are not cards; they run the whole way through.

- Three at most. For a reel under 20 seconds, one or two. None is fine.
- The first is the hook: on screen in the first second and a half, built from the line that makes someone stay.
- After that, only at a moment that earns it: a number, a named step, a strong claim, a contrast.
- Six words or fewer. Sentence case. The words must be the person's own from the transcript, or a shortening they would say. Never invent a claim.
- If there's a comment word, the last card is `Comment WORD` (only the word in capitals), shown when they say it or over the last two to three seconds.
- Keep cards off the face, and vary where they sit.

`cards.txt` has one card per line: when, the words, where, and optionally the letter size:

```
0-2.2    | Stop editing by hand | top
9.1-11.3 | Comment EDIT         | 520 | 76
```

The place is `top`, `middle`, `bottom`, or a number of pixels from the top of the 1920-tall frame. Times are from the tightened cut, so read them from `captions.json`. Cards fade in and out by themselves. To leave them out for one run, add `--no-cards`.

## Things to never do

- Change, move or delete the original recording.
- Add music, sound effects, zooms, emoji or a logo unless the user asks.
- Put words on screen the person didn't say.
- Show the user half-finished steps. They see the finished reel first.
