from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

TEXT_EXTENSIONS = frozenset(
    {
        ".md",
        ".txt",
        ".rst",
        ".yaml",
        ".yml",
        ".toml",
        ".json",
        ".cfg",
        ".ini",
        ".csv",
        ".log",
        ".py",
        ".sh",
        ".env.example",
    }
)


@dataclass
class DocFile:
    path: Path
    relative_path: str


@dataclass
class DocDir:
    name: str
    path: Path
    children: list[DocDir | DocFile]


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter delimited by ``---`` lines.

    Returns (metadata_dict, body_without_frontmatter).
    """
    if not text.startswith("---"):
        return {}, text

    lines = text.split("\n")
    end_line: int | None = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end_line = i
            break

    if end_line is None:
        return {}, text

    meta: dict[str, str] = {}
    for line in lines[1:end_line]:
        line = line.strip()
        if ": " in line:
            key, _, value = line.partition(": ")
            meta[key.strip()] = value.strip().strip("\"'")
        elif line.endswith(":"):
            meta[line[:-1].strip()] = ""

    body = "\n".join(lines[end_line + 1 :])
    return meta, body


def _is_text_file(p: Path) -> bool:
    return p.suffix in TEXT_EXTENSIONS


def scan_docs(root: Path, docs_dir: Path | None = None) -> DocDir:
    if docs_dir is None:
        docs_dir = root / "docs"

    return _scan_directory(docs_dir, docs_dir)


def _scan_directory(directory: Path, base: Path) -> DocDir:
    children: list[DocDir | DocFile] = []

    if not directory.exists():
        return DocDir(name=directory.name, path=directory, children=[])

    entries = sorted(
        directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
    )

    for entry in entries:
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            sub = _scan_directory(entry, base)
            if sub.children:
                children.append(sub)
        elif entry.is_file() and _is_text_file(entry):
            rel = str(entry.relative_to(base))
            children.append(DocFile(path=entry, relative_path=rel))

    return DocDir(name=directory.name, path=directory, children=children)


def scan_docs_flat(root: Path, docs_dir: Path | None = None) -> list[DocFile]:
    tree = scan_docs(root, docs_dir)
    result: list[DocFile] = []
    _flatten(tree, result)
    return result


def _flatten(node: DocDir, acc: list[DocFile]) -> None:
    for child in node.children:
        if isinstance(child, DocFile):
            acc.append(child)
        else:
            _flatten(child, acc)
