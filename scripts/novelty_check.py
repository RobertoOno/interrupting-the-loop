#!/usr/bin/env python3
"""Check generated texts for objective novelty against an infini-gram index.

Example:

    python scripts/novelty_check.py runs/sweep_8b_band/lam=3.txt \
        --index olmo13b --ns 4,6,8 --stride 2
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from creative_machine.novelty import (  # noqa: E402
    INDEX_DOLMA,
    INDEX_OLMO2_13B,
    INDEX_OLMO2_32B,
    InfiniGramClient,
    novelty_report,
)

ALIASES = {"dolma": INDEX_DOLMA, "olmo13b": INDEX_OLMO2_13B, "olmo32b": INDEX_OLMO2_32B}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("files", nargs="+", type=Path)
    p.add_argument("--index", default="olmo13b", help="alias (dolma|olmo13b|olmo32b) or raw index name")
    p.add_argument("--ns", default="4,6,8")
    p.add_argument("--stride", type=int, default=2)
    p.add_argument("--throttle", type=float, default=0.25)
    args = p.parse_args()

    index = ALIASES.get(args.index, args.index)
    ns = tuple(int(x) for x in args.ns.split(","))
    for path in args.files:
        client = InfiniGramClient(index, throttle_s=args.throttle)
        rep = novelty_report(client, path.read_text(), ns=ns, stride=args.stride)
        print(f"=== {path}")
        print(json.dumps(rep.summary(), indent=2))


if __name__ == "__main__":
    main()
