# Phase 2 — Codebase Audit Gap Report

## Executive Summary
**Audit Date**: 2026-08-04  
**Scope**: NexusAgent (Python 3.13+, src layout, MIT OSS, container deployment)  
**Baseline**: Phase 1 Standards Baseline table  
**Tools Executed**: ruff, mypy (partial), pip-audit/safety (missing), gitleaks/trufflehog (missing), hadolint (via Dockerfile analysis), interrogate (not run)

---

## Gap Report

| ID | Tier | Finding | Severity | Evidence | Recommended Fix |
|----|------|---------|----------|----------|-----------------|
| **G-001** | A | Ruff lint: 27 errors (16 fixable) | HIGH | `ruff check src/nexusagent tests` output — 27 errors including W293, UP035, RUF022, W292 | Run `ruff check --fix src/ tests` and `ruff format src/ tests` |
| **G-002** | A | Ruff format: 12+ files unformatted | HIGH | `ruff format --check src/ tests` — agent.py, dag.py, worker.py, pool.py, etc. | Run `ruff format src/ tests` |
| **G-003** | A | mypy: 10 type errors in worker module | HIGH | `mypy src/nexusagent/core/worker` — missing type annotations, Any returns, None callable | Add type annotations; fix `None` callable on line 258 |
| **G-004** | A | Missing basedpyright/pyright for additional type coverage | MEDIUM | Phase 1 baseline recommends both mypy + basedpyright | Add basedpyright to dev deps and CI |
| **G-005** | A | No interrogate/docstring coverage enforcement | MEDIUM | Not in pyproject.toml or CI | Add `interrogate` to dev deps; configure in pyproject.toml |
| **G-006** | A | Unused imports detected (AsyncMock, logging) | LOW | `ruff check` output | Remove unused imports |
| **G-007** | A | Local `import math` inside function in memory_files.py | NIT | `ruff check` output shows UP035 | Move import to module top (already partially fixed) |
| **G-008** | A | `__all__` not sorted in memory_utils.py | NIT | `ruff check` output RUF022 | Sort `__all__` alphabetically |

| ID | Tier | Finding | Severity | Evidence | Recommended Fix |
|----|------|---------|----------|----------|-----------------|
| **G-009** | B | CHANGELOG.md references Keep a Changelog v1.1.0; v2.0.0 released June 2026 | MEDIUM | CHANGELOG.md header: "format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)" | Update header to v2.0.0 URL |
| **G-010** | B | No interrogate configuration for docstring coverage | MEDIUM | Not in pyproject.toml | Add `[tool.interrogate]` section |
| **G-011** | B | No SPDX license headers in source files | LOW | Spot-check: src/nexusagent/core/worker/worker.py has no SPDX header | Add SPDX-License-Identifier headers |
| **G-012** | B | No automated docstring style enforcement (pydocstyle) | LOW | Not in pyproject.toml or CI | Add pydocstyle or ruff rule for docstrings |

| ID | Tier | Finding | Severity | Evidence | Recommended Fix |
|----|------|---------|----------|----------|-----------------|
| **G-013** | C | Branch protection not verified/enforced in repo settings | BLOCKER | CI runs on PRs but no evidence of required reviews, status checks, force-push prevention | Enable GitHub branch protection: require PR, 1+ review, status checks, no force push |
| **G-014** | C | No signed commits enforcement | HIGH | No commit signing requirement | Enable vigilant mode / require signed commits |
| **G-015** | C | No SBOM generation in CI/pipeline | HIGH | No cyclonedx-py, syft, or trivy SBOM step in .github/workflows/ci.yml | Add SBOM generation (cyclonedx-py or syft) to CI; publish as release artifact |
| **G-016** | C | No signed release artifacts | HIGH | No cosign/sigstore signing in release workflow | Add cosign signing to release pipeline |
| **G-017** | C | No dependency update automation (Dependabot/Renovate) | HIGH | No dependabot.yml or renovate.json | Add dependabot.yml with weekly updates + auto-merge for patch |
| **G-018** | C | No SPDX license headers in source files | MEDIUM | No `SPDX-License-Identifier: MIT` headers | Add `SPDX-License-Identifier: MIT` to all .py files |
| **G-019** | C | No dependency update tool (Dependabot/Renovate) | HIGH | No .github/dependabot.yml or renovate.json | Add dependabot.yml with weekly schedule |
| **G-020** | C | Token permissions not minimized in GitHub Actions | MEDIUM | ci.yml uses default GITHUB_TOKEN permissions | Add `permissions:` block to workflow jobs |

