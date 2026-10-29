# Program 3A calibration worlds

These worlds are infrastructure and behavioral-calibration fixtures only. They are permanently excluded
from the main sample, even if a future run does not expose them to a model.

- `CAL_T1_E2CCC255`: template T1, seed `e2ccc2555a3cccc7`.
- `CAL_T2_15CCB41E`: template T2, seed `15ccb41e67d0ca58`.

Each `metadata.json` records `phase: calibration` and `eligible_for_main: false`. Each
`manifest.sha256` covers every frozen artifact in that world. Build products (`.lake/` and
`lake-manifest.json`) are ignored and are not part of the frozen package.

Generate and validate from the repository root:

```bash
PYTHONPATH=src .venv/bin/python scripts/p3_worlds.py generate-calibration
PYTHONPATH=src .venv/bin/python scripts/p3_worlds.py validate --lean \
  worlds/calibration/CAL_T1_E2CCC255 \
  worlds/calibration/CAL_T2_15CCB41E
```
