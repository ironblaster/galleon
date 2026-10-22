# Contributing to Galleon

Thanks for wanting to join the crew! ⛵

## Ground rules

- **Upstream images only.** Galleon configures the official images through their public APIs. No forks, no patched binaries.
- **Idempotent or it doesn't ship.** Every bootstrap step must be safe to run twice. CI runs `./galleon bootstrap` a second time to prove it.
- **No secrets in presets.** Credentials are always `${GALLEON_IDX_*}` placeholders resolved from `.env`.
- **Stdlib first.** The `core/` package depends only on the Python standard library and PyYAML.

## What your PR must pass

Merging into `main` requires all of these, enforced by branch protection:

- **Checks:** lint (ruff, shellcheck, hadolint, preset secret check, compose validation), the voyage test (full stack plus idempotency), CodeQL, Gitleaks, dependency review, Trivy, zizmor and a conventional PR title (`feat: …`, `fix: …`, `preset: …`)
- **Review:** an approving review from a code owner, with every conversation resolved
- **History:** linear history (squash or rebase), no force-pushes

Workflows on PRs from first-time and outside contributors only run after a maintainer approves them. Never add a workflow that uses `pull_request_target` or that checks out PR code with secrets.

Run the same checks locally with `pre-commit install`.

## Dev loop

```bash
./galleon init --yes
./galleon up
# edit core/galleon_core/*.py, then:
docker compose build galleon && ./galleon bootstrap
tests/e2e.sh
```

Lint before pushing:

```bash
shellcheck galleon tests/*.sh
ruff check core
```

## Adding a service

1. Add it to `compose.yaml` (or to a profile if it's optional).
2. Seed what you can before boot in `seed.py`: keys, passwords, folders.
3. Add a client module in `core/galleon_core/` and a step in `bootstrap.py`.
4. Add an assertion to `tests/e2e.sh`.
5. Document it in the README tables.

## Adding an indexer preset

Create `presets/indexers/<name>.yml` (copy an existing file). Use Prowlarr definition ids from [Prowlarr/Indexers](https://github.com/Prowlarr/Indexers). Mark any indexer behind Cloudflare with `flaresolverr: true`.
