# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""GUI layer: per-peer Tkinter live view + replay player (no business logic).

Windows + uv venv quirk: Tk searches <venv>/lib/tcl8.6 while the base Python
ships the runtime under <base>/tcl/tcl8.6 — point the env vars there.
"""

import os
import sys
from pathlib import Path


def _fix_tcl_env() -> None:
    base = Path(sys.base_prefix)
    for var, sub in (("TCL_LIBRARY", "tcl8.6"), ("TK_LIBRARY", "tk8.6")):
        candidate = base / "tcl" / sub
        if var not in os.environ and candidate.is_dir():
            os.environ[var] = str(candidate)


_fix_tcl_env()
