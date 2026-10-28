"""The original weekly planning prompt, including confirmation before persistence."""

from importlib.resources import files
from typing import Any

from fastmcp import FastMCP
from fastmcp.prompts import Message, Prompt, PromptArgument, PromptResult
from mcp.types import Prompt as MCPPrompt


def weekly_meal_plan(preferences: str | None = None) -> PromptResult:
    context = (
        files("mealie_mcp_server")
        .joinpath("resources/weekly-meal-plan.md")
        .read_text(encoding="utf-8")
    )
    request = (
        "I need help creating a balanced meal plan for the next week that includes "
        "breakfast, lunch, and dinner."
    )
    if preferences:
        request += " My preferences are: " + preferences
    return PromptResult(
        messages=[Message(context, role="assistant"), Message(request, role="user")]
    )


class WeeklyMealPlanPrompt(Prompt):
    def __init__(self) -> None:
        super().__init__(
            name="weekly-meal-plan",
            description=(
                "Generate a balanced weekly meal plan with breakfast, lunch, and dinner for 7 days"
            ),
            arguments=[
                PromptArgument(
                    name="preferences",
                    description="Dietary preferences or constraints",
                    required=False,
                )
            ],
        )

    async def render(self, arguments: dict[str, Any] | None = None) -> PromptResult:
        preferences = (arguments or {}).get("preferences")
        if preferences is not None and not isinstance(preferences, str):
            raise ValueError("preferences must be a string.")
        return weekly_meal_plan(preferences)

    def to_mcp_prompt(self, **overrides: Any) -> MCPPrompt:
        overrides.setdefault("_meta", self.meta)
        return super().to_mcp_prompt(**overrides)


def register_prompts(server: FastMCP) -> None:
    server.add_prompt(WeeklyMealPlanPrompt())
