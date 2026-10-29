import fcntl
import json
import multiprocessing
import os

import pytest

from creative_machine.formal_routes.transfer_worker_v1 import WorkerClaim, WorkerOwnershipError

PLAN = "a" * 64


def contender(registry, queue):
    try:
        with WorkerClaim(registry, "one-run", PLAN):
            queue.put("won")
    except FileExistsError:
        queue.put("blocked")


def crash(registry):
    with WorkerClaim(registry, "crashed", PLAN):
        os._exit(7)


def test_lifetime_receipt_and_permanent_no_restart(tmp_path):
    registry = tmp_path / "claims"
    with WorkerClaim(registry, "one-run", PLAN) as owner:
        receipt = owner.assert_owned()
        assert receipt["pid"] == os.getpid() and receipt["execution_plan_sha256"] == PLAN
        assert not receipt["restart_permitted"] and not receipt["inference_admitted"]
        assert len(owner.sha256) == 64
        receipt["run_id"] = "tampered return value"
        assert owner.assert_owned()["run_id"] == "one-run"
        with (registry / "one-run.claim.json").open() as handle:
            with pytest.raises(BlockingIOError):
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert (registry / "one-run.claim.json").exists()
    with pytest.raises(WorkerOwnershipError): owner.assert_owned()
    with pytest.raises(WorkerOwnershipError): owner.__enter__()
    with pytest.raises(FileExistsError):
        with WorkerClaim(registry, "one-run", "b" * 64): pass


def test_exception_does_not_erase_intent(tmp_path):
    with pytest.raises(RuntimeError, match="fixture"):
        with WorkerClaim(tmp_path, "one-run", PLAN): raise RuntimeError("fixture")
    with pytest.raises(FileExistsError):
        with WorkerClaim(tmp_path, "one-run", PLAN): pass


def test_competing_processes_have_exactly_one_admission(tmp_path):
    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    workers = [ctx.Process(target=contender, args=(tmp_path, queue)) for _ in range(6)]
    for process in workers: process.start()
    results = [queue.get(timeout=15) for _ in workers]
    for process in workers:
        process.join(timeout=15)
        assert process.exitcode == 0
    assert results.count("won") == 1 and results.count("blocked") == 5


def test_crashed_process_cannot_be_replaced_by_a_new_worker(tmp_path):
    process = multiprocessing.get_context("spawn").Process(target=crash, args=(tmp_path,))
    process.start()
    process.join(timeout=15)
    assert process.exitcode == 7
    with pytest.raises(FileExistsError):
        with WorkerClaim(tmp_path, "crashed", PLAN): pass


@pytest.mark.parametrize("kind", ("bytes", "replacement", "symlink", "hardlink", "parent"))
def test_owner_detects_lost_or_modified_claim(tmp_path, kind):
    registry = tmp_path / "registry"
    with WorkerClaim(registry, "one-run", PLAN) as owner:
        path = registry / "one-run.claim.json"
        if kind == "bytes": path.write_bytes(path.read_bytes().replace(b'"pid"', b'"PID"'))
        elif kind == "replacement":
            replacement = registry / "replacement"
            replacement.write_bytes(path.read_bytes())
            os.replace(replacement, path)
        elif kind == "symlink":
            path.rename(registry / "old")
            path.symlink_to(registry / "old")
        elif kind == "hardlink": os.link(path, registry / "linked")
        else:
            registry.rename(tmp_path / "old-registry")
            registry.mkdir()
        with pytest.raises(WorkerOwnershipError): owner.assert_owned()


@pytest.mark.parametrize("run_id", ("../escape", "", "a/b", "a" * 121, None))
def test_unsafe_id_never_creates_files(tmp_path, run_id):
    with pytest.raises(WorkerOwnershipError): WorkerClaim(tmp_path, run_id, PLAN)
    assert list(tmp_path.iterdir()) == []


def test_symlink_registry_is_not_followed(tmp_path):
    (tmp_path / "actual").mkdir()
    (tmp_path / "linked").symlink_to(tmp_path / "actual", target_is_directory=True)
    with pytest.raises(OSError):
        with WorkerClaim(tmp_path / "linked", "one-run", PLAN): pass
    assert list((tmp_path / "actual").iterdir()) == []


def test_fork_child_cannot_assert_or_release_parent_ownership(tmp_path):
    with WorkerClaim(tmp_path, "one-run", PLAN) as owner:
        pid = os.fork()
        if pid == 0:
            try:
                try: owner.assert_owned()
                except WorkerOwnershipError: pass
                else: os._exit(2)
                owner.close()
                os._exit(0)
            except BaseException:
                os._exit(3)
        _, status = os.waitpid(pid, 0)
        assert os.waitstatus_to_exitcode(status) == 0
        owner.assert_owned()
        with (tmp_path / "one-run.claim.json").open() as handle:
            with pytest.raises(BlockingIOError): fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_partial_creation_is_preserved_after_fsync_failure(tmp_path, monkeypatch):
    def fail(fd): raise OSError("fixture fsync failure")
    monkeypatch.setattr(os, "fsync", fail)
    with pytest.raises(OSError):
        with WorkerClaim(tmp_path, "one-run", PLAN): pass
    assert json.loads((tmp_path / "one-run.claim.json").read_text())["run_id"] == "one-run"
    with pytest.raises(FileExistsError):
        with WorkerClaim(tmp_path, "one-run", PLAN): pass
