"""Offline checks for the protected EUIPO MCP Apps image viewer.

Run with the existing auth tests; no EUIPO credentials and no network calls.
"""
import unittest

from mcp.types import CallToolResult
from server import euipo_markenanzeige, euipo_markenanzeige_ui, mcp


VIEWER_URI = "ui://euipo/markenanzeige-v1.html"
EXISTING_TOOLS = {
    "markenvarianten_erstellen",
    "alter_vergleichsmarke",
    "euipo_wortmarkenrecherche",
    "euipo_markendetails",
    "euipo_aehnlichkeitsrecherche",
    "euipo_erweiterte_markenrecherche",
    "euipo_markenabbildung",
}


class ViewerRegistrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_existing_tools_retained(self):
        names = {t.name for t in await mcp.list_tools()}
        self.assertEqual(names, EXISTING_TOOLS | {"euipo_markenanzeige"})

    async def test_ui_tool_advertises_resource(self):
        tools = {t.name: t for t in await mcp.list_tools()}
        meta = tools["euipo_markenanzeige"].meta
        self.assertEqual(meta["ui"]["resourceUri"], VIEWER_URI)
        self.assertEqual(meta["openai/outputTemplate"], VIEWER_URI)
        self.assertEqual(meta["ui"]["visibility"], ["model", "app"])

    async def test_resource_has_standard_mcp_app_mime(self):
        resources = await mcp.list_resources()
        viewer = next(resource for resource in resources if str(resource.uri) == VIEWER_URI)
        self.assertEqual(viewer.mimeType, "text/html;profile=mcp-app")
        self.assertEqual(viewer.meta["ui"]["csp"]["connectDomains"], [])
        self.assertEqual(viewer.meta["ui"]["csp"]["resourceDomains"], [])

    async def test_tool_returns_compact_non_sensitive_result(self):
        result = euipo_markenanzeige("019440746")
        self.assertIsInstance(result, CallToolResult)
        self.assertFalse(result.isError)
        self.assertEqual(result.structuredContent, {"anmeldenummer":"019440746"})
        self.assertIn("019440746", result.content[0].text)
        self.assertNotIn("base64", str(result.model_dump()))

    async def test_international_mark_supported(self):
        result = euipo_markenanzeige("W00843427A")
        self.assertEqual(result.structuredContent["anmeldenummer"], "W00843427A")

    async def test_invalid_mark_rejected_without_api_call(self):
        result = euipo_markenanzeige("019440746/../../secret")
        self.assertTrue(result.isError)
        self.assertIsNone(result.structuredContent)

    async def test_viewer_is_self_contained_and_uses_existing_tool(self):
        html = euipo_markenanzeige_ui()
        for expected in (
            "ui/initialize", "ui/notifications/initialized",
            "ui/notifications/tool-input", "ui/notifications/tool-result",
            'name: "euipo_markenabbildung"', "tools/call",
            "data:", "image/jpeg", "image/png",
        ):
            self.assertIn(expected, html)
        self.assertNotIn("<script src=", html)
        self.assertNotIn("fetch(", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)


if __name__ == "__main__":
    unittest.main()
