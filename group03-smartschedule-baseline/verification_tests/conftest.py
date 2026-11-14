"""
Pytest configuration for Verification Tests suite.
Author: Nguyen Nguyen Gia Bao (Builder 3)
"""

import sys
from pathlib import Path

# Add project root directory (group03-smartschedule-baseline) to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

