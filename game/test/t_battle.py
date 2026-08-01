import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import Run, A, B, RIGHT, LEFT, UP, DOWN, press
r = Run()
from play import start_game, arena_fraction
start_game(r)     # the ROM boots to the title; get into the field first
r.idle(20); r.shot("b0_field")
# walk until an encounter starts (the field is quiet, battle repaints black)
for i in range(60):
    r.step(press(RIGHT), 10)
    r.step(press(LEFT), 10)
    if arena_fraction(r.frame) > 0.6:      # the battle arena
        break
r.shot("b1_battle")
print("frames", r.n)
