# Checking your own work

"It checks its own motion before you see it." You can't watch the video, but you can look at frames, and the frames that matter are known: every cut, every caption, every mark landing, every tear. `check` snapshots exactly those.

```
uv run --project kit kit/run.py check <reel>                 lint + every moment that matters, on labelled sheets
uv run --project kit kit/run.py check <reel> --at 3.2,7.5    just those times, after a fix
uv run --project kit kit/run.py final <reel>                 after rendering: one frame a second from the MP4
```

`check` prints the sheets (`work/<reel>/renders/check/sheet-1.jpg`, ...) and a list of what each time shows (also saved as `moments.txt`). Each tile is labelled with its time. Open every sheet with your image-reading tool and go through the list below, scene by scene.

## Look for

1. **Readable in half a second.** Big words big enough, strong contrast against the ground. If a colour is hard to read in every reel, fix it in the style (`style show` warns), not in one scene.
2. **Nothing clipped or crowded.** No words running off the sides or into each other; rows with clear space between them. Use `fit()` for sizes.
3. **Inside the safe area.** Important words and marks between y=240 and y=1560 (in a tile, roughly the middle 70%). Nothing important at the very top or bottom.
4. **Captions.** One or two lines, never three; not sitting on top of big words, a face, or the bright part of a photo (add `grad()`); in the style's caption look.
5. **The picture shows the line.** Read the line next to its frame. If someone with the sound off wouldn't get it, change the picture or draw it.
6. **Marks land on their target.** Circles around the thing, strikes through the word, arrows pointing at something. Adjust coordinates if they miss.
7. **No empty frames.** The first clean frame of each scene has something on it (a stamped word may still be landing at +0.1 s; that's fine). A scene that sits empty for over a second needs something earlier.
8. **Words get time to be read.** In "last frame before the cut" tiles, the scene's big words should already be there; if they arrive too late to read, move them earlier.
9. **One big moment.** At most one takeover (the accent filling the frame), on the turn.
10. **Ending.** The last scene holds long enough to read the call to action.

A "transition in progress" tile may show the new scene sliding, zooming or fading in: that's correct, not a bug.

11. **It looks like their style.** Compare one sheet with `My Style/style.md` and its references: colours, type, caption look, amount of movement.

## Fixing

Fix in `scenes.py`, build, then re-check only the times you changed with `--at`. Two rounds at most; after that, note anything left when you hand the reel over.

## After rendering

`final` writes `final-sheet.jpg` (one frame a second, labelled) and prints the length, size and loudness. Confirm:

- 1080x1920, the length you expected, and "sound" (not "NO SOUND") after the sound step.
- Loudness about -14 LUFS (that's normal for phones) and peak around -1.5 dBTP or lower.
- The frames match what you checked before rendering (a render can differ if a font or picture failed to load: look for missing pictures or plain fonts).

You can't hear the audio. Say so when you deliver, and let the user judge the voice and the sound.
