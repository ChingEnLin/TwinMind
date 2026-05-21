from pathlib import Path

from twin_mind.ingestion.local_docs import LocalDocsLoader


def test_local_loader_reads_markdown(tmp_path: Path):
    (tmp_path / "a.md").write_text("# title\n\nbody")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.md").write_text("hello")

    docs = list(LocalDocsLoader(tmp_path).load())
    ids = sorted(d.id for d in docs)
    assert ids == ["a.md", "sub/b.md"]


def test_local_loader_handles_missing_dir(tmp_path: Path):
    docs = list(LocalDocsLoader(tmp_path / "nope").load())
    assert docs == []
