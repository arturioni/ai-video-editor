#!/usr/bin/env python3
"""The AI Video Editor's one command. Run it from the AI Video Editor folder:

    uv run --project kit kit/run.py <step> [...]

Setup
  doctor                 check what's installed (changes nothing)
  setup                  install what's missing, then make a 3-second test reel
  count                  how many files the kit has

Your look (My Style/)
  style list | start <look> | show | set key=value | font "<name>" | palette <file> | preview

Make a reel (work/<reel>/)
  new <reel> ["about"]   start a reel folder
  voice <reel>           script.txt -> the voiceover and a time for every word
  voice samples          a short sample of every voice, in kit/voice-samples/
  pictures search <reel> <slot> "<2-3 words>"    public-domain photo candidates on a numbered sheet
  pictures use <reel> <slot> <number|file>       crop and finish one for the reel
  build <reel>           scenes.py -> the animated page
  check <reel>           snapshot every moment that matters, for looking at before rendering
  render <reel>          draw every frame into an MP4 (1 to 3 minutes)
  sound <reel>           voice + sound effects, mixed and levelled
  final <reel>           contact sheet, length and loudness of the finished MP4
  finish <reel>          copy it to "Finished Reels/"
  all <reel>             voice (if missing), build, render, sound, finish

Edit filmed footage
  talk <step> ...        see .claude/skills/edit-talking-head/SKILL.md
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine"))


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return
    step, rest = argv[0], argv[1:]
    if step in ("doctor", "setup"):
        import setup
        return setup.doctor(rest) if step == "doctor" else setup.setup(rest)
    if step in ("new", "build", "render", "finish", "all", "count"):
        import make
        return make.main(argv)
    if step == "voice":
        import voice
        return voice.main(rest)
    if step == "pictures":
        import pictures
        return pictures.main(rest)
    if step in ("check", "final"):
        import check
        return check.main(argv)
    if step == "sound":
        import mix
        return mix.main(rest)
    if step == "style":
        import style
        return style.main(rest)
    if step == "talk":
        import talk
        return talk.main(rest)
    sys.exit(f"Unknown step '{step}'.\n{__doc__}")


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)      # progress lines appear in order, as they happen
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        sys.exit("Stopped.")
