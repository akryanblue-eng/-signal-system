#!/usr/bin/env python3
"""
CLI v0: log_story — primary entry point.
Story Board always first. No constraint or attractor is valid
unless it traces back to at least one story event.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORIES_DIR = ROOT / "stories"


def next_id(date_str: str) -> str:
    prefix = f"story_{date_str.replace('-', '_')}_"
    existing = list(STORIES_DIR.glob(f"{prefix}*.json"))
    return f"{prefix}{len(existing) + 1:03d}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Log a story event to the capture layer."
    )
    parser.add_argument("--text", required=True, help="One-sentence literal observation")
    parser.add_argument("--driver", required=True, help="Memory driver")
    parser.add_argument("--intensity", type=int, choices=[1, 2, 3], required=True,
                        help="Signal intensity: 1=low, 2=moderate, 3=high")
    parser.add_argument("--salience", action="store_true",
                        help="Mark as high-salience candidate for attractor promotion")
    args = parser.parse_args()

    sentence_count = args.text.count(".") + args.text.count("!") + args.text.count("?")
    if sentence_count > 1:
        print("WARNING: text should be exactly one sentence. No interpretation.", file=sys.stderr)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    STORIES_DIR.mkdir(exist_ok=True)
    story_id = next_id(date_str)

    story = {
        "id": story_id,
        "timestamp": now.isoformat(),
        "text": args.text,
        "memory_driver": args.driver,
        "intensity": args.intensity,
        "high_salience": args.salience,
        "perturbation_refs": [],
        "attractor_refs": []
    }

    out = STORIES_DIR / f"{story_id}.json"
    out.write_text(json.dumps(story, indent=2))
    print(f"Logged: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
