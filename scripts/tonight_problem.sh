#!/bin/sh
# Battery B (the interrupted loop over a problem with a verifier), scheduled for the night:
# waits until 22:00 local, runs the problem battery with two RNG seeds, then verifies.
cd "$(dirname "$0")/.." || exit 1
while [ "$(date +%H)" -lt 22 ]; do sleep 300; done
mkdir -p runs/dream_problem runs/dream_problem_r1
caffeinate -is .venv/bin/python scripts/dream_battery2.py --battery problem --premises problem --rng-seed 0 --out runs/dream_problem
caffeinate -is .venv/bin/python scripts/dream_battery2.py --battery problem --premises problem --rng-seed 1 --out runs/dream_problem_r1
echo "PROBLEM BATTERY DONE $(date)"
.venv/bin/python scripts/problem_verify.py runs/dream_problem > runs/dream_problem/verify.log 2>&1
.venv/bin/python scripts/problem_verify.py runs/dream_problem_r1 > runs/dream_problem_r1/verify.log 2>&1
echo "PROBLEM VERIFIED $(date)"
