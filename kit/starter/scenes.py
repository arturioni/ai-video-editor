#!/usr/bin/env python3
"""{about}

Build: uv run --project kit kit/run.py build {slug}
This file is what's on screen, line by line. The engine does the timing. The worked example is
kit/examples/airplane-food/scenes.py; the pieces you can use are in .claude/skills/make-reel/references/scenes.md.
"""
from beats import *

# One entry per spoken line: (key, its exact words, "cut" or "move"). Together they must equal script.txt.
# "move" lines come in with your style's transition; use them where the topic shifts, 2 to 4 in a short reel.
LINES = [
    ("hook", "First line of script.txt.", "cut"),
    ("end", "Last line of script.txt.", "move"),
]

begin(__file__, LINES)
TOTAL = total()

t0, t1 = T["hook"], T["end"]
s = stack("hook", [("HOOK", 236, 700, None, None)])
caps("hook")
scene("hook", t0, t1, "main", s)

t0, t1 = T["end"], TOTAL
s = stack("end", [("END", 236, 700, None, None)])
caps("end")
scene("end", t0, t1, "alt", s)

finish()
