# V1 Evidence Index

Quickstart scenario evidence is preserved here; command success is separated
from behavioral acceptance. Status: implementation synthetic evidence complete;
real-client and real-deployment evidence PENDING.

| Area | Evidence document | Status |
|---|---|---|
| Foundation/protocol/secret | `foundation.md` | PASS (synthetic) |
| US1 cross-client life records | `us1-cross-client-life-records.md` | PASS (synthetic) |
| US2 provenance | `us2-provenance.md` | PASS (synthetic) |
| US3 self model | `us3-self-model.md` | PASS (synthetic) |
| US4 project recovery | `us4-project-recovery.md` | PASS (synthetic) |
| US5 context/retrieval | `us5-context.md` | PASS (synthetic) |
| US6 assets | `us6-assets.md` | PASS (synthetic) |
| US7 security/bridge | `us7-security.md` | PASS (synthetic) |
| US8 lifecycle/deletion | `us8-lifecycle.md` | PASS (synthetic) |
| US9 offline | `us9-offline.md` | PASS (synthetic) |
| US10 operations | `us10-restore.md` | PASS (contract/synthetic) |
| US11 notifications | `us11-proactivity.md` | PASS (synthetic) |
| US12 human interface | `us12-human-interface.md` | PASS (contract); real Trilium PENDING |
| Real clients | `client-matrix.md` | EXTERNAL_VERIFICATION_PENDING |
| Traceability | `traceability-matrix.md` | PENDING (T169) |
| Final review | `final-readiness-review.md` | PENDING (T170) |

The acceptance evidence schema (`tests/acceptance/conftest.py`) enforces that a
`passed` journey requires authoritative refs, no failures and a reviewer
decision — mocks/placeholder/http-status evidence are rejected.
