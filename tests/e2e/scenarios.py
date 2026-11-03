"""Record verified results, not merely attempted calls, for the full catalog."""

import json
import uuid

from tests.e2e.context import baseline_arguments, catalog_names
from tests.e2e.evidence import validate_case, write_report


def contains(value, needle):
    return str(needle) in json.dumps(value, ensure_ascii=False)


class Scenario:
    def __init__(self, context, client, observer, transport, protocol):
        self.context, self.client, self.observer = context, client, observer
        self.prefix = (
            "MCP E2E " + transport + " " + protocol.replace("-", "") + " " + uuid.uuid4().hex[:8]
        )
        self.records = {}
        self.owned = []
        self.data = {}
        self.report = {
            "status": "failed",
            "transport": transport,
            "protocolVersion": protocol,
            "imageId": context.image,
            "checks": [],
            "tools": [],
            "inputRejections": [],
            "calls": 0,
        }

    async def call(self, name, arguments):
        self.report["lastTool"] = name
        result = await self.client.call_tool(name, arguments)
        self.report["calls"] += 1
        if result.is_error:
            raise AssertionError(name + ": " + result.content[0].text)
        value = json.loads(result.content[0].text)
        self.records.setdefault(name, {"tool": name, "outcome": "positive", "checks": []})
        return value

    def verify(self, name, condition, check):
        assert condition, name + ": " + check
        self.records[name]["checks"].append(check)

    def remember(self, path):
        self.owned.append(path)

    async def get(self, path):
        response = await self.observer.get(path)
        response.raise_for_status()
        return response.json()

    async def absent(self, path):
        return (await self.observer.get(path)).status_code == 404

    async def reject_all_inputs(self):
        for name, arguments in sorted(baseline_arguments().items()):
            result = await self.client.call_tool(
                name, {**arguments, "e2eUnexpectedField": "private-sentinel-must-not-echo"}
            )
            assert result.is_error, name
            text = result.content[0].text
            assert "e2eUnexpectedField" in text and "private-sentinel-must-not-echo" not in text
            self.report["inputRejections"].append(
                {"tool": name, "checks": ["unknown_field_rejected", "value_redacted"]}
            )

    async def verify_cleanup(self):
        for path in self.owned:
            assert await self.absent(path), "Owned resource remains: " + path
        self.report["checks"].append("owned_data_removed")

    async def run(self):
        from tests.e2e import (
            catalog_flow,
            mealplan_flow,
            recipe_extensions_flow,
            recipe_flow,
            shopping_flow,
        )

        try:
            listed = await self.client.list_tools()
            assert self.client.protocol_version == self.report["protocolVersion"]
            assert {tool.name for tool in listed.tools} == catalog_names()
            self.report["checks"].extend(["catalog_78", "transport_connected"])
            prompts = await self.client.list_prompts()
            assert [prompt.name for prompt in prompts.prompts] == ["weekly-meal-plan"]
            assert (
                len(
                    (
                        await self.client.get_prompt(
                            "weekly-meal-plan", {"preferences": "vegetarian"}
                        )
                    ).messages
                )
                == 2
            )
            self.report["checks"].append("prompt")
            await self.reject_all_inputs()
            await catalog_flow.prepare(self)
            await recipe_flow.exercise(self)
            await recipe_extensions_flow.exercise(self)
            from tests.e2e import (
                advanced_330_flow,
                collections_330_flow,
                jobs_330_flow,
                media_330_flow,
            )

            await advanced_330_flow.exercise(self)
            await collections_330_flow.exercise(self)
            await media_330_flow.exercise(self)
            await jobs_330_flow.exercise(self)
            await mealplan_flow.exercise(self)
            await shopping_flow.exercise(self)
            await recipe_flow.merge_and_cleanup(self)
            await catalog_flow.cleanup(self)
            await self.verify_cleanup()
            self.report["tools"] = list(self.records.values())
            self.report["status"] = "passed"
            self.report["coverage"] = validate_case(self.report, catalog_names())
        except Exception as error:
            self.report["status"] = "failed"
            self.report["failureType"] = type(error).__name__
            raise
        finally:
            self.report["tools"] = list(self.records.values())
            self.report["missingTools"] = sorted(catalog_names() - self.records.keys())
            path = self.context.artifacts / (
                "case-" + self.report["transport"] + "-" + self.report["protocolVersion"] + ".json"
            )
            write_report(path, self.report, secrets=(self.context.api_key, self.context.bearer))
