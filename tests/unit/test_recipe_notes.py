import asyncio
import json
from copy import deepcopy

import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.mealie.errors import MealieApiError
from mealie_mcp_server.services import recipe_notes as service

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
REF = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
TOKEN = "2026-11-03T10:00:00Z"
NOTE = {"title": "Title", "text": "Original", "referenceId": REF, "extra": {"keep": True}}
STEP = {
    "id": "ephemeral",
    "text": "Cook",
    "extra": False,
    "noteReferences": [
        {"referenceId": REF, "provider": "retain"},
        {"referenceId": OTHER, "provider": 0},
    ],
}
ORIGINAL = {"slug": "soup", "updatedAt": TOKEN, "notes": [NOTE], "recipeInstructions": [STEP]}


def transport_for(snapshot=ORIGINAL, *, status=200, mismatch=False):
    requests = []

    def handle(request):
        requests.append((request.method, json.loads(request.content) if request.content else None))
        if request.method == "GET":
            return httpx.Response(200, json=snapshot)
        if status != 200:
            return httpx.Response(status, json={"detail": "private body"})
        body = requests[-1][1]
        result = {**snapshot, **body}
        if "recipeInstructions" in result:
            result["recipeInstructions"] = [
                {**row, "id": "regenerated"} for row in result["recipeInstructions"]
            ]
        return httpx.Response(200, json=snapshot if mismatch else result)

    return httpx.MockTransport(handle), requests


async def test_read_exposes_snapshot_notes_without_losing_unknown_fields():
    transport, requests = transport_for()
    async with MealieClient(SETTINGS, transport=transport) as client:
        result = await service.get_recipe_notes(client, "soup")
    assert result == {"slug": "soup", "updatedAt": TOKEN, "notes": [NOTE]}
    assert len(requests) == 1


async def test_add_appends_and_keeps_empty_text_title_and_unknown_fields():
    transport, requests = transport_for()
    async with MealieClient(SETTINGS, transport=transport) as client:
        result = await service.add_recipe_note(
            client,
            "soup",
            {"expectedUpdatedAt": TOKEN, "title": "", "text": "", "referenceId": OTHER},
        )
    assert result["notes"] == [NOTE, {"title": "", "text": "", "referenceId": OTHER}]
    assert requests[1] == ("PATCH", {"notes": result["notes"]})


async def test_add_generates_valid_durable_uuid():
    from uuid import UUID

    transport, _ = transport_for()
    async with MealieClient(SETTINGS, transport=transport) as client:
        result = await service.add_recipe_note(
            client, "soup", {"expectedUpdatedAt": TOKEN, "title": "New", "text": "Content"}
        )
    assert str(UUID(result["notes"][-1]["referenceId"])) == result["notes"][-1]["referenceId"]


async def test_update_retains_identity_order_fields_and_omitted_text():
    transport, requests = transport_for(
        {**ORIGINAL, "notes": [NOTE, {**NOTE, "referenceId": OTHER}]}
    )
    async with MealieClient(SETTINGS, transport=transport) as client:
        result = await service.update_recipe_note(
            client, "soup", {"expectedUpdatedAt": TOKEN, "referenceId": REF.upper(), "title": ""}
        )
    assert result["notes"][0] == {**NOTE, "title": ""}
    assert result["notes"][1] == {**NOTE, "referenceId": OTHER}
    assert set(requests[1][1]) == {"notes"}


async def test_noop_update_skips_patch():
    transport, requests = transport_for()
    async with MealieClient(SETTINGS, transport=transport) as client:
        assert (
            await service.update_recipe_note(
                client, "soup", {"expectedUpdatedAt": TOKEN, "referenceId": REF, "text": "Original"}
            )
            == ORIGINAL
        )
    assert [method for method, _ in requests] == ["GET"]


