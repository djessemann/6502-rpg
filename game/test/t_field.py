import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import Run, RIGHT, LEFT, UP, DOWN, press
r = Run()
from play import start_game
start_game(r)     # the ROM boots to the title; get into the field first
r.idle(20); r.shot("field_00_start")
r.step(press(DOWN), 90); r.shot("field_01_down")
r.step(press(RIGHT), 90); r.shot("field_02_right")
r.step(press(UP), 120); r.shot("field_03_up")
r.step(press(LEFT), 120); r.shot("field_04_left")
print("frames", r.n, "nonblack", r.nonblack())
