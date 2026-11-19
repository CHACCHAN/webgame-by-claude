"""The F-15J / DJ (tools/blender-models.cjs jets f15j): see f15.py."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f15  # noqa: E402

f15.main("f15j")
