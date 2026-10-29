#!/usr/bin/env python3
"""Re-run the family classifier over every stored stage-1 transplant (the codes are in the
JSONL rows) after the carry-free base bound was raised from 25 to 2001. Writes
family2 / carry_free_base2 fields into <arm>.reclass.json (never edits the raw rows).

    PYTHONPATH=src python scripts/p2_reclassify.py --run stage1 --workers 6
"""
import argparse, json, sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))


def work(item):
    entry, attempt, code = item
    from transfer_correspond import get_object
    from family_sumdiff3 import features
    nums = get_object(code, "construct", [], 20)
    if not nums:
        return entry, attempt, None
    U = sorted({int(round(x)) for x in nums})
    if len(U) > 4000 or len(U) < 2:
        return entry, attempt, None
    f = features(U)
    f["family"] = "F0" if f["frac_pow2_sums_le3"] >= 0.8 else ("F_rec" if (f["carry_free_base"] and f["n"] >= 50) else "other")
    return entry, attempt, f


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--run", default="stage1"); ap.add_argument("--workers", type=int, default=6); a = ap.parse_args()
    run = ROOT / "runs/p2" / a.run
    for f in sorted(run.glob("*.jsonl")):
        rows = [json.loads(l) for l in f.read_text().splitlines()]
        items = [(r["entry"], r["attempt"], r["code"]) for r in rows if r.get("ok") and r.get("code")]
        out = {}
        with ProcessPoolExecutor(max_workers=a.workers) as ex:
            for entry, attempt, feat in ex.map(work, items):
                out[f"{entry}|{attempt}"] = feat
        (run / f"{f.stem}.reclass.json").write_text(json.dumps(out))
        fams = {}
        for feat in out.values():
            k = feat["family"] if feat else "none"; fams[k] = fams.get(k, 0) + 1
        print(f.stem, fams)


if __name__ == "__main__":
    main()
