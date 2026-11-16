# Pictures

Each line of the script gets one picture: a photo that fills the screen, or a drawn scene. All commands run from the AI Video Editor folder (the one with `kit/` in it, not inside `kit/`) as `uv run --project kit kit/run.py pictures ...`.

## Photo or drawn scene

Use a photo when the line names something you can point a camera at: a person doing a thing, a place, an object. Use a drawn scene for numbers, ideas, screens and anything a photo would only hint at. If two searches turn up nothing that shows the line, draw it. A photo that almost fits is worse than a clear drawing.

The picture should show the line, not decorate it. A specific, slightly funny photo beats a generic one: a man asleep on a pile of fish baskets beats "person asleep at a desk".

## Searching

`pictures search <reel> <slot> "airliner cabin"`

- Use 2 or 3 plain words. Long searches find almost nothing. "switchboard operators" works; "telephone switchboard operators 1940s photograph" doesn't.
- Search for the thing in the picture, not the idea: "chef seasoning", "tomato juice", "typist desk", "factory line".
- A thin sheet is normal, because only pictures that are free for anyone to use are kept. Try again with other words for the same thing ("juice glass", "drinking glass"), or a wider word ("kitchen cook").
- Old words find old archive photos: "stewardess", "typewriter", "soda fountain".
- A search takes from half a minute to two minutes, because pictures are downloaded slowly on purpose. Run one at a time. If a message says a site is refusing downloads, wait a few minutes. There is a limit of about 200 searches a day.

Each search replaces the last sheet for that slot.

## Reading the sheet and picking

Open `work/<reel>/assets/candidates/<slot>/sheet.jpg`. Every tile is already cut to phone shape (in black and white, to judge shape and light), numbered left to right, top to bottom. Judge the tile, not the title: a photo that sounds right can fall apart once it's cut tall.

Pick the one where the subject is big, the light and dark are clearly separated, and there's a calm area for words. Skip tiles marked "small, may look soft" unless nothing else works. Skip pictures with their own text, logos or watermarks.

Then read that picture's entry in `candidates.json` (title, author, date, description, source page) and run the checks below before using it.

## Checks before using a photo

A "free to use" label isn't enough. Read who made it, when, and what it shows.

- No recent photos of ordinary people who can be recognised, even when the label says free. Old archive photos, crowds from behind, hands and objects are fine.
- No photos where a child is the main subject.
- No photos with a painful history behind them: camps, disasters, political rallies, weapons, modern military. The title or description usually gives it away.
- War-time settings (a bomber factory, a uniform) aren't banned, but tell the user and let them decide.
- No costumed or staged portraits of a people or culture.
- Look closely at small patterns, badges and signs before choosing. Zoom in if unsure.
- If the author or licence field looks odd or empty for a modern photo, pick another one.

When unsure, show the user the sheet and say what worried you.

## Finishing the pick

`pictures use <reel> <slot> 07`

This writes `work/<reel>/assets/f/<slot>.jpg` at 1080x1920, finished the way their style says (`"photos"`: colour, black and white or duotone). `--color`, `--bw` or `--duotone` overrides it for one picture. Open it and check it before moving on.

- `--focus X,Y` moves the cut. Both numbers run from 0 to 1: across from the left, down from the top. A face on the right third is `--focus 0.7,0.4`. Wide photos nearly always need this.
- `--zoom 1.3` cuts in tighter. Stay under about 1.5 unless the photo is very large, or it turns soft. The command warns when a picture is too small.
- `--gamma 0.8` lifts a dark photo; `--gamma 1.2` deepens a washed-out one.

## The user's own photos

Photos in `My Photos/` work the same way: `pictures use <reel> <slot> "My Photos/desk.jpg"`. They get the style's photo treatment too. Ask the user before using a photo of them.

## Credits

Every `use` saves the picture's title, author, licence and source page to `work/<reel>/credits.json`. `pictures credits <reel>` prints them as plain lines for the credits file that goes next to the finished video. Nothing to write by hand.
