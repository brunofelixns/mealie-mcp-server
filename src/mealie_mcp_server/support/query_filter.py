"""Build Mealie LIKE filters without inventing an unsupported escape grammar."""

import re
from collections.abc import Sequence


def sanitize_for_like_filter(raw: str) -> str:
    return re.sub(r'["%_]', "", raw).strip()


def build_combined_like_filter(
    fields: Sequence[str], sanitized_queries: Sequence[str]
) -> str | None:
    groups = [
        "(" + " OR ".join(f'{field} LIKE "%{query}%"' for field in fields) + ")"
        for query in sanitized_queries
        if query
    ]
    return " OR ".join(groups) if groups else None
