import pytest

from mealie_mcp_server.services.candidate_matching import MatchField, classify_and_rank

FOOD_FIELDS = [MatchField("name"), MatchField("pluralName"), MatchField("alias", True)]
UNIT_FIELDS = [
    *FOOD_FIELDS[:2],
    MatchField("abbreviation"),
    MatchField("pluralAbbreviation"),
    FOOD_FIELDS[-1],
]


@pytest.mark.parametrize(
    ("candidate", "query", "field", "match_type", "value"),
    [
        ({"name": "Basil"}, "BASIL", "name", "exact", "Basil"),
        (
            {"name": "Tomato", "pluralName": "Tomatoes"},
            "Tomatoes",
            "pluralName",
            "exact",
            "Tomatoes",
        ),
        ({"name": "Fresh Mozzarella"}, "mozzarella", "name", "substring", "Fresh Mozzarella"),
        (
            {"name": "fermented pork", "aliases": [{"name": "cured pork (som moo)"}]},
            "som moo",
            "alias",
            "substring",
            "cured pork (som moo)",
        ),
        (
            {"aliases": [{"name": "cured pork (som moo)"}]},
            "cured pork (som moo)",
            "alias",
            "exact",
            "cured pork (som moo)",
        ),
        ({"abbreviation": "tbsp"}, "tbsp", "abbreviation", "exact", "tbsp"),
    ],
)
def test_classifies_stored_values(candidate, query, field, match_type, value):
    result = classify_and_rank(query, [candidate], UNIT_FIELDS)
    assert result == [
        {**candidate, "matchedBy": field, "matchType": match_type, "matchedValue": value}
    ]


def test_exact_precedes_substring_and_field_priorities():
    candidates = [
        {"id": str(i), field.key: "tablespoon"} for i, field in enumerate(UNIT_FIELDS[:-1])
    ]
    candidates += [
        {"id": "4", "aliases": [{"name": "tablespoon"}]},
        {"id": "5", "name": "tablespoon heaping"},
    ]
    result = classify_and_rank("tablespoon", list(reversed(candidates)), UNIT_FIELDS)
    assert [row["id"] for row in result] == ["0", "1", "2", "3", "4", "5"]


def test_unicode_name_id_and_alias_ties_match_node_collation():
    # Order observed with Intl.Collator(en-US) in the pinned Node reference.
    names = ["Z", "á", "A", "a", "é", "e", "E", "ß", "ss", "ñ", "n", "N", "2", "10", "_x", "-x"]
    candidates = [{"id": name, "name": name, "aliases": [{"name": "hit"}]} for name in names]
    result = classify_and_rank("hit", candidates, FOOD_FIELDS)
    assert [row["name"] for row in result] == [
        "_x",
        "-x",
        "10",
        "2",
        "a",
        "A",
        "á",
        "e",
        "E",
        "é",
        "n",
        "N",
        "ñ",
        "ss",
        "ß",
        "Z",
    ]
    aliases = [
        {"name": "é garlic"},
        {"name": "Z garlic"},
        {"name": "a garlic"},
        None,
        {},
        {"name": " "},
    ]
    assert (
        classify_and_rank("garlic", [{"aliases": aliases}], FOOD_FIELDS)[0]["matchedValue"]
        == "a garlic"
    )
    ids = [{"id": "Z", "name": "hit"}, {"id": "a", "name": "hit"}]
    assert [row["id"] for row in classify_and_rank("hit", ids, FOOD_FIELDS)] == ["a", "Z"]


def test_trims_js_whitespace_and_uses_lower_not_casefold():
    assert len(classify_and_rank("\ufeff basil \ufeff", [{"name": " Basil "}], FOOD_FIELDS)) == 1
    assert classify_and_rank("ss", [{"name": "ß"}], FOOD_FIELDS) == []
    assert (
        classify_and_rank("missing", [{"name": "Basil", "aliases": "invalid"}], FOOD_FIELDS) == []
    )
    assert (
        classify_and_rank("basil", [{"name": None}, {"name": 2}, {"name": " "}], FOOD_FIELDS) == []
    )


def test_alias_exact_beats_earlier_alias_substring_and_preserves_payload():
    candidate = {
        "name": "x",
        "custom": {"untouched": True},
        "aliases": [{"name": "aaa garlic"}, {"name": "garlic"}],
    }
    result = classify_and_rank("garlic", [candidate], FOOD_FIELDS)
    assert result[0]["matchedValue"] == "garlic"
    assert "matchedValue" not in candidate
    assert result[0]["custom"] == {"untouched": True}
