"""
Pytest configuration for Verification Tests suite.
Author: Nguyen Nguyen Gia Bao (Builder 3)
"""

import sys
from pathlib import Path

# Add repository root and v1.0-alpha-plan directories to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
PLAN_ROOT = REPO_ROOT / "v1.0-alpha-plan"
for _p in (str(REPO_ROOT), str(PLAN_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

