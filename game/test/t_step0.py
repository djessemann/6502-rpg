import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import Run
r = Run()
r.idle(40)
print("nonblack px:", r.nonblack(), "digest:", r.digest())
print("shot:", r.shot("step0"))
