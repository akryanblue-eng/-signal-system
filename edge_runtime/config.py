import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MORPHISM_PATH = REPO_ROOT / "transition_morphism.json"
WITNESS_OUTPUT_DIR = Path(
    os.environ.get("SIGNAL_SYSTEM_WITNESS_DIR", "/var/lib/signal-system/witnesses")
)
