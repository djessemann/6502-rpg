import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import Run, A, B, RIGHT, LEFT, UP, DOWN, press
r = Run()
r.idle(20); r.shot("b0_field")
# walk until an encounter starts (the field is quiet, battle repaints black)
for i in range(60):
    r.step(press(RIGHT), 10)
    r.step(press(LEFT), 10)
    f = r.frame
    import numpy as np
    if np.asarray(f)[8:120, :, :].sum() < 200000:
        break
r.shot("b1_battle")
print("frames", r.n)
