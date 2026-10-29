"""One prospective, count-only D/C2 preflight; no generation or source editing.

Freeze the metric and request hashes before obtaining native counts. The evidence
directory is exclusive: errors never authorize retry, padding, or another path.
The counter accepts a client for offline tests; only run() constructs the pinned
Bedrock Mantle client after checking committed inputs.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import time

from .calibration_protocol_v3 import HARNESS_FILES as HISTORICAL_FILES
from .calibration_worlds_v3 import load_v3
from .production_contract_v1 import materialize_production_proposer, render_production_proposer
from .production_runner_v1 import build_production_request, interface_hashes, production_config

PLAN_ID = "p3_source_matching_v1"
PLAN_PATH = "docs/p3/source_matching_plan_v1.json"
EVIDENCE_PATH = "docs/p3/source_matching_evidence_v1"
POLICY_PATH = "docs/p3/PAREAMENTO_NATIVO_FONTES_V1.md"
WORLDS = ("worlds/calibration/CAL3_I_E87C49876088749B",
          "worlds/calibration/CAL3_R_F76437525B190ECB")
ARMS = ("D0", "D", "C2")
SOURCE_PREFIX = "FILE SOURCE.md\n"
TOLERANCE_NUMERATOR = 1
TOLERANCE_DENOMINATOR = 20
COUNT_TIMEOUT_SECONDS = 30.0
BASE_URL = "https://bedrock-mantle.us-east-1.api.aws/anthropic"
EXPECTED_SDK_VERSION = "1.4.0"
EXTRA_FILES = (
    "src/creative_machine/formal_routes/production_contract_v1.py",
    "src/creative_machine/formal_routes/production_runner_v1.py",
    "src/creative_machine/formal_routes/source_matching_v1.py",
    "scripts/p3_source_matching_v1.py", "tests/test_p3_source_matching_v1.py", POLICY_PATH,
)


def encoded(value) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_new(path: Path, data: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def catalog(repository: Path) -> list[dict]:
    """Host labels stay outside the model-facing request; no hidden-file render."""
    config = production_config()

    def item(identity, kind, content, **labels):
        body = build_production_request([{"role": "user", "content": content}], config)
        return {"id": identity, "kind": kind, **labels, "body": body,
                "body_sha256": sha(encoded(body))}

    rows = [item("empty_source", "empty_source", SOURCE_PREFIX)]
    for world_rel in WORLDS:
        world = repository / world_rel
        metadata = load_v3(world, phase="calibration")
        family = metadata["family"]
        for arm, source_rel in (("D", "Sources/Relevant.md"), ("C2", "Sources/Sham.md")):
            source = (world / source_rel).read_bytes()
            rows.append(item(f"{family}_source_{arm}", "source", SOURCE_PREFIX + source.decode("utf-8"),
                             family=family, arm=arm, world=world_rel,
                             source_sha256=sha(source), source_bytes=len(source)))
        for arm in ARMS:
            with tempfile.TemporaryDirectory(prefix="p3-source-count-input-") as temporary:
                record = materialize_production_proposer(world, arm, Path(temporary) / "workspace")
                payload = render_production_proposer(record)
                rows.append(item(f"{family}_initial_{arm}", "initial_proposer", payload,
                                 family=family, arm=arm, world=world_rel,
                                 input_sha256=sha(payload.encode()), copied_hashes=record.copied_hashes))
    return rows


def fingerprints(repository: Path) -> dict[str, str]:
    files = set(HISTORICAL_FILES) | set(EXTRA_FILES)
    for world in WORLDS:
        metadata = load_v3(repository / world, phase="calibration")
        files.update(f"{world}/{rel}" for rel in (*metadata["artifact_hashes"], "metadata.json", "manifest.sha256"))
    result = {}
    for rel in sorted(files):
        path = repository / rel
        if path.is_symlink() or not path.resolve().is_relative_to(repository.resolve()):
            raise ValueError("symlink or escaping source: " + rel)
        result[rel] = sha(path.read_bytes())
    return result


def build_plan(repository: Path) -> dict:
    return {"schema_version": 1, "plan_id": PLAN_ID, "status": "FROZEN_TOKEN_PREFLIGHT_ONLY",
            "metric": "incremental_native_input_tokens_above_identical_empty_source_wrapper",
            "relative_gap": "2*abs(D-C2)/(D+C2)",
            "tolerance": {"numerator": TOLERANCE_NUMERATOR, "denominator": TOLERANCE_DENOMINATOR},
            "require_both_families": True, "source_prefix": SOURCE_PREFIX,
            "provider": "bedrock-mantle", "base_url": BASE_URL,
            "anthropic_sdk_version": EXPECTED_SDK_VERSION,
            "endpoint_path": "/v1/messages/count_tokens", "agent": asdict(production_config()),
            "interface_sha256": interface_hashes(), "max_requests": 11, "max_retries": 0,
            "timeout_seconds": COUNT_TIMEOUT_SECONDS, "evidence_path": EVIDENCE_PATH,
            "inference_sessions_authorized": 0, "main_sample_admitted": False,
            "on_gap_failure": "review_sources_prospectively_no_automatic_adjustment",
            "on_technical_failure": "preserve_partial_evidence_stop_no_retry",
            "harness_and_world_sha256": fingerprints(repository),
            "requests": [{k: v for k, v in row.items() if k != "body"} for row in catalog(repository)]}


def prepare(repository: Path) -> dict:
    plan = build_plan(repository)
    save_new(repository / PLAN_PATH, encoded(plan))
    return plan


def load_plan(repository: Path) -> dict:
    plan = json.loads((repository / PLAN_PATH).read_bytes())
    if encoded(plan) != encoded(build_plan(repository)):
        raise ValueError("source-matching plan, policy, inputs or implementation drift")
    return plan


def assert_committed(repository: Path, plan: dict) -> str:
    for rel in (*plan["harness_and_world_sha256"], PLAN_PATH):
        committed = subprocess.check_output(["git", "show", "HEAD:" + rel], cwd=repository, timeout=15)
        if committed != (repository / rel).read_bytes():
            raise ValueError("uncommitted source-matching input: " + rel)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True, timeout=15).strip()


def summarize(rows: list[dict], counts: dict[str, int]) -> dict:
    expected = [row["id"] for row in rows]
    if len(expected) != len(set(expected)) or set(counts) != set(expected):
        raise ValueError("missing, extra or duplicate native count")
    if any(type(n) is not int or n < 0 for n in counts.values()):
        raise ValueError("invalid native count")
    overhead = counts["empty_source"]
    families = {}
    for family in ("invariant", "representation"):
        d = counts[f"{family}_source_D"] - overhead
        c2 = counts[f"{family}_source_C2"] - overhead
        if min(d, c2) <= 0:
            raise ValueError("nonpositive incremental source token count")
        # Integer cross multiplication fixes the inclusive 5% boundary exactly.
        passed = 2 * abs(d - c2) * TOLERANCE_DENOMINATOR <= (d + c2) * TOLERANCE_NUMERATOR
        families[family] = {"source_incremental_tokens": {"D": d, "C2": c2},
                            "symmetric_relative_gap": 2 * abs(d - c2) / (d + c2),
                            "within_tolerance": passed,
                            "full_initial_input_tokens": {arm: counts[f"{family}_initial_{arm}"] for arm in ARMS}}
    passed = all(row["within_tolerance"] for row in families.values())
    return {"plan_id": PLAN_ID, "status": "complete", "count_requests": len(counts),
            "empty_source_input_tokens": overhead, "families": families, "matching_passed": passed,
            "next_step": "continue_prospective_batch_preparation" if passed else
                         "review_sources_prospectively_no_automatic_adjustment",
            "inference_calls": 0, "main_sample_admitted": False,
            "scope": "Native input estimates, not billed usage, semantic equality, or model outcomes."}


def count_once(rows: list[dict], *, client, destination: Path, provenance: dict) -> dict:
    """Strictly count-only execution; all raw JSON response bytes are retained."""
    if type(getattr(client, "max_retries", None)) is not int or client.max_retries != 0:
        raise ValueError("disable native count retries")
    if len(rows) != 11 or len({row["id"] for row in rows}) != 11:
        raise ValueError("exactly eleven distinct requests are required")
    for row in rows:
        if not row["id"].replace("_", "").isalnum() or sha(encoded(row["body"])) != row["body_sha256"]:
            raise ValueError("invalid count request identity or hash")
    if destination.is_symlink():
        raise ValueError("evidence destination is a symlink")
    destination.mkdir(parents=True, exist_ok=False)
    save_new(destination / "provenance.json", encoded(provenance))
    save_new(destination / "events.jsonl", b"")
    started = time.monotonic()
    counts, sequence = {}, 0

    def event(kind, **data):
        nonlocal sequence
        sequence += 1
        payload = {"seq": sequence, "event": kind, "at": datetime.now(timezone.utc).isoformat(),
                   "elapsed_seconds": time.monotonic() - started, **data}
        with (destination / "events.jsonl").open("ab") as handle:
            handle.write(json.dumps(payload, sort_keys=True, allow_nan=False).encode() + b"\n")
            handle.flush()
            os.fsync(handle.fileno())

    for row in rows:
        identity = row["id"]
        save_new(destination / f"{identity}.request.json", encoded(row["body"]))
        event("count_started", request_id=identity, body_sha256=row["body_sha256"],
              timeout_seconds=COUNT_TIMEOUT_SECONDS)
        try:
            response = client.messages.with_raw_response.count_tokens(
                **deepcopy(row["body"]), timeout=COUNT_TIMEOUT_SECONDS)
            raw = response.read()
            save_new(destination / f"{identity}.response.json", raw)
            parsed = json.loads(raw)
            value = parsed.get("input_tokens") if isinstance(parsed, dict) else None
            if type(value) is not int or value < 0:
                raise ValueError("native counter returned invalid input_tokens")
            counts[identity] = value
            event("count_finished", request_id=identity, input_tokens=value, response_sha256=sha(raw),
                  provider_request_id=response.request_id or response.headers.get("x-amzn-requestid"),
                  http_status=response.status_code)
        except Exception as exc:
            # Provider error response is useful evidence, without credential headers.
            body = getattr(exc, "body", None)
            event("count_failed", request_id=identity, error_type=type(exc).__name__,
                  detail=str(exc), provider_error_body=body)
            result = {"plan_id": PLAN_ID, "status": "technical_failure", "matching_passed": None,
                      "completed_counts": counts, "failed_request": identity,
                      "next_step": "preserve_partial_evidence_stop_no_retry", "inference_calls": 0}
            break
    else:
        try:
            result = summarize(rows, counts)
        except ValueError as exc:
            event("invalid_measurement", detail=str(exc))
            result = {"plan_id": PLAN_ID, "status": "technical_failure", "matching_passed": None,
                      "completed_counts": counts, "next_step": "review_invalid_native_measurement",
                      "inference_calls": 0}
    event("preflight_finished", status=result["status"])
    save_new(destination / "result.json", encoded(result))
    manifest = {p.name: sha(p.read_bytes()) for p in sorted(destination.iterdir()) if p.is_file()}
    save_new(destination / "manifest.json", encoded(manifest))
    return result


def audit(repository: Path) -> dict:
    """Recompute completed counts and their decision without contacting a client."""
    plan = load_plan(repository)
    root = repository / EVIDENCE_PATH
    if root.is_symlink() or any(p.is_symlink() or not p.is_file() for p in root.iterdir()):
        raise ValueError("unexpected entry in count evidence")
    manifest = json.loads((root / "manifest.json").read_bytes())
    actual = {p.name: sha(p.read_bytes()) for p in root.iterdir() if p.is_file() and p.name != "manifest.json"}
    if manifest != actual:
        raise ValueError("native count evidence drift")
    provenance = json.loads((root / "provenance.json").read_bytes())
    if provenance["plan_sha256"] != sha(encoded(plan)) or provenance["injected_client"]:
        raise ValueError("wrong plan or synthetic evidence")
    if (provenance["client_class"] != "anthropic.lib.bedrock._mantle.AnthropicBedrockMantle"
            or provenance["base_url"] != BASE_URL or provenance["max_retries"] != 0
            or provenance["aws_profile"] != "main-account" or provenance["aws_region"] != "us-east-1"
            or provenance["endpoint_path"] != "/v1/messages/count_tokens"):
        raise ValueError("provider provenance drift")
    rows, counts = catalog(repository), {}
    expected_files = {"provenance.json", "events.jsonl", "result.json"} | {
        f"{r['id']}.{suffix}.json" for r in rows for suffix in ("request", "response")}
    if set(manifest) != expected_files:
        raise ValueError("unexpected count evidence inventory")
    events = [json.loads(line) for line in (root / "events.jsonl").read_bytes().splitlines()]
    if [e["seq"] for e in events] != list(range(1, len(events) + 1)):
        raise ValueError("invalid event sequence")
    if [e["event"] for e in events] != [kind for _ in rows for kind in ("count_started", "count_finished")] + ["preflight_finished"]:
        raise ValueError("invalid count event order")
    times = [e["elapsed_seconds"] for e in events]
    if times != sorted(times) or any(datetime.fromisoformat(e["at"]).tzinfo is None for e in events):
        raise ValueError("invalid count timestamps")
    if [e["request_id"] for e in events if e["event"] == "count_started"] != [r["id"] for r in rows]:
        raise ValueError("count order or completeness drift")
    for row in rows:
        identity = row["id"]
        if (root / f"{identity}.request.json").read_bytes() != encoded(row["body"]):
            raise ValueError("model-facing count request drift")
        raw = (root / f"{identity}.response.json").read_bytes()
        counts[identity] = json.loads(raw)["input_tokens"]
        begun = next(e for e in events if e["event"] == "count_started" and e["request_id"] == identity)
        if begun["body_sha256"] != row["body_sha256"] or begun["timeout_seconds"] != COUNT_TIMEOUT_SECONDS:
            raise ValueError("count request and event disagree")
        finished = [e for e in events if e["event"] == "count_finished" and e["request_id"] == identity]
        if (len(finished) != 1 or finished[0]["input_tokens"] != counts[identity]
                or finished[0]["response_sha256"] != sha(raw) or finished[0]["http_status"] != 200):
            raise ValueError("native response and event disagree")
    result = summarize(rows, counts)
    if encoded(result) != (root / "result.json").read_bytes():
        raise ValueError("native count result does not reconstruct")
    return result


def run(repository: Path) -> dict:
    plan = load_plan(repository)
    if (repository / EVIDENCE_PATH).exists() or (repository / EVIDENCE_PATH).is_symlink():
        raise FileExistsError("native preflight already attempted; never rerun or relocate")
    commit = assert_committed(repository, plan)
    rows = catalog(repository)
    if [{k: v for k, v in row.items() if k != "body"} for row in rows] != plan["requests"]:
        raise ValueError("count inputs changed after commit check")
    if version("anthropic") != EXPECTED_SDK_VERSION:
        raise ValueError("native counter SDK version drift")
    from anthropic import AnthropicBedrockMantle
    client = AnthropicBedrockMantle(aws_profile="main-account", aws_region="us-east-1",
                                   base_url=BASE_URL, max_retries=0, timeout=COUNT_TIMEOUT_SECONDS)
    if (client.aws_profile != "main-account" or client.aws_region != "us-east-1"
            or not client._use_sigv4 or client.skip_auth or str(client.base_url).rstrip("/") != BASE_URL):
        raise ValueError("unexpected Mantle provider, profile, region or authentication mode")
    packages = {}
    for name in ("anthropic", "boto3", "botocore", "httpx2"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    provenance = {"commit_before_counts": commit, "plan_sha256": sha(encoded(plan)),
                  "started_at": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
                  "packages": packages, "client_class": f"{type(client).__module__}.{type(client).__qualname__}",
                  "injected_client": False, "base_url": BASE_URL, "endpoint_path": plan["endpoint_path"],
                  "aws_profile": client.aws_profile, "aws_region": client.aws_region, "max_retries": 0}
    try:
        return count_once(rows, client=client, destination=repository / EVIDENCE_PATH,
                          provenance=provenance)
    finally:
        client.close()
