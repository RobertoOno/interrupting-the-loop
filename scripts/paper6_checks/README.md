# Post hoc checks of paper 6 (5 October 2026)

Scripts written during the audit of paper 6 (`docs/correcoes_2026-10-05/auditoria_paper6.md`). They produce the counts marked
"post hoc" in Section 10 of the report ("Corrections after freezing"). Run from the repository root.

- `parity_e.py`: which E worlds admit the parity of y as a separating invariant (75 of the generator's 132, 66 of the 108 used).
- `accepted.py`: applies the A6 classifier (`scripts/a6_forms.py`, unchanged) to the accepted proof (`Solution.lean`) of every
  observed solved session in the evidence archives; output `docs/paper6_checks_2026-10-05/accepted.jsonl`.
- `own3_l4.py`: own3's first submissions at L4 compared numerically with the hidden reference measure (13 of 24 exact).
- `l2_modular.py`: modular separating forms at L2 (the L2 shortcut family).

None of these counts is a registered read; none changes a registered verdict.
