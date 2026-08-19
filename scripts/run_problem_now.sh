#!/bin/sh
cd "$(dirname "$0")/.." || exit 1
caffeinate -is .venv/bin/python scripts/dream_battery2.py --battery problem --premises problem --rng-seed 0 --out runs/dream_problem
caffeinate -is .venv/bin/python scripts/dream_battery2.py --battery problem --premises problem --rng-seed 1 --out runs/dream_problem_r1
echo "PROBLEM BATTERY DONE $(date)"
.venv/bin/python scripts/problem_verify.py runs/dream_problem > runs/dream_problem/verify.log 2>&1
.venv/bin/python scripts/problem_verify.py runs/dream_problem_r1 > runs/dream_problem_r1/verify.log 2>&1
echo "PROBLEM VERIFIED $(date)"
