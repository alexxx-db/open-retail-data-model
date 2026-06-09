import os
import sys

# Make the repo root importable so tests can use the shared resolver
# (tools.ordm_config) — the single source of truth for ${*_schema} tokens.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
