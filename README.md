# AI Video Editor

Type one line, get a finished reel.

> make a reel about why airplane food tastes so bland

Claude writes the script in your voice, records the voiceover, animates every scene in your own style, times the captions to every word, checks its own frames before you see it, and renders a vertical video ready for Instagram, TikTok or Shorts. If something feels off, tell it like you'd tell an editor, and it fixes it.

The look is yours: show it a few reels you like (or pick a starter look) and it builds your colours, fonts, captions and pace from them.

Free to use. No accounts or keys. The voice is made on your computer, and nothing is uploaded.

## What you need

- The Claude desktop app with Claude Code (a paid Claude plan).
- A Mac (Windows should work but is less tested).
- About 2 GB of free space and an internet connection for the first setup.

## Set it up (once)

1. Make a folder on your computer called **AI Video Editor**.
2. Open the Claude desktop app, go to **Code**, start a new chat, choose **Local**, and select that folder.
3. Paste this and press Enter:

```
Set up the AI Video Editor in this folder: download https://github.com/arturioni/ai-video-editor/archive/refs/heads/main.zip, unzip it, move everything inside the ai-video-editor-main folder (hidden files too) into this folder, delete the zip and the empty folder, then read .claude/skills/check-setup/SKILL.md and follow it to check my setup.
```

Claude downloads the kit, then checks your setup and installs what's missing: the video renderer, ffmpeg, a voice and a speech model. The first time takes 5 to 15 minutes. It asks which voice you like (click the samples in `kit/voice-samples/` to hear them) and finishes by making a 3-second test reel.

## Set up your look (once)

Save 1 to 3 reels or screenshots whose look you like in **My References**, then say `set up my style`. Claude studies them and builds **My Style**: your colours, fonts (any Google font), caption look, transitions, pace and the @handle at the top, plus how your scripts should sound (who they're for, how you talk, how you end). It shows you a preview and changes whatever you say.

No references? Pick a starter look instead (previews in `kit/styles/`): **Clean** (white, calm, blue accent), **Bold** (black, huge capitals, yellow) or **Soft** (pale blue, hand-drawn marks, gentle fades). Change it any time: `use my brand colours`, `bigger captions`, `use a serif font`.

## Make a reel

Start a new chat in the same folder any time and type what the reel is about in one line:

- `make a reel about why airplane food tastes so bland`
- `make a reel about the 3 apps I use every morning, end with comment APPS`
- `make a reel with this script: ...`

Your finished reels land in **Finished Reels**. Add a song in Instagram or TikTok when you post.

To see what you'll get first, watch `kit/examples/airplane-food/airplane-food.mp4`: the airplane-food reel, made by the kit in the Clean starter look.

Other things you can say:

| Say | What happens |
|---|---|
| `check my setup` | Checks everything and fixes what's missing |
| `set up my style` / `make it look like these reels` / `change my colours` | Builds or changes your look |
| `the hook is weak, try another` / `use a different picture for the second scene` / `make it shorter` | Changes just that and makes a new version (old versions stay) |
| `remake this reel: <paste the words of a viral reel>` | Breaks down why it worked and writes your version on the same structure |
| `edit this video` (with a video of you talking in **My Footage**) | Keeps your best takes, cuts the pauses, adds captions and levels the sound |

## Your own voice and photos

- **Your voice:** record yourself reading the reel's script (Voice Memos is fine) and tell Claude "use my recording". It replaces the generated voice and keeps the timing.
- **Your photos:** drop them in **My Photos** and say which scene they're for. Otherwise Claude finds free-to-use (public domain) photos, finishes them in your style (colour, black and white or duotone) and lists their credits next to each finished reel.

## The folder

| Folder | What's in it |
|---|---|
| Finished Reels | Your finished videos |
| My Style | Your look and voice (Claude fills it in) |
| My References | Reels and screenshots you like, for your style and for remakes |
| My Photos, My Footage | Your own pictures and videos for Claude to use |
| work | One folder per reel: the script, scenes, voice and renders (Claude keeps notes here) |
| kit | The engine, the starter looks and a worked example. You don't need to open it |
| settings.json | Your voice |

## If something breaks

Type `check my setup`. It finds the problem and fixes it, or tells you in plain words what to do.

## What gets downloaded

On the first setup: `uv` (runs the kit's own Python), the HyperFrames renderer and a headless Chrome, a voice model (Kokoro, about 340 MB), a speech-to-text model (faster-whisper, about 145 MB), and Node.js and ffmpeg if your computer doesn't have them. They live in this folder or in the usual download caches in your home folder. Pictures come from Openverse and Wikimedia Commons, public domain and CC0 only.

## Install as a Claude Code plugin instead

If you'd rather have the skills in every folder: `/plugin marketplace add arturioni/ai-video-editor`, then `/plugin install ai-video-editor@ai-video-editor`. Then open an empty folder and say `check my setup`; it copies the engine into that folder. Use one way or the other, not both.

## Credits

Built on [HyperFrames](https://github.com/heygen-com/hyperframes) (HTML to video), [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M) (voice) and [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (word timing). Sound effects from Freesound (CC0), Inter under the SIL Open Font License: see `CREDITS.md`. MIT licence (`LICENSE`).
