"""Request-bound worker/financial checks for the unchanged session runners.

This is not a launcher or scientific admission. The host supplies an already
admitted cell and client; this layer constructs neither credentials nor clients.
Receipts document host observations, not authenticated provider provenance.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import importlib.metadata
import math
import os
from pathlib import Path
import time

from .bedrock_runner import TokenBudget
from . import production_runner_v1 as production
from . import recipient_runner_v1 as recipient
from .production_audit_v1 import _snapshot
from .transfer_budget_v1 import TransferBudget
from .transfer_design_v1 import encoded, matrix, sha
from .transfer_worker_v1 import WorkerClaim

VERSION = "p3_transfer_transport_v1"
ENDPOINT = "https://bedrock-mantle.us-east-1.api.aws/anthropic"
SDK_VERSION = "1.4.0"


class TransportGateError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise TransportGateError(message)


def validate_experimental_client(client, config):
    # No credential resolution or network call. Do not log key/header values.
    from anthropic import AnthropicBedrockMantle
    require(type(client) is AnthropicBedrockMantle, "native Mantle client required")
    require(importlib.metadata.version("anthropic") == SDK_VERSION, "SDK version drift")
    require(str(client.base_url).rstrip("/") == ENDPOINT, "provider endpoint drift")
    require(client.aws_profile == config.aws_profile and client.aws_region == config.aws_region,
            "provider profile/region drift")
    require(client.skip_auth is False and client._use_sigv4 is True and client.api_key is None,
            "AWS profile SigV4 authentication required")
    require(all(getattr(client, name) is None for name in
                ("aws_access_key", "aws_secret_key", "aws_session_token")), "explicit credential override forbidden")
    require(type(client.max_retries) is int and client.max_retries == 0, "SDK retries forbidden")


class ProtectedSession:
    """Single-use messages guard; retains the native client's class in raw traces.

    Reconciliation supplier returns (receipt, externally retained hash). Each
    operation rechecks it, rather than trusting an admission-time snapshot.
    Any error permanently closes admissions on this guard. The caller must halt
    the batch; this class neither retries nor releases its financial reservation.
    """
    def __init__(self, client, *, owner: WorkerClaim, budget: TransferBudget,
                 reservation: dict, expected_reservation_sha256: str,
                 reconciliation_supplier, permitted_reconcilers: tuple[str, ...],
                 cell_id: str, initial_request: dict, artifacts: Path):
        require(isinstance(owner, WorkerClaim) and isinstance(budget, TransferBudget), "worker/budget required")
        cells = {c["cell_id"]: c for c in matrix()}
        require(cell_id in cells, "unknown matrix cell")
        self.cell = cells[cell_id]
        self.config = production.production_config()
        self.builder = (production.build_production_request if self.cell["role"] == "proposer"
                        else recipient.build_recipient_request)
        self.initial = deepcopy(initial_request)
        messages = self.initial.get("messages")
        require(isinstance(messages, list) and len(messages) == 1
                and set(messages[0]) == {"role", "content"} and messages[0]["role"] == "user"
                and isinstance(messages[0]["content"], str) and bool(messages[0]["content"]), "initial request schema")
        require(encoded(self.initial) == encoded(self.builder(messages, self.config)), "initial interface drift")
        self.client, self.owner, self.budget = client, owner, budget
        self.reservation = deepcopy(reservation)
        self.reservation_sha = expected_reservation_sha256
        self.reconcile, self.allowlist = reconciliation_supplier, permitted_reconcilers
        self.artifacts = Path(artifacts)
        self.original = client.messages
        require(not isinstance(self.original, ProtectedSession), "client already guarded")
        self._attempted = self._entered = self._failed = self._inflight = False
        self._terminal = False
        self._counted_body = self._next_reservation = None
        self._turns = self._sequence = 0
        self._head = None
        self._records = {}
        self.tokens = TokenBudget(self.config)

    def _client_check(self):
        require(type(self.client.max_retries) is int and self.client.max_retries == 0, "SDK retry configuration changed")
        if self.budget.data_kind == "experimental":
            validate_experimental_client(self.client, self.config)

    def _financial_check(self):
        reconciliation, reference = self.reconcile()
        return self.budget.check_before_request(self.owner, self.reservation,
            expected_reservation_sha256=self.reservation_sha, reconciliation=reconciliation,
            expected_reconciliation_sha256=reference, permitted_reconcilers=self.allowlist)

    def _save(self, name, value):
        self._files_check()
        data = encoded(value)
        production._write_new(self.artifacts / name, data)
        fd = os.open(self.artifacts, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        self._records[name] = sha(data)
        self._files_check()

    def _files_check(self):
        info = self.artifacts.stat(follow_symlinks=False)
        require((info.st_dev, info.st_ino) == self._directory_identity, "transport directory replaced")
        files, directories = _snapshot(self.artifacts)
        require(not directories and {name: sha(data) for name, data in files.items()} == self._records,
                "transport evidence changed")

    def __enter__(self):
        require(not self._attempted, "session guard cannot be reused")
        self._attempted = True
        self._client_check()
        financial = self._financial_check()
        self.artifacts.mkdir(exist_ok=False)
        info = self.artifacts.stat(follow_symlinks=False)
        self._directory_identity = (info.st_dev, info.st_ino)
        self._save("binding.json", {"version": VERSION, "data_kind": self.budget.data_kind,
            "cell_id": self.cell["cell_id"], "execution_plan_sha256": self.owner.plan_sha256,
            "worker_claim_sha256": self.owner.sha256, "reservation_sha256": self.reservation_sha,
            "initial_request_sha256": sha(encoded(self.initial)), "config": asdict(self.config),
            "admission_financial_check": financial, "provider_authenticated": False})
        self._started = time.monotonic()
        self.client.messages = self
        self._entered = True
        return self.client

    def _event(self, kind, **payload):
        self._sequence += 1
        row = {"seq": self._sequence, "previous_sha256": self._head, "event": kind,
               "at": datetime.now(timezone.utc).isoformat(), **payload}
        name = f"{self._sequence:04d}.json"
        self._save(name, row)
        self._head = self._records[name]

    def _check(self):
        require(self._entered and not self._failed and not self._inflight and not self._terminal,
                "session guard closed, failed, terminal or reentrant")
        require(self.client.messages is self, "messages guard replaced")
        self.owner.assert_owned()
        self._client_check()
        self._files_check()
        require(time.monotonic() - self._started < self.config.timeout_seconds, "session deadline passed")

    def _call(self, method, arguments):
        try:
            self._check()
            body = deepcopy(arguments)
            timeout = body.pop("timeout", None)
            ceiling = production.COUNT_TIMEOUT_SECONDS if method == "count_tokens" else self.config.request_timeout_seconds
            require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= ceiling, "request timeout drift")
            if method == "count_tokens":
                require(self._counted_body is None and self._turns < self.config.max_turns, "count/create sequence or turn ceiling")
                messages = body.get("messages")
                require(isinstance(messages, list) and bool(messages) and messages[0] == self.initial["messages"][0], "initial input changed")
                require(encoded(body) == encoded(self.builder(messages, self.config)), "request interface drift")
                self._turns += 1
            else:
                require(self._counted_body is not None and self._next_reservation is not None, "create without admitted native count")
                expected = {**self._counted_body, "max_tokens": self._next_reservation[1]}
                require(encoded(body) == encoded(expected), "count/create request drift or token ceiling")
            financial = self._financial_check()
            self._event("before_request", method=method, turn=self._turns,
                        body_sha256=sha(encoded(body)), timeout_seconds=timeout, financial_check=financial)
            self.owner.assert_owned()
            self._inflight = True
            response = getattr(self.original, method)(**deepcopy(arguments))
            self._inflight = False
            # Archive completion before validation; errors preserve both sides.
            if method == "count_tokens":
                counted = response.input_tokens
                self._event("after_request", method=method, turn=self._turns, input_tokens=counted)
                require(type(counted) is int and counted >= 0, "invalid native count")
                self._counted_body = body
                self._next_reservation = self.tokens.reserve(counted)
            else:
                payload = response.model_dump(mode="json", exclude_none=True)
                self._event("after_request", method=method, turn=self._turns,
                            response_sha256=sha(encoded(payload)), response=payload)
                usage = payload["usage"]
                require(isinstance(usage, dict) and {"input_tokens", "output_tokens"} <= set(usage), "missing provider usage")
                require(all(type(usage.get(k, 0)) is int and usage.get(k, 0) >= 0 for k in production.USAGE_FIELDS), "invalid provider usage")
                billable_input = usage["input_tokens"] + 2 * usage.get("cache_creation_input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
                self.tokens.settle(self._next_reservation, billable_input, usage["output_tokens"])
                require(isinstance(payload.get("model"), str) and payload["model"].removeprefix("anthropic.")
                        == self.config.model.removeprefix("anthropic."), "response model drift")
                self._terminal = payload.get("stop_reason") != "tool_use"
                self._counted_body = self._next_reservation = None
            self.owner.assert_owned()
            require(not self._failed, "nested operation failed; session remains closed")
            return response
        except Exception:
            self._failed = True
            self._inflight = False
            raise

    def count_tokens(self, **kwargs):
        return self._call("count_tokens", kwargs)

    def create(self, **kwargs):
        return self._call("create", kwargs)

    def __exit__(self, exc_type, exc, traceback):
        self._entered = False
        # Do not restore an unguarded messages interface to a used client.
        # The host closes the actual client after this single cell.
        self._save("closure.json", {"version": VERSION, "data_kind": self.budget.data_kind,
            "events": self._sequence, "head_sha256": self._head, "files": dict(self._records),
            "failed": self._failed or exc_type is not None, "provider_authenticated": False,
            "external_reservation_must_remain_open": True})
        return False
