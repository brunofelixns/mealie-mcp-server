from pydantic import Field

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import format_params
from mealie_mcp_server.models.inputs.base import ToolInput
from mealie_mcp_server.server import create_server
from mealie_mcp_server.tools.contracts import register_contract_tool
from mealie_mcp_server.tools.helpers import success_result
from mealie_mcp_server.tools.registry import definitions
from tests.support.contracts import assert_contract_matches, load_cases
from tests.support.fake_mealie import FakeMealie


class Pagination(ToolInput):
    page: float | None = None
    per_page: float | None = Field(default=None, alias="perPage")


async def test_comparator_checks_requests_and_results_against_the_upstream_case() -> None:
    with FakeMealie("categories.basic") as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        server = create_server(settings)

        async def handler(request: Pagination, state):
            params = format_params({"page": request.page, "perPage": request.per_page})
            data = await state.client.request(
                "GET", "/api/organizers/categories", params=list(params.items())
            )
            return success_result(data)

        register_contract_tool(server, definitions()["get_categories"], Pagination, handler)
        await assert_contract_matches(server, load_cases("categories")[0], fake)
