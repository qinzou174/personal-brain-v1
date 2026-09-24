# Dependency/version baseline for Personal Brain V1

Verified 2026-09-23 Asia/Shanghai, before project dependency locking. This records **candidate exact versions and upstream compatibility evidence**, not installed packages, a successful lock resolution, or real-client interoperability.

## Observed platform

- Target: Ubuntu 24.04.4 x86-64; Python `3.12.3`; Docker `29.7.1`; Compose `v5.3.1` (read-only commands in [environment report](environment-report.md)).
- Windows development Python `3.12.0`, uv `0.12.6`; production artifacts must resolve for Linux x86-64 Python 3.12, not just Windows.
- Database candidate: [PostgreSQL 18.6](https://www.postgresql.org/docs/release/), a supported stable minor as of verification, with [pgvector 0.8.6](https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md). The maintainer-published [0.8.6-pg18-trixie image](https://hub.docker.com/r/pgvector/pgvector/tags?name=0.8.6-pg18-trixie) lists linux/amd64. Select and verify the immutable platform digest before T042; a mutable tag is not the deployment pin.

## Python direct-dependency candidates

The linked PyPI JSON metadata is the package registry's published `version`, `requires_python`, and dependency metadata observed on the verification date. Every selected package states Python 3.12 support by its declared range except `jieba`, which does not declare a range and therefore requires an execution test before lock acceptance.

| Package / role | Candidate exact pin | Declared Python compatibility / relevant intersection | Primary metadata |
|---|---|---|---|
| FastAPI / ASGI | `fastapi==0.141.1` | `>=3.10`; requires Pydantic `>=2.9.0` | [PyPI](https://pypi.org/pypi/fastapi/json) |
| Pydantic / validation | `pydantic==2.13.5` | `>=3.9`; satisfies FastAPI and MCP v2 `>=2.12.0` | [PyPI](https://pypi.org/pypi/pydantic/json) |
| Pydantic Settings / config | `pydantic-settings==2.15.0` | `>=3.10` | [PyPI](https://pypi.org/pypi/pydantic-settings/json) |
| SQLAlchemy / UoW | `SQLAlchemy==2.0.54` | `>=3.7`; satisfies Alembic `>=2.0` | [PyPI](https://pypi.org/pypi/SQLAlchemy/json), [official 2.0 docs](https://docs.sqlalchemy.org/en/20/intro.html) |
| Alembic / migrations | `alembic==1.20.0` | `>=3.10`; requires SQLAlchemy `>=2.0` | [PyPI](https://pypi.org/pypi/alembic/json) |
| MCP Python SDK / stdio + HTTP | `mcp==2.2.0` | `>=3.10`; requires Pydantic `>=2.12.0`, lock-stepped `mcp-types==2.2.0` | [PyPI](https://pypi.org/pypi/mcp/json), [SDK release](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.2.0) |
| PostgreSQL driver | `psycopg[binary]==3.3.6` | `>=3.10`; binary extra pins `psycopg-binary==3.3.6` | [PyPI](https://pypi.org/pypi/psycopg/json) |
| pgvector Python adapter | `pgvector==0.5.0` | `>=3.10`; distinct from server extension version | [PyPI](https://pypi.org/pypi/pgvector/json) |
| Password hashing | `argon2-cffi==25.1.0` | `>=3.8` | [PyPI](https://pypi.org/pypi/argon2-cffi/json) |
| ASGI server | `uvicorn==0.53.0` | `>=3.10` | [PyPI](https://pypi.org/pypi/uvicorn/json) |
| HTTP client | `httpx==0.28.1` | `>=3.8`; FastAPI's optional standard extra accepts `>=0.23,<1` | [PyPI](https://pypi.org/pypi/httpx/json) |
| Chinese segmentation | `jieba==0.42.1` | No published `requires_python`; test import/tokenization on Python 3.12 and lock fixtures before acceptance | [PyPI](https://pypi.org/pypi/jieba/json) |
| Test runner | `pytest==9.1.1` | `>=3.10` | [PyPI](https://pypi.org/pypi/pytest/json) |
| Async tests | `pytest-asyncio==1.4.0` | `>=3.10` | [PyPI](https://pypi.org/pypi/pytest-asyncio/json) |
| Property tests | `hypothesis==6.168.0` | `>=3.10`; official package lists Python 3.12 | [PyPI](https://pypi.org/project/hypothesis/6.168.0/) |

## Protocol compatibility boundary

- Local bridge uses MCP stdio; remote Brain transport is [Streamable HTTP](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) with [OAuth/resource binding](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization). The current SDK's [protocol-version guide](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/protocol-versions.md) describes negotiation across legacy and newer protocol eras. Do not force its newest revision on a client without an interoperability test.
- [OpenAI MCP guidance](https://developers.openai.com/api/docs/mcp) and [plugin authentication guidance](https://developers.openai.com/plugins/build/auth) were rechecked. Actual ChatGPT account capability and a reachable HTTPS endpoint remain unverified, and LAN-only staging cannot pass the ChatGPT web acceptance case.
- SDK v2.2.0 release notes explicitly identify behavior changes and not-yet-implemented extensions. The project must use only proven tool/transport/auth features; no task-extension or DPoP dependency is assumed.

## Lock and acceptance rule

T006 declared these exact **direct** candidates in `pyproject.toml`; `uv lock --python 3.12` resolved 57 packages to `uv.lock`, with `requires-python = "==3.12.*"`. `uv run --locked` installed the local Windows Python 3.12 environment, imported the API, model, ORM, migration, MCP, PostgreSQL adapter, vector adapter and tokenizer modules, and imported all five project package boundaries. Jieba tokenization executed, though the Windows terminal rendered Chinese output incorrectly; semantic fixture assertions remain for later tests. Before considering the lock production-accepted: import the selected stack on the target Linux runtime/image; run migration and protocol smoke tests; execute Chinese tokenization fixtures; verify image digest and PostgreSQL extension version; record deviations with primary-source evidence. A resolved lock and local import are still not real-client or production compatibility proof. Refresh this document if versions, target runtime, SDK protocol support, or official requirements drift.
