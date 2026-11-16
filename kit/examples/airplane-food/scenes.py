#!/usr/bin/env python3
"""Why airplane food tastes so bland: the kit's worked example (about 28 seconds).

Build: uv run --project kit kit/run.py build airplane-food
Ten lines, ten scenes: three photos, six drawn scenes, one takeover. Big words carry the one idea of each line
(never the whole caption again), and each drawn scene gets a drawing, not only words. No colours or fonts are
written here: they all come from My Style, so this same file works in any look.
"""
from beats import *

LINES = [
    ("hook", "It's not the food. It's the plane.", "cut"),
    ("dry", "At cruising height, the cabin air is drier than most deserts.", "move"),
    ("nose", "Your nose dries out, and most flavor is really smell.", "cut"),
    ("pressure", "The low pressure weakens your taste buds too.", "cut"),
    ("third", "Salt and sugar taste about a third weaker.", "cut"),
    ("salt", "So airlines add extra salt and spice to make up for it.", "move"),
    ("turn", "But here's the weird part.", "cut"),
    ("noise", "The engine noise dulls sweet, but it boosts savory.", "cut"),
    ("tomato", "That's one reason people crave tomato juice on planes.", "move"),
    ("end", "Save this for your next flight.", "cut"),
]

begin(__file__, LINES, beat_after="turn")
TOTAL = total(at_least=line_end("end") + 1.4)

# 1. hook: THE FOOD is struck out on "food.", THE PLANE arrives in the accent colour, a little plane under it
t0, t1 = T["hook"], T["dry"]
s = label("IT'S NOT", 560, t0 + 0.04)
s += stack("hook", [("THE FOOD", fit("THE FOOD"), 630, None, None),
                    ("THE PLANE", fit("THE PLANE"), 900, "plane.", ACCENT)])
s += strike(110, 770, 970, 730, end_of("hook", "food.") - 0.05)
s += doodle("plane", 540, 1180, 240, start_of("hook", "plane.") + 0.12)
caps("hook")
scene("hook", t0, t1, "main", s)

# 2. dry: a desert comes in; DRIER arrives on its word
t0, t1 = T["dry"], T["nose"]
end = t0 + 0.3                    # the style's transition takes about 0.3 s
s = photo("p1", "desert", t0, t1) + grad("bottom", 760, 0.85)
s += label("CABIN AIR", 470, max(end, start_of("dry", "cabin")))
s += stamp("DRIER", 530, fit("DRIER"), start_of("dry", "drier"))
s += note("than most deserts", 790, start_of("dry", "deserts."))
s += doodle("sun", 820, 330, 150, end + 0.1, color=ACCENT)
caps("dry")
scene("dry", t0, t1, "photo", s)

# 3. nose: a drawn nose, scent lines beside it, FLAVOR IS SMELL
t0, t1 = T["nose"], T["pressure"]
s = doodle("nose", 430, 820, 340, t0 + 0.05)
s += doodle("smell", 690, 780, 220, start_of("nose", "flavor"), color=ACCENT)
s += stack("nose", [("FLAVOR", fit("FLAVOR", 200), 440, "flavor", None),
                    ("IS SMELL", fit("IS SMELL"), 1060, "smell.", ACCENT)])
caps("nose")
scene("nose", t0, t1, "alt", s)

# 4. pressure: the wing above the clouds, LOW PRESSURE with a pen arrow pushing down
t0, t1 = T["pressure"], T["third"]
s = photo("p2", "cabin", t0, t1) + grad("top", 900, 0.8) + grad("bottom", 700, 0.75)
s += stack("pressure", [("LOW", 236, 420, "low", None),
                        ("PRESSURE", fit("PRESSURE"), 660, "pressure", None)])
s += pen_arrow([(890, 430), (945, 520), (915, 615)], start_of("pressure", "weakens"), color=ACCENT)
caps("pressure")
scene("pressure", t0, t1, "photo", s)

# 5. third: SALT + SUGAR, the number falls to -33% on "third"
t0, t1 = T["third"], T["salt"]
s = label("SALT + SUGAR", 540, t0 + 0.04)
s += count("third", ["100%", "90%", "80%", "70%"], "-33%", "third", top=640, final_color=ACCENT)
s += note("weaker", 920, start_of("third", "weaker."))
s += doodle("shaker", 540, 1180, 170, t0 + 0.1)
caps("third")
scene("third", t0, t1, "alt", s)

# 6. salt: a big salt shaker comes in, + SALT + SPICE arrive on their words
t0, t1 = T["salt"], T["turn"]
end = t0 + 0.3
s = doodle("shaker", 540, 700, 300, end - 0.2)
s += rays(540, 700, 190, 260, start_of("salt", "extra"), 14)
s += stack("salt", [("+ SALT", fit("+ SALT", 190), 930, "salt", None),
                    ("+ SPICE", fit("+ SPICE", 190), 1130, "spice", ACCENT)])
caps("salt")
scene("salt", t0, t1, "main", s)

# 7. turn: the reel's one takeover
t0, t1 = T["turn"], T["noise"]
s = takeover("turn", [("WEIRD", fit("WEIRD"), 660, "weird"), ("PART", 236, 900, "part.")])
caps("turn")
scene("turn", t0, t1, "main", s)

# 8. noise: an ear and engine sound waves, SWEET struck out, SAVORY arrives in the accent colour
t0, t1 = T["noise"], T["tomato"]
s = doodle("waves", 400, 600, 260, t0 + 0.05)
s += doodle("ear", 690, 600, 200, t0 + 0.2)
s += stack("noise", [("SWEET", fit("SWEET", 200), 820, "sweet,", None),
                     ("SAVORY", fit("SAVORY"), 1050, "savory.", ACCENT)])
s += strike(200, 930, 880, 900, end_of("noise", "sweet,"))
caps("noise")
scene("noise", t0, t1, "alt", s)

# 9. tomato: a glass of tomato juice comes in; TOMATO JUICE arrives and gets underlined
t0, t1 = T["tomato"], T["end"]
end = t0 + 0.3
s = photo("p3", "tomato", t0, t1) + grad("bottom", 760, 0.85)
s += stamp("TOMATO JUICE", 1100, fit("TOMATO JUICE"), max(end, start_of("tomato", "tomato")))
s += underline(140, 940, 1300, start_of("tomato", "juice"))
caps("tomato", ["That's one reason", "people crave", "tomato juice on planes."])
scene("tomato", t0, t1, "photo", s)

# 10. end: SAVE THIS arrives as it's said, with a drawn plane
t0, t1 = T["end"], TOTAL
s = stamp_words("end", [("Save", fit("Save"), 560, True), ("this", 150, 820, False)])
s += doodle("plane", 540, 1150, 300, t0 + 0.25)
caps("end")
scene("end", t0, t1, "alt", s)

finish()
