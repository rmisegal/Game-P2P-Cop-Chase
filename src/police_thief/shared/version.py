# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Global version tracking for code and config (glb-quality rule 6)."""

from pathlib import Path

CODE_VERSION = "2.1.1"
BOOK_VERSION = "1.0.36"  # guidelines book (kept in sync by scripts/sync_versions.py)
SUPPORTED_CONFIG_VERSIONS = ["1.10"]

# Short suffix shown in every GUI title bar (requirement: game id + rights).
COPYRIGHT_TITLE = "(c) 2026 Dr. Yoram Segal - all rights reserved"

# Full License & Copyright block shown in Help -> About (matches the GitHub LICENSE).
LICENSE_NOTICE = (
    "Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence "
    "Ltd. (GTAI). All rights reserved.\n\n"
    "Licensed under a restrictive Educational Use EULA - see LICENSE for the full "
    "binding terms. In short:\n\n"
    "- Use is limited to formally enrolled students under Dr. Yoram Segal's direct "
    "academic instruction, for personal educational purposes only.\n"
    "- No commercial use, no redistribution, no derivative works outside the "
    "curriculum without prior explicit written consent from Dr. Yoram Segal or an "
    "authorized GTAI representative.\n"
    "- By accessing, cloning, downloading, or using this repository you agree to be "
    "bound by the LICENSE terms.\n\n"
    "Licensing / authorization requests: segal@gal-tech.ai - www.gal-tech.ai"
)

# The bundled guidelines PDF (repo_root/docs/police_thief_p2p.pdf).
GUIDELINES_PDF = Path(__file__).resolve().parents[3] / "docs" / "police_thief_p2p.pdf"
