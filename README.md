# Language-model generation and verified search

Published papers, reports and reproducibility code by Roberto I. Ono Filho, independent researcher ([ORCID 0009-0006-8650-629X](https://orcid.org/0009-0006-8650-629X)). The series studies generation, verified search, consolidation, the use of supplied information and the reliability of AI-assisted research.

Start with [REPRODUCING.md](REPRODUCING.md) for installation, offline tests, data restoration and paper-output commands. The [public research record](NOTEBOOK.md) links dated protocols and immutable evidence. [Publication notes](docs/PUBLICATION_NOTES.md) distinguish delivered versions from later qualifications.

## Papers and reports

The PDF and LaTeX sources in each directory correspond to the delivered version below.

1. **Interrupting the Loop: Periodic Subject Changes Raise Judged Surprise and Connection in Base Language Models** — [paper/](paper/), corrected version 2; [arXiv:2608.19893](https://arxiv.org/abs/2608.19893), [Zenodo 23163693](https://doi.org/10.5281/zenodo.23163693).
2. **Moving the Mean Toward the Known Good, Not Beyond It** — [paper2/](paper2/), corrected version 2; [arXiv:2608.28886](https://arxiv.org/abs/2608.28886), [Zenodo 23163706](https://doi.org/10.5281/zenodo.23163706).
3. **Operator Packages, Proposer Strength, and Construction-Family Plateaus in Office-Scale Verified Search** — [paper3/](paper3/), paper version 4; [arXiv:2609.29636](https://arxiv.org/abs/2609.29636), [Zenodo 23163677](https://doi.org/10.5281/zenodo.23163677).
4. **What State-Space Injection Buys in Open-Ended Generation, and What It Costs** — [paper4/](paper4/), version 4; [Zenodo 23163708](https://doi.org/10.5281/zenodo.23163708).
5. **Operable Form, Not Stimulus: What Seven Pre-Registered Programs Say a Language Model Does with the Ideas It Is Handed, and Where Stimulating It Had a Ceiling** — [paper5/](paper5/), version 1, 11 September; [Zenodo 22714792](https://doi.org/10.5281/zenodo.22714792).
6. **Fine-Tuning a Language Model on Its Own Verified Lean Proofs: Transfer, Generalisation and Saturation Across Three Iterations** — [paper6/](paper6/), report version 1; [Zenodo 23163729](https://doi.org/10.5281/zenodo.23163729). A frozen report, not submitted to a venue.
7. **Errata in AI-Executed Research: A Census of Six Papers, a Blind Replay of the Checks, and What the Record Says About Why** — [paper7/](paper7/), report deposited on 22 October; [Zenodo 23562924](https://doi.org/10.5281/zenodo.23562924).

The short evaluation paper **What a Windowed LLM Judge Cannot See** is in [paper/short/](paper/short/), [Zenodo 23163731](https://doi.org/10.5281/zenodo.23163731).

## Code and data

- `src/creative_machine/`: sampling, generation, evaluation, verified-search domains and the formal-route instruments used by the published work.
- `scripts/`: experimental runners, frozen readers, table and figure generators, and the public-data restorer.
- `tests/`: synthetic and optional integration tests for the published code.
- `docs/`: selected protocols, single-read appendices and compact numerical results. The historical notebook excerpt and agent instructions are frozen; use the public record above for navigation.

Raw evidence is distributed through versioned deposits rather than committed into this tree:

- [10.5281/zenodo.22714138](https://doi.org/10.5281/zenodo.22714138): the original `run-data-v1` and `run-data-v2` releases for papers 1–4, also in [GitHub releases](https://github.com/RobertoOno/interrupting-the-loop/releases).
- [10.5281/zenodo.22713807](https://doi.org/10.5281/zenodo.22713807): the three programs underlying paper 5, with their protocols, code, Lean worlds, runs and verifier reports.
- [10.5281/zenodo.23163299](https://doi.org/10.5281/zenodo.23163299): October correction evidence for papers 1–4 and 6, including missing runs, LLM judgments, analysis code and dated pre-registration excerpts.
- [10.5281/zenodo.23562924](https://doi.org/10.5281/zenodo.23562924): paper 7, its redacted replay evidence, frozen documents, R2 pilots and review record.

Each deposit documents its checksums, redactions and omissions. Individual human ratings and identity keys are withheld. Model adapters and large hidden-state tensors have recorded hashes where they are not distributed. Some historical reproduction steps require private records; their limits are explicit in [REPRODUCING.md](REPRODUCING.md).

This public tree is a curated export. [The export manifest](docs/PUBLIC_EXPORT_MANIFEST.json) identifies the deposited sources and SHA-256 of exported files. Historical protocol commits refer to the private research history; they need not resolve here. On 5 October the older public history was rewritten to remove identifying details about human raters.

## Interpretation and later qualifications

The studies report effects within their tasks, models and budgets. In particular, the 18–19 October follow-ups showed that the P3 recipient could solve without the supplied bridge when given a larger output budget: in those development worlds the bridge bought token efficiency. Resource-censored sessions must be distinguished from completed failures. See [publication notes](docs/PUBLICATION_NOTES.md) before extending earlier claims.

## License, citation and use of AI

The repository's [MIT license](LICENSE) covers the code. The data deposits specify their own licenses and attribution requirements. Cite the versioned paper or report and the data DOI used for an analysis.

The experiments, analyses and manuscripts were produced by the author working with Claude (Anthropic) as a programming and writing assistant inside Claude Code. The author decided the questions and designs and is responsible for the published work; the individual manuscripts document their use of AI and review status. This repository update was prepared with Codex (OpenAI).
