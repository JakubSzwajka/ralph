---
status: draft
date: 2026-02-24
author: "kuba"
gh-issue: ~
---

# Homebrew Distribution — Package and Distribute Ralph via `brew install`

## Problem

Ralph currently lives as a local dev checkout. To use it in another repo you'd need to clone it, set up the Python environment, and install deps manually. There's no versioning, no release process, and no way for others (or yourself across machines) to just install and run it.

## Proposed Solution

Set up a full release pipeline so Ralph is installable via Homebrew:

1. **Package prep** — Clean up `pyproject.toml` (real description, classifiers, license, URLs). Pin a versioning strategy (CalVer or SemVer). Ensure `ralph` CLI entrypoint works from a clean install.

2. **GitHub Release workflow** — A GitHub Actions workflow triggered by version tags (`v*`). Builds a source distribution, creates a GitHub Release with the tarball attached, and computes the SHA256.

3. **Homebrew tap repo** — A new repo (`kuba-szwajka/homebrew-ralph` or similar) containing a formula that installs Ralph from the GitHub release tarball using Python/pip. The formula declares Python 3.13+ dependency and installs into a virtualenv (standard Homebrew Python formula pattern).

4. **Auto-update formula** — The release workflow dispatches to the tap repo to update the formula with the new version and SHA. This makes `brew upgrade ralph` pick up new versions automatically.

End result: `brew tap kuba-szwajka/ralph && brew install ralph` → working `ralph` command.

## Key Cases

- Fresh install on a new machine — `brew install` gets a working `ralph` CLI with all deps
- Upgrade — `brew upgrade ralph` picks up the latest release
- Tag-driven release — push `v0.2.0` tag → GH Actions builds release → formula updated
- Python version mismatch — formula declares `depends_on "python@3.13"`, Homebrew handles it
- Uninstall — `brew uninstall ralph` cleanly removes everything
- Private repo consideration — if Ralph repo is private, tap formula needs a download strategy (GitHub token or make repo public)

## Out of Scope

- PyPI publishing (can add later as separate PRD)
- Linux package managers (apt, dnf)
- Docker distribution
- Windows support
- Auto-update notifications within the CLI itself

## Open Questions

- Should the repo be public or private? (Homebrew taps work best with public repos)
- SemVer or CalVer for versioning?
- Tap repo name — `homebrew-ralph` or `homebrew-tap` (if you want a multi-tool tap)?
- License — what license for Ralph? (needed for pyproject.toml and formula)

## References

- Current package config: `pyproject.toml` (v0.1.0, entrypoint exists)
- CLI: `ralph/cli.py` (argparse, main entrypoint)
- Homebrew formula cookbook: https://docs.brew.sh/Formula-Cookbook
- Homebrew Python formula pattern: https://docs.brew.sh/Python-for-Formula-Authors
