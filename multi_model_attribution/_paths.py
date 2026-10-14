"""Make the existing study packages importable from this folder.

The authorship study keeps its library code under scripts/ (elicitation, vignette_gen) and
analysis/ (wcb). Import this module first in every script and test here.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for sub in ("scripts", "analysis"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)
