from backend.triage import priority, sort_queue


def test_priority_order():
    assert priority(is_sensitive=True, is_urgent=True) == 1
    assert priority(is_sensitive=False, is_urgent=True) == 2
    assert priority(is_sensitive=True, is_urgent=False) == 3
    assert priority(is_sensitive=False, is_urgent=False) == 4


def row(id, *, resolved=False, prio=4, combined=None, created="2026-10-01T10:00:00"):
    return {"id": id, "resolved": resolved, "priority": prio, "combined_score": combined, "created_at": created}


def test_sort_queue_full_order():
    rows = [
        row("resolved-p1", resolved=True, prio=1),
        row("p4-strong", prio=4, combined=0.75),
        row("p4-weak", prio=4, combined=0.20),
        row("p4-null", prio=4, combined=None),
        row("p2", prio=2, combined=0.5),
        row("p1", prio=1, combined=0.9),
        row("p3-old", prio=3, combined=0.5, created="2026-10-01T09:00:00"),
        row("p3-new", prio=3, combined=0.5, created="2026-10-01T11:00:00"),
    ]
    assert [r["id"] for r in sort_queue(rows)] == [
        "p1",
        "p2",
        "p3-new",
        "p3-old",
        "p4-null",
        "p4-weak",
        "p4-strong",
        "resolved-p1",
    ]
