<div align="center">

# Encre Agent Plugin Central Registry

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg?style=flat-square)](LICENSE)
[![Encre Agent](https://img.shields.io/badge/Encre%20Agent-plugin--market-181717?style=flat-square)](https://github.com/mf2023/Encre)

This repository is the **central repository of the Encre Agent plugin market**. It holds the
authoritative plugin index (one validated `catalog.json` describing every published plugin),
the per-plugin entry directory `catalog.d/`, the CI that gates and publishes them, and the
zero-dependency tooling behind both.

The index ships to clients as a plain data package on PyPI, versioned by this repo's release
pipeline (see below). The Encre Agent market backend never renders from the network: it
upgrades the index package once a day and displays what the validated document says.
Publishing here IS publishing to the market.

</div>

<h2 align="center">🧭 How the pipeline works</h2>

```
author machine                       this repository                    every Encre Agent
┌────────────────────┐   PR    ┌─────────────────────────┐   daily   ┌──────────────────────┐
│ encre-plugin build │ ──────► │ validate-catalog.yml    │ ────────► │ pip install -U ea-cwh │
│ encre-plugin verify│  merge  │   (schema + PyPI digest │  publish  │ read catalog.json     │
│ encre-plugin publish│ ─────► │    cross-check)         │ ────────► │ render the market     │
└────────────────────┘         │ publish-index.yml       │           │ install = pinned +    │
                               │   → PyPI (trusted pub.) │           │   sha256-verified     │
                               └─────────────────────────┘           └──────────────────────┘
```

1. A plugin is a normal Python package named **`ea-plugin-<name>`**, published to PyPI.
2. Its catalogue entry lands here as `catalog.d/<name>.json` via a PR opened by `encre-plugin publish`.
3. The PR gate merges all entries, validates the schema, and cross-checks the artifacts of
   every CHANGED entry on PyPI (the publish job always verifies the full catalog).
4. Merging triggers `publish-index.yml`, which regenerates `ea_cwh/catalog.json`, stamps a new
   index version and releases `ea-cwh` to PyPI. Agents pick it up on the next daily refresh.

<h2 align="center">🚀 Publishing a plugin with the CLI</h2>

The `encre-plugin` CLI (from the Encre repository, `cli/`) is the only supported way to enter
this registry. Five steps, ~10 minutes for a first release.

**Step 0 — Get the CLI**

`encre-plugin` ships as a single download-and-run executable for each OS
(Windows `.exe`; native binaries on macOS/Linux — built by
[`python build.py cli`](https://github.com/mf2023/Encre) in the Encre
repository). No `pip install` is required for the tool itself; it drives a
system Python (3.14+, standard for plugin authors) for the build/verify/publish
steps. Prefer the module form? `pip install ea-plugin-cli` installs the same CLI.

**Step 1 — Scaffold**

```bash
encre-plugin init my-toolkit
cd ea-plugin-my-toolkit
```

Creates a compliant skeleton: `pyproject.toml` with the
`[project.entry-points."ea.plugins"]` registration and `[tool.ea]` tier, a `plugin.py` with a
`create_plugin` factory, and a `ui/` directory for pre-compiled frontend assets.

**Step 2 — Implement**

Fill in the manifest (name, version, description, author, license, tags, permissions,
capabilities). Rules the CLI will enforce at build time are listed [below](#-submission-rules).

**Step 3 — Build and verify**

```bash
encre-plugin build      # policy check → wheel + sdist → sha256 every artifact
                        # writes dist/ea-build-info.json (your catalogue entry draft)
encre-plugin verify     # fresh temp venv, install the wheel, import the entry point,
                        # call the factory and echo the manifest back
```

`build` refuses to produce anything if a rule fails; `verify` proves the wheel is loadable
before PyPI ever sees it.

**Step 4 — Publish**

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=<your PyPI API token>   # scoped to ea-plugin-my-toolkit

encre-plugin publish                            # PyPI + registry PR, in one go
```

`publish` uploads to PyPI first, then clones (or re-syncs) this registry into a
local cache, writes `catalog.d/my-toolkit.json` on a fresh branch cut from
`main`, pushes it and files the PR with `gh`. One command, both halves of the
release. Flags: `--registry-dir` to use your own checkout, `--registry-url` to
target a fork, `--no-upload` for the PR half only, `--dry-run` to print instead
of doing anything.

**Step 5 — Merge**

CI validates the PR; after a maintainer merges, the index is rebuilt and published
automatically. Your plugin appears in every Encre Agent market within one refresh cycle
(≤ 24 h). From then on, every release is just steps 3–4 again with a bumped version.

<h2 align="center">📋 Submission rules</h2>

Enforced by `encre-plugin build` and again by `ea_cwh.validate_catalog` in CI — a squatted,
mis-versioned or tampered package can never merge:

| Rule | Detail |
|:------|:------|
| Reserved prefix | PyPI name must start with `ea-plugin-`; `name` and `pypi_package` are unique in the index |
| One plugin per wheel | exactly one `[project.entry-points."ea.plugins"]` entry |
| Version pinned | a concrete PEP 440 version, never a range; manifest version == pyproject version |
| Metadata complete | description, author, license non-empty; `min_encre_version` or `engines.encre` declared; tier is `user` |
| Digests required | every artifact ships a 64-hex `sha256`; the installer verifies the download against it before installing |
| UI pre-compiled | packages declaring UI must bundle `ui/` assets as package data — the market machine never runs a build |

The entry fields themselves are defined by `tools/regen_catalog.py` / `ea_cwh` validation —
`encre-plugin build` emits the correct shape for you, so hand-writing a `catalog.d/` file is
neither necessary nor encouraged.

<h2 align="center">🛡️ Why this is safe to auto-install</h2>

- The market installs **exactly** the version the index names, downloads it from PyPI, and
  refuses anything whose sha256 does not match the entry that survived human review.
- Freshly installed code is not executed at once: the plugin enters the registry's dynamic
  authorisation flow (`confirm_activation`) — import happens only at activation time.
- A failed activation rolls the ledger entry back; nothing half-installed stays behind.

<h2 align="center">🧰 Maintainer operations</h2>

| Task | How |
|:------|:------|
| Yank a plugin | set `"yanked": true` in its `catalog.d/<name>.json`, PR as usual — yanked rows never count as updates |
| Re-cut the index | Actions → `publish-index.yml` → *Run workflow* (validates + publishes without a catalog change) |
| Validate a catalog locally | `python tools/regen_catalog.py` (merge + schema) · `--check-pypi [names…]` adds the PyPI cross-check (no names = whole catalog) · `--out ea_cwh/catalog.json` writes it |
| PyPI trusted publisher | one-time: PyPI project `ea-cwh` → Publishing → add `mf2023/ea-cwh` / `publish-index.yml` / environment `pypi` |
| PRs from contributors | collaborators push branches directly; external authors fork + PR, or use `gh` after `gh auth login` |

<h2 align="center">📄 License</h2>

Apache License 2.0 — see [LICENSE](LICENSE). Part of the Encre Agent ecosystem by the Dunimd Team.
