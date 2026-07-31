import sys, pathlib, numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import Run, A, press, RIGHT, LEFT
from play import start_game, arena_fraction
r = Run()
start_game(r)     # the ROM boots to the title; get into the field first
# Long enough that a quiet stretch of the encounter roll cannot fail the test.
# 80 was marginal: booting through the title changed how many frames run before
# the first step, which moved the RNG and turned a pass into a failure.
for i in range(300):
    r.step(press(RIGHT), 8); r.step([0] * 8, 2)
    r.step(press(LEFT), 8); r.step([0] * 8, 2)
    if arena_fraction(r.frame) > 0.6:      # the battle arena
        break
else:
    print("no encounter"); sys.exit(1)
r.shot("bb_0_start")
# mash A: pick FIGHT + first target for all four members, then watch it resolve
for i in range(90):
    r.tap(A, 2, 6)
    if i in (10, 30, 60):
        r.shot(f"bb_{i}")
r.shot("bb_end")
print("frames", r.n)