@pytest.mark.parametrize("operation", ["add", "update", "delete"])
async def test_stale_snapshot_rejected_before_patch(operation):
    transport, requests = transport_for()
    async with MealieClient(SETTINGS, transport=transport) as client:
        with pytest.raises(ValueError, match="Stale snapshot"):
            await getattr(service, operation + "_recipe_note")(
                client,
                "soup",
                {"expectedUpdatedAt": "old", "referenceId": OTHER, "title": "X", "text": "Y"},
            )
    assert [method for method, _ in requests] == ["GET"]


@pytest.mark.parametrize("changes", [{}, {"expectedUpdatedAt": ""}, {"expectedUpdatedAt": None}])
async def test_snapshot_required_before_http(changes):
    transport, requests = transport_for()
    async with MealieClient(SETTINGS, transport=transport) as client:
        with pytest.raises(ValueError, match="expectedUpdatedAt"):
            await service.add_recipe_note(client, "soup", {"title": "X", "text": "Y", **changes})
    assert requests == []


@pytest.mark.parametrize("notes", [[NOTE, NOTE], [{**NOTE, "referenceId": None}], [None], "bad"])
async def test_ambiguous_or_malformed_stored_notes_reject_all_writes(notes):
    transport, requests = transport_for({**ORIGINAL, "notes": notes})
    async with MealieClient(SETTINGS, transport=transport) as client:
        with pytest.raises(ValueError, match="notes"):
            await service.add_recipe_note(
                client, "soup", {"expectedUpdatedAt": TOKEN, "title": "X", "text": "Y"}
            )
    assert len(requests) == 1


@pytest.mark.parametrize(
    "operation,reference", [("update", OTHER), ("delete", OTHER), ("add", REF)]
)
async def test_unknown_or_duplicate_identity_rejected(operation, reference):
    transport, requests = transport_for()
    async with MealieClient(SETTINGS, transport=transport) as client:
        with pytest.raises(ValueError, match="referenceId"):
            await getattr(service, operation + "_recipe_note")(
                client,
                "soup",
                {"expectedUpdatedAt": TOKEN, "referenceId": reference, "title": "X", "text": "Y"},
            )
    assert len(requests) == 1


async def test_linked_delete_requires_explicit_reference_removal():
    transport, requests = transport_for()
    async with MealieClient(SETTINGS, transport=transport) as client:
        with pytest.raises(ValueError, match="removeReferences"):
            await service.delete_recipe_note(
                client, "soup", {"expectedUpdatedAt": TOKEN, "referenceId": REF}
            )
    assert len(requests) == 1


async def test_linked_delete_removes_only_matching_refs_preserving_step_fields_order():
    snapshot = deepcopy(ORIGINAL)
    snapshot["recipeInstructions"].append({"id": "other", "text": "Serve", "unknown": []})
    transport, requests = transport_for(snapshot)
    async with MealieClient(SETTINGS, transport=transport) as client:
        await service.delete_recipe_note(
            client,
            "soup",
            {"expectedUpdatedAt": TOKEN, "referenceId": REF, "removeReferences": True},
        )
    assert requests[1] == (
        "PATCH",
        {
            "notes": [],
            "recipeInstructions": [
                {
                    "text": "Cook",
                    "extra": False,
                    "noteReferences": [{"referenceId": OTHER, "provider": 0}],
                },
                {"text": "Serve", "unknown": []},
            ],
        },
    )


@pytest.mark.parametrize("refs", [[{"referenceId": "invalid"}], [None], "bad"])
async def test_delete_refuses_malformed_instruction_references(refs):
    transport, requests = transport_for(
        {**ORIGINAL, "recipeInstructions": [{**STEP, "noteReferences": refs}]}
    )
    async with MealieClient(SETTINGS, transport=transport) as client:
        with pytest.raises(ValueError, match="reference"):
            await service.delete_recipe_note(
                client,
                "soup",
                {"expectedUpdatedAt": TOKEN, "referenceId": REF, "removeReferences": True},
            )
    assert len(requests) == 1


