from mealie_mcp_server.support.query_filter import (
    build_combined_like_filter,
    sanitize_for_like_filter,
)


def test_unrepresentable_quote_and_wildcards_are_removed() -> None:
    assert sanitize_for_like_filter('  say "hello" 100%_free ') == "say hello 100free"
    assert sanitize_for_like_filter("chef's knife, [aged] (OR crème 🧈)") == (
        "chef's knife, [aged] (OR crème 🧈)"
    )


def test_queries_are_opaque_literals_inside_the_filter() -> None:
    assert build_combined_like_filter(["name", "aliases.name"], ["basil", "garlic"]) == (
        '(name LIKE "%basil%" OR aliases.name LIKE "%basil%") OR '
        '(name LIKE "%garlic%" OR aliases.name LIKE "%garlic%")'
    )
    assert build_combined_like_filter(["name"], ["", "basil"]) == '(name LIKE "%basil%")'
    assert build_combined_like_filter(["name"], []) is None
