"""Stateful synthetic backend for concurrency and creation/patch failure checks."""

import asyncio
import copy
import json

import httpx2 as httpx


class OrganizerBackend:
    def __init__(self):
        self.catalogs = {
            "categories": [
                {"id": "a", "name": "Dinner", "slug": "dinner"},
                {"id": "b", "name": "Dessert", "slug": "dessert"},
            ],
            "tags": [
                {"id": "t", "name": "Quick", "slug": "quick"},
                {"id": "u", "name": "Easy", "slug": "easy"},
            ],
            "tools": [
                {"id": "w", "name": "Whisk", "slug": "whisk"},
                {"id": "p", "name": "Pan", "slug": "pan"},
            ],
        }
        self.recipes = {}
        self.calls = []
        self.created = []
        self.patch_fail = False
        self.create_fail_after = None
        self.active_reads = self.peak_reads = 0
        self.active_patches = self.peak_patches = 0

    def recipe(self, slug="one"):
        return self.recipes.setdefault(
            slug,
            {
                "id": "id-" + slug,
                "slug": slug,
                "name": "Recipe",
                "recipeCategory": copy.deepcopy(self.catalogs["categories"][:1]),
                "tags": copy.deepcopy(self.catalogs["tags"][:1]),
                "tools": copy.deepcopy(self.catalogs["tools"][:1]),
                "recipeIngredient": [{"note": "keep"}],
                "nutrition": {"keep": True},
            },
        )

    async def handle(self, request):
        method, path = request.method, request.url.path
        body = json.loads(request.content) if request.content else None
        self.calls.append((method, path, body))
        if path.startswith("/api/recipes/"):
            slug = path.removeprefix("/api/recipes/")
            if slug == "missing":
                return httpx.Response(404, json={"detail": "synthetic missing"})
            if method == "GET":
                self.active_reads += 1
                self.peak_reads = max(self.peak_reads, self.active_reads)
                await asyncio.sleep(0.005)
                self.active_reads -= 1
                return httpx.Response(200, json=copy.deepcopy(self.recipe(slug)))
            if method == "PATCH":
                if self.patch_fail:
                    return httpx.Response(500, json={"detail": "synthetic private body"})
                self.active_patches += 1
                self.peak_patches = max(self.peak_patches, self.active_patches)
                await asyncio.sleep(0.005)
                self.active_patches -= 1
                self.recipe(slug).update(copy.deepcopy(body))
                return httpx.Response(200, json=copy.deepcopy(self.recipe(slug)))
        if path.startswith("/api/organizers/"):
            kind = path.removeprefix("/api/organizers/")
            if method == "GET":
                snapshot = copy.deepcopy(self.catalogs[kind])
                await asyncio.sleep(0.005)
                return httpx.Response(200, json={"items": snapshot})
            if method == "POST":
                if (
                    self.create_fail_after is not None
                    and len(self.created) >= self.create_fail_after
                ):
                    return httpx.Response(500, json={"detail": "synthetic private body"})
                item = {
                    "id": "new-" + str(len(self.created)),
                    "name": body["name"],
                    "slug": body["name"].lower().replace(" ", "-"),
                }
                self.created.append((kind, item))
                self.catalogs[kind].append(item)
                await asyncio.sleep(0.005)
                return httpx.Response(200, json=item)
        return httpx.Response(500, json={"detail": "unexpected synthetic request"})

    def patches(self):
        return [body for method, path, body in self.calls if method == "PATCH"]
