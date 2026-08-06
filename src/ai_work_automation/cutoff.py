from datetime import datetime


def is_after_cutoff(created: datetime, cutoff: datetime) -> bool:
    if created.tzinfo is None or cutoff.tzinfo is None:
        raise ValueError("created와 cutoff는 timezone-aware datetime이어야 합니다")
    return created >= cutoff
