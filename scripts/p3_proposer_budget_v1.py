#!/usr/bin/env python3
"""Proposer budget sensitivity (pre-registered in PLANO 2026-09-11 BEFORE any call; round-5 reviews of papers 4/5).
The trigger ablation found 23/24 proposer sessions without a same-kind example ending at the 16,384-token output cap
without a submission. Is that null censored by the budget? Same two worlds, same runner, same prompts (D0 = target
alone; T5 = kind in words + the order to first write one's own worked example), two output caps per response
(32,768 and 65,536), two replicates: 16 sessions.

The frozen development runner enforces ceilings (16,384 per request, 20,000 per session, 600 s); this script does not
edit it: it installs its own explicit validation with the lifted ceilings declared here, and every artifact records
the configuration used (input.json). Model outcomes are never retried; a transport/infrastructure failure before any
model verdict is reported as such and may be rerun ONCE under a new cell id (recorded in launcher.jsonl).

Transport amendment (PLANO 2026-09-11, 14:55 UTC, before any further call): the first two 32,768-token requests never
returned through the non-streaming path (APITimeoutError at the 2,400 s request timeout, no bytes; 16,384-token sessions
of the ablation had taken 168-195 s). The launcher now injects a client whose messages.create sends the SAME request
through the streaming endpoint and returns the assembled final message; count_tokens and max_retries=0 are untouched,
the frozen runner is untouched. Cells that failed before any model verdict are rerun once under "<id>_R2".

    PYTHONPATH=src python scripts/p3_proposer_budget_v1.py [--limit N] [--workers 2]     # run
    python scripts/p3_proposer_budget_v1.py --read                                        # single read
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "scripts"))
OUT = REPO / "runs/p3/proposer_budget_v1"
ARMS = ("D0", "T5"); CAPS = (32768, 65536); REPS = 2
CEILINGS = {"max_turns": 12, "timeout_seconds": 3600, "request_timeout_seconds": 2400,
            "max_input_tokens": 200_000, "max_output_tokens": 81_920, "output_per_request": 65_536}
REFERENCE_16K = {"D0": "0/4", "T5": "0/4"}   # docs/APPENDIX_P3_TRIGGER.md (single read of 2026-09-09)


def budget_validate(config) -> None:
    """Same invariants as production_runner_v1._validate_config, with the ceilings of this protocol."""
    for name in ("max_turns", "max_input_tokens", "max_output_tokens", "output_per_request"):
        value = getattr(config, name)
        if type(value) is not int or value <= 0:
            raise ValueError(f"invalid configuration: {name}")
    for name in ("timeout_seconds", "request_timeout_seconds", "input_usd_per_million", "output_usd_per_million"):
        value = getattr(config, name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"invalid configuration: {name}")
    if (config.model != "anthropic.claude-opus-5" or config.effort != "high"
            or config.aws_profile != "main-account" or config.aws_region != "us-east-1"):
        raise ValueError("no model/profile/region fallback")
    if any(getattr(config, name) > ceiling for name, ceiling in CEILINGS.items()):
        raise ValueError("configuration exceeds the budget-sensitivity ceilings")


class _StreamingMessages:
    """messages.create through the streaming endpoint with the same body; count_tokens passthrough."""

    def __init__(self, inner):
        self._inner = inner

    def count_tokens(self, **kw):
        return self._inner.count_tokens(**kw)

    def create(self, **kw):
        with self._inner.stream(**kw) as stream:
            return stream.get_final_message()


class StreamingClient:
    """Declared transport substitution (see module docstring); exposes the runner's contract (max_retries == 0)."""

    max_retries = 0

    def __init__(self, inner):
        if getattr(inner, "max_retries", None) != 0:
            raise ValueError("inner client must have max_retries == 0")
        self._inner = inner
        self.messages = _StreamingMessages(inner.messages)


TRANSPORT = "streaming"


def budget_config(cap: int):
    from creative_machine.formal_routes.production_runner_v1 import production_config
    return replace(production_config(), output_per_request=cap, max_output_tokens=cap + 16384,
                   request_timeout_seconds=2400.0, timeout_seconds=3600.0)


