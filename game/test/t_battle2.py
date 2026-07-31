import sys, pathlib, numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import Run, A, press
r = Run(); r.idle(20)
from harness import RIGHT, LEFT
for i in range(80):
    r.step(press(RIGHT), 10); r.step(press(LEFT), 10)
    if np.asarray(r.frame)[8:120, :, :].sum() < 200000:
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
