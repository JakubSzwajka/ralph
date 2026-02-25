from __future__ import annotations

from pathlib import Path

from ralph.browser import DocDir, DocFile, scan_docs, scan_docs_flat


class TestScanDocs:
    def test_missing_docs_dir_returns_empty_tree(self, tmp_path: Path):
        tree = scan_docs(tmp_path)
        assert tree.children == []

    def test_empty_docs_dir_returns_empty_tree(self, tmp_path: Path):
        (tmp_path / "docs").mkdir()
        tree = scan_docs(tmp_path)
        assert tree.children == []

    def test_discovers_text_files(self, tmp_path: Path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "readme.md").write_text("# Hello\n")
        (docs / "config.yaml").write_text("key: val\n")
        (docs / "binary.bin").write_bytes(b"\x00\x01")

        tree = scan_docs(tmp_path)
        names = [c.path.name for c in tree.children]
        assert "readme.md" in names
        assert "config.yaml" in names
        assert "binary.bin" not in names

    def test_recursive_directory_structure(self, tmp_path: Path):
        docs = tmp_path / "docs"
        sub = docs / "prds" / "feature-a"
        sub.mkdir(parents=True)
        (sub / "README.md").write_text("# Feature A\n")
        (docs / "index.md").write_text("# Index\n")

        tree = scan_docs(tmp_path)
        top_names = [c.name if isinstance(c, DocDir) else c.path.name for c in tree.children]
        assert "index.md" in top_names
        assert "prds" in top_names

    def test_hidden_files_excluded(self, tmp_path: Path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / ".hidden.md").write_text("secret\n")
        (docs / "visible.md").write_text("public\n")

        tree = scan_docs(tmp_path)
        names = [c.path.name for c in tree.children if isinstance(c, DocFile)]
        assert "visible.md" in names
        assert ".hidden.md" not in names

    def test_empty_subdirs_excluded(self, tmp_path: Path):
        docs = tmp_path / "docs"
        (docs / "empty-sub").mkdir(parents=True)
        (docs / "has-file").mkdir()
        (docs / "has-file" / "notes.txt").write_text("hi\n")

        tree = scan_docs(tmp_path)
        dir_names = [c.name for c in tree.children if isinstance(c, DocDir)]
        assert "has-file" in dir_names
        assert "empty-sub" not in dir_names

    def test_sorted_dirs_first_then_files(self, tmp_path: Path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "zebra.md").write_text("z\n")
        sub = docs / "alpha"
        sub.mkdir()
        (sub / "a.md").write_text("a\n")
        (docs / "beta.md").write_text("b\n")

        tree = scan_docs(tmp_path)
        names = []
        for c in tree.children:
            names.append(c.name if isinstance(c, DocDir) else c.path.name)
        assert names[0] == "alpha"

    def test_custom_docs_dir(self, tmp_path: Path):
        custom = tmp_path / "my-docs"
        custom.mkdir()
        (custom / "file.md").write_text("hi\n")

        tree = scan_docs(tmp_path, docs_dir=custom)
        assert tree.name == "my-docs"
        assert len(tree.children) == 1

    def test_scan_docs_flat(self, tmp_path: Path):
        docs = tmp_path / "docs"
        sub = docs / "nested"
        sub.mkdir(parents=True)
        (docs / "top.md").write_text("top\n")
        (sub / "deep.txt").write_text("deep\n")

        flat = scan_docs_flat(tmp_path)
        paths = [f.path.name for f in flat]
        assert "top.md" in paths
        assert "deep.txt" in paths

    def test_relative_path_set(self, tmp_path: Path):
        docs = tmp_path / "docs"
        sub = docs / "sub"
        sub.mkdir(parents=True)
        (sub / "file.md").write_text("hi\n")

        flat = scan_docs_flat(tmp_path)
        assert flat[0].relative_path == "sub/file.md"

    def test_real_project_docs(self):
        project_root = Path(__file__).parent.parent.parent.parent
        tree = scan_docs(project_root)
        flat = scan_docs_flat(project_root)
        assert len(flat) > 0
        assert tree.name == "docs"