async def test_unlinked_delete_only_patches_notes():
    transport, requests = transport_for({**ORIGINAL, "recipeInstructions": []})
    async with MealieClient(SETTINGS, transport=transport) as client:
        await service.delete_recipe_note(
            client, "soup", {"expectedUpdatedAt": TOKEN, "referenceId": REF}
        )
    assert requests[1] == ("PATCH", {"notes": []})


async def test_duplicate_links_remove_all_matching_entries_only():
    snapshot = {
        **ORIGINAL,
        "recipeInstructions": [
            {
                **STEP,
                "noteReferences": [
                    {"referenceId": REF},
                    {"referenceId": OTHER, "unknown": []},
                    {"referenceId": REF},
                ],
            }
        ],
    }
    transport, requests = transport_for(snapshot)
    async with MealieClient(SETTINGS, transport=transport) as client:
        await service.delete_recipe_note(
            client,
            "soup",
            {"expectedUpdatedAt": TOKEN, "referenceId": REF, "removeReferences": True},
        )
    assert requests[1][1]["recipeInstructions"][0]["noteReferences"] == [
        {"referenceId": OTHER, "unknown": []}
    ]


@pytest.mark.parametrize("linked", [False, True])
async def test_delete_preserves_provider_nullable_unlinked_note_reference(linked):
    unlinked = {"referenceId": None, "providerExtra": True}
    references = [unlinked, {"referenceId": REF}] if linked else [unlinked]
    snapshot = {
        **ORIGINAL,
        "recipeInstructions": [{**STEP, "noteReferences": references}],
    }
    transport, requests = transport_for(snapshot)
    async with MealieClient(SETTINGS, transport=transport) as client:
        result = await service.delete_recipe_note(
            client,
            "soup",
            {"expectedUpdatedAt": TOKEN, "referenceId": REF, "removeReferences": linked},
        )
    assert result["notes"] == []
    assert result["recipeInstructions"][0]["noteReferences"] == [unlinked]
    payload = requests[1][1]
    if linked:
        assert payload["recipeInstructions"][0]["noteReferences"] == [unlinked]
        assert payload["recipeInstructions"][0]["extra"] is False
    else:
        assert set(payload) == {"notes"}


async def test_linked_delete_verifies_links_and_preserved_step_fields_without_replay():
    methods = []

    def handle(request):
        methods.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, json=ORIGINAL)
        return httpx.Response(200, json={**ORIGINAL, "notes": []})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError, match="verification failed"):
            await service.delete_recipe_note(
                client,
                "soup",
                {"expectedUpdatedAt": TOKEN, "referenceId": REF, "removeReferences": True},
            )
    assert methods == ["GET", "PATCH"]


@pytest.mark.parametrize("mismatch,status", [(True, 200), (False, 503)])
async def test_failed_or_unverified_write_never_replayed(mismatch, status):
    transport, requests = transport_for(mismatch=mismatch, status=status)
    async with MealieClient(SETTINGS, transport=transport) as client:
        with pytest.raises(ValueError if mismatch else MealieApiError) as caught:
            await service.update_recipe_note(
                client, "soup", {"expectedUpdatedAt": TOKEN, "referenceId": REF, "text": "Changed"}
            )
    assert len(requests) == 2
    assert "private body" not in str(caught.value)


async def test_cancelled_issued_patch_finishes_without_replay():
    entered, release = asyncio.Event(), asyncio.Event()
    methods = []

    async def handle(request):
        methods.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, json=ORIGINAL)
        entered.set()
        await release.wait()
        return httpx.Response(200, json={**ORIGINAL, **json.loads(request.content)})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        task = asyncio.create_task(
            service.update_recipe_note(
                client, "soup", {"expectedUpdatedAt": TOKEN, "referenceId": REF, "text": "Changed"}
            )
        )
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
    assert methods == ["GET", "PATCH"]
