# Phase 1 — Standards Baseline

## Tier A: Code Quality (Python)

| Standard | Current Tool/Version | Source Citation |
|----------|---------------------|-----------------|
| **Linter/Formatter** | Ruff v0.16.1 (latest as of 2026-08) | PyPI, Astral blog — drops Black/flake8/isort |
| **Target Python Version** | py313 (project requires >=3.13) | pyproject.toml `requires-python = ">=3.13"` |
| **Line Length** | 100 (project config) | pyproject.toml `[tool.ruff] line-length = 100` |
| **Rule Selection** | E, W, F, I, N, W, UP, B, SIM, RUF | pyproject.toml `[tool.ruff.lint.select]` |
| **Type Checker** | mypy (strict mode enabled) | pyproject.toml `[tool.mypy] strict = true` |
| **Python Version for mypy** | 3.13 | pyproject.toml `[tool.mypy] python_version = "3.13"` |
| **myPy Strict Mode** | Enabled (`strict = true`) | pyproject.toml `[tool.mypy] strict = true` |
| **Test Framework** | pytest + pytest-asyncio | pyproject.toml `[tool.pytest.ini_options]` |
| **Package Manager/Lock** | uv (uv.lock present) | uv.lock at root |
| **Dependency Spec** | PEP 621 via pyproject.toml | pyproject.toml `[project]` |
| **Build Backend** | setuptools | pyproject.toml `[build-system]` |

**Note**: Project uses `ignore_missing_imports = true` in mypy — acceptable for third-party libs without stubs.

---

## Tier B: Documentation Standards

| Standard | Current Practice | Source Citation |
|----------|------------------|-----------------|
| **README** | Comprehensive with badges, architecture diagram, quickstart | README.md — has CI badge, ASCII arch diagram, quickstart |
| **CHANGELOG** | Keep a Changelog format v1.1.0 header | CHANGELOG.md header references Keep a Changelog 1.1.0 |
| **CHANGELOG Version** | **GAP** — Uses v1.1.0; v2.0.0 released June 2026 | keepachangelog.com v2.0.0 (June 7, 2026) |
| **License** | MIT (in LICENSE file, README badge) | LICENSE file, README |
| **CONTRIBUTING** | Present with conventional commits guidance | CONTRIBUTING.md |
| **CODE_OF_CONDUCT** | Contributor Covenant 2.1 | CODE_OF_CONDUCT.md |
| **SECURITY.md** | Present with reporting email | SECURITY.md |
| **SUPPORT.md** | Present | SUPPORT.md |
| **ADRs** | 0001-0011 in docs/adrs/ | docs/adrs/ directory |
| **API Docs** | mkdocs.yml present | mkdocs.yml at root |
| **Docstrings** | Google/NumPy style implied | CONTRIBUTING.md mentions "strict type hints" |
| **Interrogate/Docstring Coverage** | Not configured | No interrogate in pyproject.toml |

**Key Gap**: CHANGELOG references Keep a Changelog v1.1.0; v2.0.0 released June 7, 2026 (relaxes SemVer requirement, clarifies LLM-drafted changelogs).

---

## Tier C: Open Source Standards (Applies — MIT-licensed OSS public)

| Standard | Current Status | OSSF Scorecard / OSPS Baseline Source |
|----------|----------------|----------------------------------------|
| **LICENSE** | ✅ MIT at root | LICENSE file |
| **README** | ✅ Comprehensive | README.md |
| **CONTRIBUTING** | ✅ Present | CONTRIBUTING.md |
| **CODE_OF_CONDUCT** | ✅ Contributor Covenant 2.1 | CODE_OF_CONDUCT.md |
| **SECURITY.md** | ✅ Present with reporting email | SECURITY.md |
| **CHANGELOG** | ✅ Keep a Changelog format (v1.1.0) | CHANGELOG.md |
| **Branch Protection** | ❓ Not verified — CI runs on PRs | OSPS-AC-03 / Scorecard Branch-Protection |
| **Signed Commits** | ❌ Not enforced | OSPS-BR-06 / Scorecard Signed-Releases |
| **Dependency Pinning** | ✅ uv.lock at root | OSPS-QA-02 / Scorecard Pinned-Dependencies |
| **SBOM** | ❌ Not generated/published | Scorecard SBOM / OSPS-QA-02 |
| **Signed Releases** | ❌ No signed release artifacts | Scorecard Signed-Releases / OSPS-BR-06 |
| **Code Review Required** | ❓ PRs go through CI but review not enforced | Scorecard Code-Review |
| **Dependency Update Tool** | ❌ No Dependabot/Renovate config | Scorecard Dependency-Update-Tool |
| **Token Permissions** | ❓ GitHub workflow uses default tokens | Scorecard Token-Permissions |
| **Binary Artifacts** | ✅ None apparent | Scorecard Binary-Artifacts |
| **CII Best Practices** | ❌ Not enrolled | Scorecard CII Best Practices |
| **SPDX License Headers** | ❌ Missing from source files | REUSE/SPDX best practice |

