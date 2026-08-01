import sys, pathlib, numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import Run, press, UP, A
r = Run(); r.idle(20); r.shot("tw_0_overworld")
d0 = r.digest()
r.step(press(UP), 60)          # two cells up onto the LANDFALL town tile
r.idle(20)
r.shot("tw_1_town")
print("map changed:", d0 != r.digest())
r.tap(A, 3, 40)                # talk to whatever is in front
r.shot("tw_2_talk")
print("frames", r.n)
