"""Review inbox and deletion reconciliation operations (T120/T121)."""


def test_review_inbox_approve_reject_single_use():
    from personal_brain_server.api.review_tools import InMemoryReviewInbox

    inbox = InMemoryReviewInbox()
    item_id = inbox.add(item_type="conflict", subject_refs=("a", "b"))
    assert inbox.approve(item_id).state == "approved"
    try:
        inbox.approve(item_id)
    except Exception:
        pass
    else:
        raise AssertionError("already-consumed approval must fail")


def test_reconciliation_removes_search_cache_and_releases_assets():
    from personal_brain_worker.deletion_jobs import reconcile_deleted_target

    outcome = reconcile_deleted_target(job_id="j1", target_id="n-1",
                                       search_refs=("s1", "s2"), cache_refs=("c1",))
    assert outcome.removed_search == 2
    assert outcome.removed_cache == 1
    assert outcome.released_assets == 1
