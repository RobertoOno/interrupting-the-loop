import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile

import pytest

spec = importlib.util.spec_from_file_location("restore_data", Path(__file__).resolve().parents[1] / "scripts/restore_published_data.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_paths_and_report_layout():
    assert module.destination("paper6/docs/a2c_results/read.json", "papers") == Path("docs/a2c_results/read.json")
    assert module.destination("report/evidence/reference_set_v1.jsonl", "report") == Path("docs/r1/reference_set_v1.jsonl")
    assert module.destination("report/review/rounds_2026-10-15_onward/freeze_status/data.json", "report") == Path("docs/r1/report_review_v2/freeze_status/data.json")
    assert module.destination("report/frozen/P1/flat.tex", "report") == Path("runs/r1/frozen/P1/flat.tex")
    assert module.destination("paper/scripts/code.py", "papers") is None
    for path in ["/etc/passwd", "root/../../file", "root/scripts/../../../file", "root\\..\\file"]:
        with pytest.raises(ValueError):
            module.destination(path, "papers")


def test_conflicts_and_symlinks_preserve_existing_data(tmp_path):
    rel = Path("docs/read.json")
    assert module.write_data(tmp_path, rel, b"original")
    assert not module.write_data(tmp_path, rel, b"original")
    with pytest.raises(ValueError):
        module.write_data(tmp_path, rel, b"different")
    assert (tmp_path / rel).read_bytes() == b"original"
    (tmp_path / "runs").symlink_to(tmp_path / "docs", target_is_directory=True)
    with pytest.raises(ValueError):
        module.write_data(tmp_path, Path("runs/other.json"), b"data")


def test_tar_restores_data_and_never_code(tmp_path):
    archive = tmp_path / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        for name, data in [("snapshot/docs/read.json", b"{}"), ("snapshot/scripts/payload.py", b"code")]:
            info = tarfile.TarInfo(name); info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    target = tmp_path / "target"; target.mkdir()
    assert module.restore(archive, "papers", target) == 1
    assert (target / "docs/read.json").read_bytes() == b"{}"
    assert not (target / "scripts").exists()


def test_bad_checksum_rejects_cached_file(tmp_path):
    cached = tmp_path / "archive.tar.gz"; cached.write_bytes(b"wrong")
    with pytest.raises(ValueError, match="checksum mismatch"):
        module.verified_download("unused", cached, "md5:" + hashlib.md5(b"right").hexdigest())
