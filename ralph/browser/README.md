# ralph/browser

PRD discovery and scanning. No TUI dependencies — pure filesystem operations.

## How it works

```
docs/prds/
├── feature-a/
│   ├── README.md    ← parsed for frontmatter (status, gh-issue) and H1 title
│   └── tasks.md     ← discovered as task file
├── feature-b/
│   ├── README.md
│   ├── tasks.md
│   └── stories.md
└── ...
```

`scan_prds(root)` walks `docs/prds/*/README.md`, parses each one, and returns a list of `PrdInfo` objects sorted by slug.

## Module layout

| File | Purpose |
|---|---|
| `scanner.py` | `PrdInfo` dataclass, `scan_prds()`, frontmatter/title parsing |

## PrdInfo

```python
@dataclass
class PrdInfo:
    slug: str           # directory name
    title: str          # H1 heading or slug fallback
    status: str         # frontmatter "status" or "unknown"
    path: Path          # absolute path to README.md
    task_files: list    # .md files in the dir (excluding README)
    gh_issue: str|None  # frontmatter "gh-issue" URL
```

## Usage

```python
from ralph.browser import scan_prds, PrdInfo

prds = scan_prds(Path.cwd())
for prd in prds:
    print(f"{prd.slug}: {prd.title} [{prd.status}]")
```
