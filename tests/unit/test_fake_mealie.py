import httpx2 as httpx
import pytest

from tests.support.fake_mealie import FakeMealie


@pytest.mark.parametrize(("expected", "actual"), [(0, False), (True, 1)])
async def test_fixture_rejects_boolean_number_substitution(expected, actual):
    requests = [
        {
            "method": "POST",
            "path": "/api/units",
            "query": {},
            "body": {"value": expected},
            "response": {"id": "id"},
        }
    ]
    with pytest.raises(AssertionError, match="Unexpected fixture request"):
        with FakeMealie(requests) as fake:
            async with httpx.AsyncClient() as client:
                response = await client.post(fake.server_url + "/api/units", json={"value": actual})
            assert response.status_code == 500
