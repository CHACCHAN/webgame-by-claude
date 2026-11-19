"""The F-15C / D (tools/blender-models.cjs jets f15c): see f15.py."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f15  # noqa: E402

f15.main('f15c')
