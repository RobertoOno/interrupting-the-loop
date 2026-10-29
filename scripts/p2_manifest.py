#!/usr/bin/env python3
"""Programa 2 closure manifest (2026-09-04): commits, commands, parameters, seeds, models, timestamps,
costs and SHA-256 checksums of every raw artifact of stages 1 and 2 (runs/ is outside git, so the
checksums in docs/MANIFEST_P2.md are the audit trail). Read-only over runs/.

    python scripts/p2_manifest.py
"""
import hashlib, json, re, subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P2 = ROOT / "runs/p2"


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main():
    m = {"generated": datetime.now().isoformat(timespec="seconds"), "head": git("rev-parse", "HEAD"), "branch": git("rev-parse", "--abbrev-ref", "HEAD")}
    m["commits"] = {
        "stage1_engine_and_launch": "4343deb (2026-09-03 21:39) run_p2_stage1.sh; engine 663d3bd",
        "stage1_D0_control": "4aabb8f (2026-09-03 23:35) D0 arm added and registered before running",
        "reclassification_bound_2001": "1302517 (2026-09-03 23:36)",
        "stage2_harness_fix_at_launch": "94fc0ea (2026-09-04 01:17) raw-completions path; chain2 launched 01:17:52",
        "stage2_analysis_prewritten": "b2c0d63 (2026-09-04 03:50)",
        "stage2_single_read": "ddecca1 (2026-09-04 11:31)",
    }
    m["commands"] = {
        "stage1": "sh scripts/run_p2_stage1.sh opus|kimi  (D: --attempts 2 --workers 4; C2: --attempts 1; C1: mechanical; opus: --effort low --max-tokens 8000)",
        "stage1_D0": "python scripts/transfer_correspond.py --target sumdiff3 --arm D0 --model opus|kimi --attempts 2 --workers 4 --out stage1 [--effort low --max-tokens 8000]",
        "seeds": "python scripts/p2_pick_seeds.py --run stage1 --top 5",
        "stage2": "sh scripts/run_p2_stage2.sh full  -> frontier_search.py --problem sumdiff3 --oai-base http://localhost:18000/v1 --oai-completions --oai-model Qwen/Qwen3-30B-A3B-Base --gens 25 --samples 4 --islands 2 --max-tokens 700 --temp 1.0 --min-p 0.05 --seed {0,1,2} --seed-file <seed>",
        "stage2_pod": "runpodctl pod create --template-id runpod-torch-v280 --gpu-id 'NVIDIA H100 80GB HBM3' --container-disk-in-gb 150; vLLM api_server --max-model-len 8192 --gpu-memory-utilization 0.92 --max-num-seqs 64",
    }
    m["parameters"] = {"target": "sumdiff3 (theta; |U| <= 4000; verify 20 s)", "library": "72 mined (8 problems, sumdiff3 excluded) + 12 classical = 84 entries",
                       "stage2_design": "7 seed arms x 5 seeds x 3 RNG + A x 3 RNG = 108 runs; 25 generations x 4 samples x 2 islands = 200 proposals per run (registered: 100; deviation recorded 01:45)",
                       "models": {"frontier": "anthropic.claude-opus-5 via Bedrock (AWS profile main-account), effort low, 8000 tokens", "cheap": "moonshotai/kimi-k2.6 via OpenRouter, reasoning off",
                                  "loop_proposer": "Qwen/Qwen3-30B-A3B-Base, bf16, vLLM on H100 80GB (roaming), raw /completions"}}
    m["timestamps"] = {"stage1_D_C2": "2026-09-03 21:39 -> 23:34", "stage1_D0": "2026-09-03 23:36 -> 2026-09-04 00:46",
                       "stage2_attempt1": "2026-09-04 01:01 -> 01:15 (pod p4hd5t70wjj6ky; smoke gate aborted: chat instruction sent to a base model; pod deleted)",
                       "stage2_attempt2": "2026-09-04 01:17 -> 11:30 (pod zszvznncc6vi59; server ready 01:30; CM-DONE 11:30; pod deleted: true)"}
    m["costs"] = {"opus_tokens": {"D": [410010, 614421], "C2": [164156, 146316], "D0": [68208, 811846]},
                  "opus_usd_list_price": round((410010 + 164156 + 68208) / 1e6 * 5 + (614421 + 146316 + 811846) / 1e6 * 25, 2),
                  "kimi_tokens": {"D": [287893, 802412], "C2": [120232, 125719], "D0": [48498, 535668]},
                  "kimi_usd_estimate": "≈ 4 (assumed ≈US$0.6/M in, ≈US$2.5/M out; exact OpenRouter rate not recorded)",
                  "pod_usd": "≈ 36.3 = RunPod balance 36.0 (reported 09-03) -> -0.26 (09-04 11:40); attempt 1 ≈ 0.9 + attempt 2 ≈ 35.4 at US$3.49/h",
                  "total_usd_estimate": "≈ 83"}
    # counts
    st2 = sorted(p for p in (P2 / "stage2").iterdir() if p.is_dir() and not p.name.startswith("smoke"))
    rows = valid = 0
    for d in st2:
        for l in (d / "history.jsonl").read_text().splitlines():
            r = json.loads(l); rows += 1; valid += bool(r.get("ok"))
    m["stage2_counts"] = {"runs": len(st2), "proposals": rows, "valid": valid, "smoke_rows": len((P2 / "stage2/smoke_A/history.jsonl").read_text().splitlines()),
                          "runs_with_best_py": sum((d / "best.py").exists() for d in st2)}
    seeds = json.loads((P2 / "stage1_seeds/manifest.json").read_text())
    m["seeds"] = seeds
    m["checksums"] = {}   # tracked artifacts first (present in any clone), then runs/ artifacts (ignored by git: outside the clone)
    m["tracked"] = ["docs/p2/stage2_audit_v2_results.json", "docs/transfer_library/index.json"]
    for rel in m["tracked"]:
        f = ROOT / rel
        if f.exists():
            m["checksums"][rel] = sha(f)
    m["volatile_excluded"] = ["runs/p2/stage2_audit*.json (full records with diagnostic re-execution scores of time-budgeted programs)",
                              "runs/p2/stage2_audit*.log", "runs/p2/stage2_audit_v2_diagnostics.json"]
    for f in sorted(list((P2 / "stage1").glob("*.jsonl")) + list((P2 / "stage1").glob("*.reclass.json")) + list((P2 / "stage1").glob("*.log"))
                    + list((P2 / "stage1_seeds").rglob("*.py")) + [P2 / "stage1_seeds/manifest.json"] + list(P2.glob("stage2_chain*.log"))):
        if f.exists():
            m["checksums"][f.relative_to(ROOT).as_posix()] = sha(f)
    for d in st2 + [P2 / "stage2/smoke_A"]:
        for name in ("history.jsonl", "state.json", "best.py"):
            f = d / name
            if f.exists():
                m["checksums"][f.relative_to(ROOT).as_posix()] = sha(f)
        lg = d.with_suffix(".log")
        if lg.exists():
            m["checksums"][lg.relative_to(ROOT).as_posix()] = sha(lg)
    (P2 / "MANIFEST_P2.json").write_text(json.dumps(m, indent=1))
    # tracked artifact with the FULL SHA-256 digests (sha256sum format): runs/ is outside git
    (ROOT / "docs/MANIFEST_P2_CHECKSUMS.sha256").write_text("".join(f"{v}  {k}\n" for k, v in m["checksums"].items()))
    L = ["# Manifesto final — Programa 2 (piloto de transferência no sum-difference III)\n", f"Gerado {m['generated']} em `{m['branch']}` @ {m['head'][:7]}. Somente leitura sobre `runs/` (fora do git); os checksums abaixo são a trilha de auditoria.\n",
         "## Commits\n"] + [f"- {k}: {v}" for k, v in m["commits"].items()] + ["\n## Comandos\n"] + [f"- **{k}**: `{v}`" for k, v in m["commands"].items()] + \
        ["\n## Parâmetros\n", f"- alvo: {m['parameters']['target']}", f"- biblioteca: {m['parameters']['library']}", f"- desenho da etapa 2: {m['parameters']['stage2_design']}"] + \
        [f"- modelo {k}: {v}" for k, v in m["parameters"]["models"].items()] + ["\n## Horários\n"] + [f"- {k}: {v}" for k, v in m["timestamps"].items()] + \
        ["\n## Contagens da etapa 2\n"] + [f"- {k}: {v}" for k, v in m["stage2_counts"].items()] + \
        ["\n## Custos\n", f"- Opus (tokens in/out por braço): {m['costs']['opus_tokens']} → US${m['costs']['opus_usd_list_price']} a preço de lista",
         f"- Kimi (tokens in/out por braço): {m['costs']['kimi_tokens']} → {m['costs']['kimi_usd_estimate']}", f"- pod: {m['costs']['pod_usd']}", f"- total: {m['costs']['total_usd_estimate']}",
         "\n## Sementes da etapa 2 (top-5 por braço)\n", "| braço | k | θ | família (leitura 1) | origem |", "|---|---|---|---|---|"] + \
        [f"| {s['arm']} | {s['k']} | {s['score']:.5f} | {s['family']} | {s['entry'].split('transfer_library/')[-1]} |" for s in seeds] + \
        [f"\n## Checksums SHA-256 ({len(m['checksums'])} artefatos; digests completos em `docs/MANIFEST_P2_CHECKSUMS.sha256`)\n",
         "Rastreados no clone: " + ", ".join(f"`{x}`" for x in m["tracked"]) + ". Os demais vivem em `runs/` (ignorado pelo git) e ficam fora do clone;",
         "os checksums permitem conferir cópias. Excluídos por serem voláteis (escores diagnósticos de programas com orçamento de tempo): " + "; ".join(m["volatile_excluded"]) + ".",
         'Dependência de análise: `pip install -e ".[analysis]"` (scipy, numpy).\n', "| artefato | sha256 (prefixo) |", "|---|---|"] + [f"| {k} | `{v[:16]}…` |" for k, v in m["checksums"].items()]
    (ROOT / "docs/MANIFEST_P2.md").write_text("\n".join(L) + "\n")
    print(json.dumps({k: m[k] for k in ("stage2_counts", "costs")}, indent=1)); print("checksums:", len(m["checksums"]))


if __name__ == "__main__":
    main()