def cells() -> list[dict]:
    from p3_trigger_ablation import WORLDS
    out = []
    for w in WORLDS:
        for arm in ARMS:
            for cap in CAPS:
                for rep in range(1, REPS + 1):
                    cid = "B_" + hashlib.sha256(f"{w}:{arm}:{cap}:{rep}".encode()).hexdigest()[:10].upper()
                    out.append({"cell_id": cid, "world": w, "world_id": Path(w).name, "arm": arm, "cap": cap, "rep": rep})
    out.sort(key=lambda c: hashlib.sha256(("2026091101:" + c["cell_id"]).encode()).hexdigest())
    return out


def run_cell(c: dict) -> dict:
    from creative_machine.formal_routes import production_runner_v1 as prod
    from creative_machine.formal_routes.bedrock_runner import make_client
    from creative_machine.formal_routes.calibration_worlds_v3 import load_v3
    from p3_trigger_ablation import make_record
    prod._validate_config = budget_validate     # declared substitution; the runner file is untouched
    root = OUT / c["cell_id"]; t0 = time.monotonic(); row = {"cell": c, "started_at": datetime.now(timezone.utc).isoformat()}
    try:
        world = REPO / c["world"]; ns = load_v3(world, phase="calibration")["roles"]["namespace"]
        rec = make_record(world, c["arm"], root / "workspace", ns)
        root.mkdir(parents=True, exist_ok=True)
        (root / "ARM.txt").write_text(f"{c['arm']} cap={c['cap']}\ntransport={TRANSPORT}\n" + (f"rerun_of={c['rerun_of']}\n" if c.get("rerun_of") else ""))
        cfg = budget_config(c["cap"])
        res = prod.run_production_session(rec, namespace=ns, artifacts=root / "artifacts", config=cfg, client=StreamingClient(make_client(cfg)))
        row["result"] = res
    except Exception as exc:  # noqa: BLE001
        row["launcher_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    row["elapsed_seconds"] = round(time.monotonic() - t0, 1)
    (root / "result.json").write_text(json.dumps(row, indent=1, ensure_ascii=False, default=str) + "\n")
    return row


def usage_of(root: Path) -> dict:
    """Output tokens and requests from the runner's event log (best effort)."""
    ev = root / "artifacts" / "events.jsonl"; out_tok = 0; n = 0
    if ev.exists():
        for line in ev.read_text().splitlines():
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("event") == "request_settled":   # the runner settles usage per request under this event
                n += 1; u = e.get("tokens") or {}; out_tok += int(u.get("output_tokens") or 0)
    return {"responses": n, "output_tokens": out_tok}


def result_of(cid: str):
    path = OUT / cid / "result.json"
    return json.loads(path.read_text()) if path.exists() else None


def infra_failed(r) -> bool:
    """No model verdict: launcher/transport error, or the runner's own infrastructure_failure status."""
    return bool(r) and (bool(r.get("launcher_error")) or (r.get("result") or {}).get("status") == "infrastructure_failure")


def attempt_of(c: dict) -> tuple[str, dict | None]:
    """The result that counts for a cell: the single rerun if it exists, else the first attempt."""
    r2 = result_of(c["cell_id"] + "_R2")
    return (c["cell_id"] + "_R2", r2) if r2 is not None else (c["cell_id"], result_of(c["cell_id"]))


def read() -> None:
    rows = {c["cell_id"]: attempt_of(c) for c in cells()}
    L = ["# Sensibilidade do propositor ao teto de saída (Opus 5; D0 e T5 a 32.768 e 65.536 tokens; leitura única)\n",
         "Pré-registro em `docs/PLANO.md` (2026-09-11) antes de qualquer chamada; mesmos mundos, prompts, contrato e verificador da ablação do gatilho "
         "(`docs/APPENDIX_P3_TRIGGER.md`), que a 16.384 tokens deu D0 0/4 e T5 0/4 com 23/24 sessões no teto. Tetos desta bateria: por resposta "
         "32.768 ou 65.536; por sessão cap + 16.384; 3.600 s por sessão; 2.400 s por requisição; 12 turnos.\n",
         "Transporte: streaming (emenda prospectiva de 11/09, 14:55 UTC, após as duas primeiras requisições sem streaming a 32.768 expirarem "
         "aos 2.400 s sem resposta; as células sem veredito do modelo foram repetidas uma vez sob `<id>_R2`, como o protocolo previa).\n",
         "| mundo | braço | teto | rep | tentativa | estado | desfecho | ponte válida | visível | revisões | respostas | tokens de saída | tempo (s) | custo US$ |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    tally = {}; tot = 0.0
    for c in cells():
        cid, r = rows[c["cell_id"]]; res = (r or {}).get("result") or {}; cost = float(res.get("cost_usd_at_configured_rates") or 0); tot += cost
        ok = bool(res.get("selected_bridge")); key = (c["arm"], c["cap"]); tally.setdefault(key, [0, 0, 0]); tally[key][0] += ok; tally[key][1] += bool(res)
        tally[key][2] += (res.get("status") == "output_limit")
        u = usage_of(OUT / cid) if r else {"responses": "—", "output_tokens": "—"}
        L.append(f"| {c['world_id'][:6]} | {c['arm']} | {c['cap']} | {c['rep']} | {'R2' if cid.endswith('_R2') else '1'} | {res.get('status', 'não rodou' if r is None else (r.get('launcher_error') or '—'))} | "
                 f"{res.get('production_outcome', '—')} | {'sim' if ok else 'não'} | {'sim' if res.get('visible_solved') else 'não'} | {res.get('revisions', '—')} | "
                 f"{u['responses']} | {u['output_tokens']} | {(r or {}).get('elapsed_seconds', '—')} | {cost:.2f} |")
    L.append("\n| braço | teto | pontes válidas / sessões | sessões no teto de saída |"); L.append("|---|---|---|---|")
    for arm in ARMS:
        L.append(f"| {arm} | 16.384 (ablação, referência) | {REFERENCE_16K[arm]} | 4/4 |")
        for cap in CAPS:
            t = tally.get((arm, cap), [0, 0, 0]); L.append(f"| {arm} | {cap} | {t[0]}/{t[1]} | {t[2]}/{t[1]} |")
    L.append(f"\nCusto desta bateria: US${tot:.2f}.\n")
    (REPO / "docs/APPENDIX_P3_BUDGET.md").write_text("\n".join(L) + "\n"); print("\n".join(L))


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--read", action="store_true"); ap.add_argument("--limit", type=int, default=0); ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    if a.read: read(); return
    OUT.mkdir(parents=True, exist_ok=True)
    plan = OUT / "plan.json"
    if not plan.exists():
        plan.write_text(json.dumps({"cells": cells(), "ceilings": CEILINGS, "caps": CAPS, "arms": ARMS, "reps": REPS,
                                    "registered_at": datetime.now(timezone.utc).isoformat()}, indent=1) + "\n")
    pending = []
    for c in cells():
        r = result_of(c["cell_id"])
        if r is None:
            pending.append(c)
        elif infra_failed(r) and result_of(c["cell_id"] + "_R2") is None:
            pending.append({**c, "cell_id": c["cell_id"] + "_R2", "rerun_of": c["cell_id"]})
    if a.limit: pending = pending[: a.limit]
    log = OUT / "launcher.jsonl"
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for f in as_completed([ex.submit(run_cell, c) for c in pending]):
            r = f.result(); res = r.get("result") or {}
            s = {"cell_id": r["cell"]["cell_id"], "rerun_of": r["cell"].get("rerun_of"), "transport": TRANSPORT,
                 "world": r["cell"]["world_id"][:6], "arm": r["cell"]["arm"], "cap": r["cell"]["cap"], "rep": r["cell"]["rep"],
                 "status": res.get("status"), "outcome": res.get("production_outcome"), "bridge": bool(res.get("selected_bridge")), "visible": res.get("visible_solved"),
                 "revisions": res.get("revisions"), "cost": res.get("cost_usd_at_configured_rates"), "elapsed": r.get("elapsed_seconds"),
                 "error": r.get("launcher_error") or res.get("error"), "at": datetime.now(timezone.utc).isoformat()}
            with log.open("a") as h: h.write(json.dumps(s) + "\n")
            print(json.dumps(s), flush=True)
    print("done", len(pending))


if __name__ == "__main__":
    main()
