"""T09C: exercise saved-model cursor tools through the MCP protocol layer.

The registry is private to each test. No server lifespan, Toolkit connection or
native worker is started.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp.server.mcpserver.exceptions import ToolError

import generic_bridge
import server


class ModelCursorProtocolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="t09c_cursor_")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.models = []
        for index in range(5):
            model = {
                "model_id": str(index) * 32,
                "model_name": f"cursor_fixture_{index}",
                "status": "ready",
                "revision": 1,
                "inspection": {"features": [{"id": number} for number in range(4)]},
            }
            folder = self.root / model["model_id"]
            folder.mkdir()
            (folder / "model.json").write_text(json.dumps(model), encoding="utf-8")
            self.models.append(model)
        patcher = patch.object(generic_bridge, "MODELS", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def call(self, tool, arguments):
        result = await server.mcp.call_tool(tool, arguments)
        self.assertFalse(result.is_error)
        self.assertEqual(json.loads(result.content[0].text), result.structured_content)
        return result.structured_content

    async def test_schema_and_omitted_null_cursor_have_same_first_page(self):
        tools = {tool.name: tool for tool in await server.mcp.list_tools()}
        for name in ("creo_list_models", "creo_inspect_model"):
            self.assertIn(
                {"type": "null"}, tools[name].input_schema["properties"]["cursor"]["anyOf"]
            )

        omitted = await self.call("creo_list_models", {"limit": 2})
        explicit_null = await self.call("creo_list_models", {"limit": 2, "cursor": None})
        self.assertEqual(omitted, explicit_null)
        self.assertEqual(len(omitted["models"]), 2)
        self.assertFalse(omitted["complete"])
        self.assertIsInstance(omitted["next_cursor"], str)

        args = {
            "model_id": self.models[0]["model_id"],
            "detail": "full",
            "section": "features",
            "limit": 2,
        }
        self.assertEqual(
            await self.call("creo_inspect_model", args),
            await self.call("creo_inspect_model", {**args, "cursor": None}),
        )

    async def test_valid_pages_and_terminal_page_have_no_duplicate_or_missing_models(self):
        cursor = None
        seen = []
        while True:
            page = await self.call("creo_list_models", {"limit": 2, "cursor": cursor})
            seen.extend(item["model_id"] for item in page["models"])
            cursor = page["next_cursor"]
            if cursor is None:
                self.assertTrue(page["complete"])
                break
        self.assertEqual(len(seen), 5)
        self.assertEqual(set(seen), {model["model_id"] for model in self.models})

        args = {
            "model_id": self.models[0]["model_id"],
            "detail": "full",
            "section": "features",
            "limit": 2,
        }
        cursor = None
        features = []
        while True:
            page = await self.call("creo_inspect_model", {**args, "cursor": cursor})
            features.extend(item["id"] for item in page["data"]["features"])
            cursor = page["next_cursor"]
            if cursor is None:
                self.assertTrue(page["complete"])
                break
        self.assertEqual(features, [0, 1, 2, 3])

    async def test_invalid_cursor_is_rejected_after_signature_validation(self):
        with self.assertRaisesRegex(ToolError, "Input should be a valid string"):
            await server.mcp.call_tool("creo_list_models", {"cursor": 123})
        with self.assertRaisesRegex(ToolError, "Invalid query cursor"):
            await server.mcp.call_tool("creo_list_models", {"cursor": "invalid!"})
        with self.assertRaisesRegex(ToolError, "Invalid query cursor"):
            await server.mcp.call_tool(
                "creo_inspect_model",
                {"model_id": self.models[0]["model_id"], "detail": "full", "cursor": "invalid!"},
            )

    async def test_changed_snapshot_or_query_rejects_old_cursor(self):
        first = await self.call("creo_list_models", {"limit": 2})
        with self.assertRaisesRegex(ToolError, "Model list changed"):
            await server.mcp.call_tool(
                "creo_list_models", {"limit": 2, "detail": "full", "cursor": first["next_cursor"]}
            )
        path = self.root / self.models[0]["model_id"] / "model.json"
        changed = {**self.models[0], "revision": 2}
        path.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaisesRegex(ToolError, "Model list changed"):
            await server.mcp.call_tool(
                "creo_list_models", {"limit": 2, "cursor": first["next_cursor"]}
            )

        args = {
            "model_id": self.models[1]["model_id"],
            "detail": "full",
            "section": "features",
            "limit": 2,
        }
        page = await self.call("creo_inspect_model", args)
        with self.assertRaisesRegex(ToolError, "Snapshot or query changed"):
            await server.mcp.call_tool(
                "creo_inspect_model", {**args, "section": "edges", "cursor": page["next_cursor"]}
            )
        source = self.root / self.models[1]["model_id"] / "model.json"
        source.write_text(json.dumps({**self.models[1], "revision": 2}), encoding="utf-8")
        with self.assertRaisesRegex(ToolError, "Snapshot or query changed"):
            await server.mcp.call_tool(
                "creo_inspect_model", {**args, "cursor": page["next_cursor"]}
            )


if __name__ == "__main__":
    unittest.main()