| ID | Tier | Finding | Severity | Evidence | Recommended Fix |
|----|------|---------|----------|----------|-----------------|
| **G-021** | D | Dockerfile: Single-stage (no multi-stage build) | BLOCKER | Dockerfile: single FROM, copies all source, runs as root | Convert to multi-stage: builder → runtime (distroless/alpine) |
| **G-022** | D | Dockerfile: Runs as root (no USER directive) | BLOCKER | Dockerfile has no USER directive; defaults to root | Add non-root user: `RUN addgroup -S app && adduser -S app -G app` + `USER app` |
| **G-023** | D | Dockerfile: Base image pinned by tag only (`python:3.13-slim`) | HIGH | `FROM python:3.13-slim` — tag is mutable | Pin by digest: `python:3.13-slim@sha256:...` |
| **G-024** | D | Missing .dockerignore file | HIGH | No .dockerignore at root (empty file found) | Create .dockerignore excluding .git, __pycache__, tests, .env, etc. |
| **G-025** | D | No hadolint in CI | HIGH | No hadolint step in .github/workflows/ci.yml | Add hadolint step to CI |
| **G-026** | D | No SBOM generation in CI | HIGH | No cyclonedx-py/syft step in CI | Add SBOM generation to CI; upload as artifact |
| **G-027** | D | No dependency vulnerability scanning in CI | HIGH | pip-audit, safety, osv-scanner not installed or in CI | Add pip-audit or osv-scanner to CI |
| **G-028** | D | No secrets scanning in CI | HIGH | gitleaks/trufflehog not in CI | Add gitleaks or trufflehog to CI |
| **G-029** | D | No container image vulnerability scanning | HIGH | No Trivy/Grype in CI | Add Trivy or Grype scan to CI |
| **G-030** | D | Dockerfile: COPY . . pattern without .dockerignore | HIGH | No .dockerignore means entire repo sent to build context | Create .dockerignore |
| **G-031** | D | Dockerfile: apt-get without pinned versions | MEDIUM | `apt-get install -y gcc libsqlite3-dev` — no version pins | Pin versions: `gcc=4:13.2.0-1 libsqlite3-dev=3.45.1-1` |
| **G-032** | D | Dockerfile: No non-root user creation | BLOCKER | No user creation before USER directive | Add `RUN addgroup -S app && adduser -S app -G app` |
| **G-033** | D | Makefile: No SBOM target | LOW | Makefile has no `sbom` target | Add `sbom:` target to Makefile |
| **G-034** | D | CI: No hadolint step | HIGH | ci.yml has no hadolint step | Add hadolint action to ci.yml |
| **G-035** | D | CI: No dependency vulnerability scan | HIGH | ci.yml has no pip-audit/osv-scanner | Add pip-audit or osv-scanner step |
| **G-036** | D | CI: No secrets scanning | HIGH | ci.yml has no gitleaks/trufflehog | Add gitleaks action |
| **G-037** | D | CI: No container scanning | HIGH | ci.yml has no Trivy/Grype | Add Trivy action |
| **G-037** | D | CI: No SBOM generation/upload | HIGH | ci.yml has no SBOM step | Add SBOM generation + upload as artifact |
| **G-038** | D | Token permissions not minimized in GitHub Actions | MEDIUM | ci.yml has no `permissions:` block | Add `permissions: contents: read` etc. |
| **G-039** | D | Missing Makefile `sbom` target | LOW | Makefile missing `sbom:` target | Add `sbom:` target |
| **G-040** | D | Missing Makefile `docker-lint` target | LOW | Makefile missing `docker-lint:` target | Add `docker-lint:` target running hadolint |
| **G-041** | D | Missing Makefile `security-scan` target | LOW | Makefile `security:` only runs ruff S,B | Add `security-scan:` with pip-audit, gitleaks |
| **G-042** | D | Dockerfile: No HEALTHCHECK timeout optimization | LOW | HEALTHCHECK uses 5s timeout; could be lower | Tune timeout |
| **G-043** | D | Dockerfile: COPY pattern copies entire src/ before pip install | LOW | COPY src/ before pip install -e . | Reorder: copy pyproject.toml first, then src/ |

| ID | Tier | Finding | Severity | Evidence | Recommended Fix |
|----|------|---------|----------|----------|-----------------|
| **G-044** | E | SOUL.md governance present but no check for "execute before claim fixed" in CI | LOW | SOUL.md mandates "execute code and confirm real output before writing 'fixed'" but no CI gate | Add pre-commit/CI check that fails if "fixed" claimed without test evidence |
| **G-045** | E | No enforcement of ADR numbering in CI | LOW | ADRs 0001-0011 exist but no lint for numbering | Add ADR linter or script |

---

## Summary by Severity

| Severity | Count |
|----------|-------|
| BLOCKER | 4 (G-013, G-021, G-022, G-032) |
| HIGH | 14 (G-001, G-002, G-003, G-013, G-014, G-015, G-016, G-017, G-019, G-021, G-022, G-023, G-024, G-025, G-026, G-027, G-028, G-029, G-030, G-031, G-034, G-035, G-036, G-037, G-038) |
| MEDIUM | 9 (G-004, G-005, G-009, G-010, G-014, G-016, G-020, G-031, G-038) |
| LOW | 6 (G-006, G-007, G-008, G-011, G-012, G-033, G-039, G-040, G-041) |
| NIT | 2 (G-007, G-008) |

**Total Findings: 45**

---

## Critical Path (BLOCKERs First)

1. **G-013** — Enable GitHub branch protection (require PR, review, status checks, no force push)
2. **G-021, G-022, G-032** — Convert Dockerfile to multi-stage, add non-root user, add USER directive
3. **G-024, G-030** — Create .dockerignore (removes root cause for G-030)

These 4 BLOCKERs unblock the rest of the remediation.