**Key Gaps**: Branch protection not verified, no SBOM generation, no signed releases, no dependency update automation, no SPDX headers.

---

## Tier D: Enterprise / Deployment Standards

| Standard | Current Status | Source Citation |
|----------|----------------|-----------------|
| **Container: Multi-stage Build** | ❌ Single-stage Dockerfile | Docker best practices / hadolint |
| **Container: Non-root User** | ❌ No USER directive | CIS Docker Benchmark 4.1 |
| **Container: Base Image Pinning** | ❌ Tags only (`python:3.13`) | Digest pinning recommended |
| **Container: .dockerignore** | ✅ Present | Docker best practices |
| **Container: hadolint** | ❌ Not in CI | hadolint best practice |
| **SBOM Generation** | ❌ Not configured | CycloneDX/Syft best practice |
| **Dependency Scanning** | ❌ No pip-audit/safety in CI | OSPS-QA-02 / pip-audit |
| **Secrets Scanning** | ❌ No gitleaks/trufflehog in CI | gitleaks/trufflehog best practice |
| **Semantic Versioning** | ✅ v0.6.0 in pyproject.toml | SemVer 2.0.0 |
| **CI Pipeline** | ✅ GitHub Actions (ci.yml, migration-guard.yml) | GitHub Actions best practice |
| **CI: Lint+Type+Test** | ✅ ruff + mypy + pytest in CI | ci.yml |
| **CI: Caching** | ✅ pip cache + venv cache | ci.yml |
| **Makefile/Taskfile** | ✅ Makefile with install/lint/test targets | Makefile at root |
| **Install Script** | ✅ `pip install -e ".[dev]"` in CONTRIBUTING | CONTRIBUTING.md |
| **Dockerfile for Dev/Prod** | Dockerfile, Dockerfile.dev, docker-compose.yml | Root files |
| **Health Check** | ❌ No HEALTHCHECK in Dockerfile | Docker best practice |

---

## Tier E: RapidWebs-Specific Standards

| Standard | Current Status | Source |
|----------|----------------|--------|
| **SOUL.md Instruction Hierarchy** | ✅ In ~/.hermes/SOUL.md | ~/.hermes/SOUL.md |
| **.docs/ Planning Artifacts** | ✅ .hermes/plans/ with dated markdown | .hermes/plans/ |
| **ADR Numbering Scheme** | ✅ 0001-0011 in docs/adrs/ | docs/adrs/ |
| **Execute & Confirm Before "Fixed"** | ✅ Mandate in SOUL.md | SOUL.md |
| **RWDN Ansible Role Boundaries** | N/A — not infra-adjacent | — |
| **Worktree Worker Plugin** | ✅ In .hermes/plugins/ | .hermes/plugins/ |
| **Jules/Mistral Cloud Dispatch** | ✅ Documented in SOUL.md | SOUL.md Cloud Dispatch section |
| **Hermes Profiles** | ✅ Multiple profiles supported | .hermes/profiles/ |

---

## Summary: Standards Baseline Established

| Tier | Standards Researched | Key Gaps Identified |
|------|---------------------|---------------------|
| A: Code Quality | ✅ | Missing basedpyright/pyright, interrogate for docstring coverage |
| B: Documentation | ✅ | CHANGELOG references v1.1.0 (v2.0.0 exists) |
| C: Open Source | ✅ | No branch protection verified, no SBOM, no signed releases, no dependabot/renovate |
| D: Enterprise/Deploy | ✅ | Single-stage Dockerfile, no non-root user, no digest pinning, no hadolint, no SBOM/scanning |
| E: RapidWebs | ✅ | All conventions present |

**Ready for Phase 2 — Codebase Audit** with this baseline.