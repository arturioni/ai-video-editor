# The voice

## Default: a free voice made on this computer

`uv run --project kit kit/run.py voice <reel>` reads `script.txt` with the voice in `settings.json` (Kokoro, a small voice model that runs on this computer: free, no account, nothing uploaded). Each sentence is spoken separately so pauses land between sentences, then a speech-to-text model times every word against the script.

Voices (samples to click in `kit/voice-samples/`):

| Voice | Sounds like |
|---|---|
| am_michael | American man (default) |
| am_adam | American man, deeper |
| af_heart | American woman, warm |
| af_nova | American woman, bright |
| af_sky | American woman, light |
| bm_george | British man |
| bf_emma | British woman |
| bf_isabella | British woman, softer |

Change it for every reel in `settings.json` (`"voice"`), or for one run with `--voice af_heart`. The speed follows the style's `pace` (calm, normal, fast); `"voice_speed"` in `settings.json` (e.g. 1.15) or `--speed 1.15` overrides it. The build prints the reel's real pace: about 3.0 to 3.6 words a second reads well.

**Mispronounced words:** add respellings to `work/<reel>/say.json`, e.g. `{"Kokoro": "ko-ko-ro", "GIF": "jiff"}`. The voice reads the respelling, the captions keep the script's spelling. Then run `voice` again.

## The user's own voice

A real voice often performs better than any generated one. To use it:

1. Ask them to record themselves reading `script.txt` word for word, in a quiet room, phone close to the mouth (Voice Memos is fine). Pauses between sentences are fine; the engine trims them.
2. Save the file in `work/<reel>/assets/voice/` named `take` with its own extension: `take.m4a`, `take.mp3`, `take.wav`, or even `take.mov` / `take.mp4` from a video.
3. Run `voice <reel>`. It uses the recording instead of the generated voice, times every word, and speeds it up slightly (8%, set by `"own_voice_tempo"` in settings; 1.0 keeps it as recorded).

If they changed words while reading, either edit `script.txt` to what they said, or ask them to read it again. The voice step warns when the recording and script don't match.

To go back to the generated voice, move the `take` file out of that folder.

## Other voice tools

Any voice made elsewhere (ElevenLabs, another app) works the same way as the user's own recording: export it as audio, save it as `work/<reel>/assets/voice/take.mp3`, run `voice`. Don't ask for or handle the user's API keys in chat.
