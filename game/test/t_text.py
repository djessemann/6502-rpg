import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import Run, A, RIGHT, DOWN, UP, press
r = Run()
r.idle(20); r.shot("t0_field")
r.tap(A, 3, 30); r.shot("t1_box")
r.idle(20); r.shot("t2_text")
r.tap(A, 3, 20); r.shot("t3_after_a")
r.tap(A, 3, 40); r.shot("t4_closed")
print("ok", r.n)
