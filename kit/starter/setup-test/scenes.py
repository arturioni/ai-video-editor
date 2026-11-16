#!/usr/bin/env python3
"""The 3-second test reel setup makes: proves voice, timing, drawing, rendering and sound work together.
It's drawn in your style (or the neutral starter look until you set yours up)."""
from beats import *

LINES = [
    ("ready", "Your setup is ready.", "cut"),
    ("go", "Let's make a reel.", "move"),
]
begin(__file__, LINES)
TOTAL = total()

t0, t1 = T["ready"], T["go"]
s = stack("ready", [("SETUP", fit("SETUP", 150), 660, "Your", None), ("READY", fit("READY"), 830, "ready.", ACCENT)])
s += tick(700, 1180, start_of("ready", "ready.") + 0.1)
caps("ready")
scene("ready", t0, t1, "main", s)

t0, t1 = T["go"], TOTAL
s = stack("go", [("LET'S GO", fit("LET'S GO"), 700, None, None)])
s += doodle("star", 540, 1080, 200, t0 + 0.1, color=ACCENT)
caps("go")
scene("go", t0, t1, "alt", s)

finish()
