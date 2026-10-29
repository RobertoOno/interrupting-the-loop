"""Offline native-counter fixtures. No provider or Lean runtime is needed."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from creative_machine.formal_routes import source_matching_v1 as matching
from creative_machine.formal_routes.production_runner_v1 import build_production_request, production_config

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def rows():
    return matching.catalog(REPO)


def sample_counts(rows, d=1000, c2=1000):
    result = {row["id"]: 5000 for row in rows}
    result["empty_source"] = 100
    for family in ("invariant", "representation"):
        result[f"{family}_source_D"] = 100 + d
        result[f"{family}_source_C2"] = 100 + c2
    return result


class FakeClient:
    max_retries = 0

    def __init__(self, values, on_count=None):
        self.messages = self.with_raw_response = self
        self.values = iter(values)
        self.calls = []
        self.on_count = on_count

    def count_tokens(self, **body):
        self.calls.append(deepcopy(body))
        if self.on_count:
            self.on_count()
        value = next(self.values)
        if isinstance(value, Exception):
            raise value
        raw = json.dumps({"input_tokens": value}, separators=(",", ":")).encode()
        return SimpleNamespace(read=lambda: raw, request_id="synthetic-id", headers={}, status_code=200)

    def create(self, **body):
        raise AssertionError("generation must never be used by a token preflight")


def test_request_catalog_has_fixed_two_worlds_eleven_counts_and_shared_wrapper(rows):
    assert len(rows) == 11 and len({r["id"] for r in rows}) == 11
    assert rows[0]["id"] == "empty_source"
    assert rows[0]["body"]["messages"][0]["content"] == matching.SOURCE_PREFIX
    assert [r["id"] for r in rows[1:6]] == [
        "invariant_source_D", "invariant_source_C2", "invariant_initial_D0",
        "invariant_initial_D", "invariant_initial_C2"]
    assert {r["world"] for r in rows[1:]} == set(matching.WORLDS)
    assert all(r["body_sha256"] == matching.sha(matching.encoded(r["body"])) for r in rows)


def test_count_bodies_use_exact_production_interface_without_generation_limit(rows):
    for row in rows:
        assert row["body"] == build_production_request(row["body"]["messages"], production_config())
        assert "max_tokens" not in row["body"]
        assert "family" not in row["body"] and "arm" not in row["body"]
        payload = row["body"]["messages"][0]["content"]
        for forbidden in ("FILE Hidden/", "FILE World/Holdout", "FILE metadata.json", "FILE manifest.sha256"):
            assert forbidden not in payload


def test_source_bytes_are_unchanged_and_d0_contains_no_source(rows):
    for row in rows:
        if row["kind"] == "source":
            kind = "Relevant" if row["arm"] == "D" else "Sham"
            source = (REPO / row["world"] / f"Sources/{kind}.md").read_bytes()
            assert row["body"]["messages"][0]["content"].encode() == matching.SOURCE_PREFIX.encode() + source
            assert row["source_sha256"] == matching.sha(source)
        if row.get("arm") == "D0":
            assert "SOURCE.md" not in row["copied_hashes"]
            assert "FILE SOURCE.md" not in row["body"]["messages"][0]["content"]


@pytest.mark.parametrize(("d", "c2", "passed"), [(1000, 1000, True), (1025, 975, True),
                                                   (1026, 975, False), (975, 1026, False)])
def test_symmetric_inclusive_five_percent_boundary(rows, d, c2, passed):
    result = matching.summarize(rows, sample_counts(rows, d=d, c2=c2))
    assert result["matching_passed"] is passed
    assert result["families"]["invariant"]["symmetric_relative_gap"] == 2 * abs(d - c2) / (d + c2)


def test_common_context_cannot_dilute_source_imbalance(rows):
    counts = sample_counts(rows, d=2000, c2=1000)
    for row in rows:
        if row["kind"] == "initial_proposer":
            counts[row["id"]] = 100000
    result = matching.summarize(rows, counts)
    assert result["matching_passed"] is False
    assert result["next_step"] == "review_sources_prospectively_no_automatic_adjustment"


def test_one_failed_family_blocks_the_matching_gate(rows):
    counts = sample_counts(rows)
    counts["representation_source_D"] = 3000
    result = matching.summarize(rows, counts)
    assert result["families"]["invariant"]["within_tolerance"]
    assert not result["matching_passed"]


@pytest.mark.parametrize("bad", [-1, 1.5, True, "123", None])
def test_invalid_counts_are_not_scientific_matching_failures(rows, bad):
    counts = sample_counts(rows)
    counts["invariant_source_D"] = bad
    with pytest.raises(ValueError, match="invalid native count"):
        matching.summarize(rows, counts)


@pytest.mark.parametrize("increment", [0, -1])
def test_nonpositive_increment_is_invalid(rows, increment):
    with pytest.raises(ValueError, match="nonpositive"):
        matching.summarize(rows, sample_counts(rows, d=increment))


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate"])
def test_inventory_must_be_exact(rows, mutation):
    copy, counts = deepcopy(rows), sample_counts(rows)
    if mutation == "missing":
        counts.pop("empty_source")
    elif mutation == "extra":
        counts["extra"] = 123
    else:
        copy.append(copy[0])
    with pytest.raises(ValueError, match="missing, extra or duplicate"):
        matching.summarize(copy, counts)


def test_raw_responses_requests_events_and_manifest_are_preserved(rows, tmp_path):
    counts = sample_counts(rows)
    dest = tmp_path / "counts"

    def already_logged():
        assert (dest / f"{rows[len(client.calls)-1]['id']}.request.json").exists()
        assert json.loads((dest / "events.jsonl").read_text().splitlines()[-1])["event"] == "count_started"

    client = FakeClient([counts[r["id"]] for r in rows], on_count=already_logged)
    result = matching.count_once(rows, client=client, destination=dest, provenance={"injected_client": True})
    assert result["matching_passed"] and result["count_requests"] == 11 and result["inference_calls"] == 0
    assert len(client.calls) == 11
    for row, call in zip(rows, client.calls):
        assert call == {**row["body"], "timeout": 30.0}
        assert (dest / f"{row['id']}.request.json").read_bytes() == matching.encoded(row["body"])
        assert (dest / f"{row['id']}.response.json").read_bytes() == json.dumps(
            {"input_tokens": counts[row["id"]]}, separators=(",", ":")).encode()
    manifest = json.loads((dest / "manifest.json").read_text())
    assert manifest == {p.name: matching.sha(p.read_bytes()) for p in dest.iterdir() if p.name != "manifest.json"}
    with pytest.raises(FileExistsError):
        matching.count_once(rows, client=client, destination=dest, provenance={})
    assert len(client.calls) == 11


@pytest.mark.parametrize("bad", [RuntimeError("synthetic service error"), "invalid", -1, True])
def test_counter_stops_after_error_without_retry_or_generation(rows, tmp_path, bad):
    client = FakeClient([100, bad])
    result = matching.count_once(rows, client=client, destination=tmp_path / "counts", provenance={"injected_client": True})
    assert len(client.calls) == 2
    assert result["status"] == "technical_failure" and result["matching_passed"] is None
    assert result["completed_counts"] == {"empty_source": 100}
    assert result["inference_calls"] == 0
    assert (tmp_path / "counts/manifest.json").exists()


@pytest.mark.parametrize("retry", [1, False, None])
def test_retry_must_be_explicit_integer_zero(rows, tmp_path, retry):
    client = FakeClient([])
    client.max_retries = retry
    with pytest.raises(ValueError, match="retries"):
        matching.count_once(rows, client=client, destination=tmp_path / "counts", provenance={})
    assert not client.calls and not (tmp_path / "counts").exists()


def test_changed_body_is_rejected_before_any_call(rows, tmp_path):
    changed = deepcopy(rows)
    changed[1]["body"]["model"] = "different-model"
    client = FakeClient([])
    with pytest.raises(ValueError, match="hash"):
        matching.count_once(changed, client=client, destination=tmp_path / "counts", provenance={})
    assert not client.calls


def test_plan_is_deterministic_binds_rule_sources_and_request_hashes():
    plan = matching.build_plan(REPO)
    assert plan == matching.build_plan(REPO)
    assert plan["tolerance"] == {"numerator": 1, "denominator": 20}
    assert plan["inference_sessions_authorized"] == 0 and not plan["main_sample_admitted"]
    assert all("body" not in row for row in plan["requests"])
    assert matching.POLICY_PATH in plan["harness_and_world_sha256"]
    assert not any(".lake" in rel for rel in plan["harness_and_world_sha256"])


def test_prepare_cannot_overwrite_and_load_rejects_drift(tmp_path, monkeypatch):
    monkeypatch.setattr(matching, "PLAN_PATH", "plan.json")
    monkeypatch.setattr(matching, "build_plan", lambda _: {"tolerance": 5})
    matching.prepare(tmp_path)
    assert matching.load_plan(tmp_path) == {"tolerance": 5}
    with pytest.raises(FileExistsError):
        matching.prepare(tmp_path)
    monkeypatch.setattr(matching, "build_plan", lambda _: {"tolerance": 6})
    with pytest.raises(ValueError, match="drift"):
        matching.load_plan(tmp_path)


def test_symlink_destination_is_rejected_before_contact(rows, tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target)
    client = FakeClient([])
    with pytest.raises(ValueError, match="symlink"):
        matching.count_once(rows, client=client, destination=link, provenance={})
    assert not client.calls and not list(target.iterdir())


def test_real_sdk_serializes_count_requests_to_mock_transport_only(rows, tmp_path):
    # Optional SDK integration, still wholly offline; CI omits the provider SDK.
    anthropic = pytest.importorskip("anthropic")
    httpx2 = pytest.importorskip("httpx2")
    counts, requests = sample_counts(rows), []

    def handler(request):
        index = len(requests)
        requests.append(request)
        assert request.method == "POST"
        assert request.url.path == "/anthropic/v1/messages/count_tokens"
        assert json.loads(request.content) == rows[index]["body"]
        return httpx2.Response(200, json={"input_tokens": counts[rows[index]["id"]]},
                               headers={"request-id": f"synthetic-sdk-{index}"})

    with anthropic.AnthropicBedrockMantle(
        skip_auth=True, base_url=matching.BASE_URL, max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    ) as client:
        result = matching.count_once(rows, client=client, destination=tmp_path / "counts",
                                     provenance={"injected_client": True, "transport": "mock"})
    assert result["matching_passed"] and len(requests) == 11


def test_audit_reconstructs_without_a_client_and_detects_rehashed_tampering(rows, tmp_path, monkeypatch):
    plan = {"synthetic_auditor_test": True}
    dest = tmp_path / "evidence"
    # Explicitly synthetic test fixture for the real-provenance validation branch.
    provenance = {"plan_sha256": matching.sha(matching.encoded(plan)), "injected_client": False,
                  "client_class": "anthropic.lib.bedrock._mantle.AnthropicBedrockMantle",
                  "base_url": matching.BASE_URL, "max_retries": 0, "aws_profile": "main-account",
                  "aws_region": "us-east-1", "endpoint_path": "/v1/messages/count_tokens"}
    counts = sample_counts(rows)
    matching.count_once(rows, client=FakeClient([counts[r["id"]] for r in rows]), destination=dest, provenance=provenance)
    monkeypatch.setattr(matching, "EVIDENCE_PATH", "evidence")
    monkeypatch.setattr(matching, "load_plan", lambda _: plan)
    monkeypatch.setattr(matching, "catalog", lambda _: rows)
    assert matching.audit(tmp_path) == matching.summarize(rows, counts)
    result = json.loads((dest / "result.json").read_bytes())
    result["matching_passed"] = False
    (dest / "result.json").write_bytes(matching.encoded(result))
    manifest = json.loads((dest / "manifest.json").read_bytes())
    manifest["result.json"] = matching.sha((dest / "result.json").read_bytes())
    (dest / "manifest.json").write_bytes(matching.encoded(manifest))
    with pytest.raises(ValueError, match="does not reconstruct"):
        matching.audit(tmp_path)
