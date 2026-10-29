# docs/hint — programs and texts handed to the proposer (family-hint battery, 27/08; slot battery, Programa 4)

- `seed_family_poor.py` — crude member of the Bellec–Fritz family (atom at zero + three dyadic atoms toward the top), score 0.2734 at L = 5000. Seed of the `famseed` arm (27/08) and content of `hint_code_poor.txt`.
- `seed_family_oracle.py` — our best hand instantiation of the family on the L = 5000 grid, score 0.3742. Seed of the `oracle` arm.
- `seed_self_s11.py`, `seed_self_s12.py`, `seed_self_s13.py` — **verbatim** final programs of the `structural` arm of 27/08 (the proposer's own implementation of the family, written from the words hint; `runs/frontier/hint/structural_s{11,12,13}/best.py`, scores 0.3284 / 0.3383 / 0.3140). `seed_self_s11.py` is the seed of the `selfseed` arm (Programa 4); the other two are kept for the record.
- `seed_words.py` — the structural hint text as the docstring of the trivial seed program (score 0.2708, identical to the default seed): the words in the seed slot (`wordseed` arm).
- `hint_code_poor.txt` — the bytes of `seed_family_poor.py` preceded by one framing line: the code in the hint slot (`codehint` arm, `--hint-file`).

The structural hint text itself (the `words` arms) lives in `scripts/run_hint.sh` (27/08) and `scripts/run_slot_pod.sh` (Programa 4), byte-identical.
