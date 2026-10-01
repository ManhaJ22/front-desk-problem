"""Operator queue ordering. Priority order is defined in docs/CLAUDE.md."""


def priority(is_sensitive: bool, is_urgent: bool) -> int:
    """1 = sensitive+urgent, 2 = urgent, 3 = sensitive, 4 = neither."""
    if is_sensitive and is_urgent:
        return 1
    if is_urgent:
        return 2
    if is_sensitive:
        return 3
    return 4


def sort_queue(rows: list[dict]) -> list[dict]:
    """Unresolved first, then priority, then weakest combined score (NULL first), then newest.

    Each row needs: resolved, priority, combined_score, created_at (ISO-8601).
    """
    by_newest = sorted(rows, key=lambda r: r["created_at"], reverse=True)
    return sorted(
        by_newest,
        key=lambda r: (
            bool(r["resolved"]),
            r["priority"],
            -1.0 if r["combined_score"] is None else r["combined_score"],
        ),
    )
