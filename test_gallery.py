"""Offline tests for the protected EUIPO similarity comparison gallery."""
import unittest
from unittest.mock import patch
from server import mcp, euipo_aehnlichkeitsgalerie, euipo_aehnlichkeitsgalerie_ui

GALLERY = "ui://euipo/aehnlichkeitsgalerie-v1.html"

def candidate(number, form="FIGURATIVE", status="REGISTERED"):
    return {
        "zeichen": "BOXBETON" if form != "WORD" else "SYSTEMBETON",
        "anmeldenummer": number,
        "markenbasis": "EU_TRADEMARK",
        "markenform": form,
        "registerstatus": status,
        "statusbewertung": "potenziell lebend",
        "anmeldedatum": "2026-01-01",
        "eintragungsdatum": None,
        "nizza_klassen": [19],
        "identischer_wortlaut": False,
        "schriftbild_aehnlichkeit_technisch": 0.68,
        "gefunden_ueber": ["BETON"],
    }

def response(candidates, errors=None, queries=None):
    return {
        "recherchestand": "API-Teilrecherche durchgeführt",
        "zeichen": "BETON",
        "nizza_klasse_vorfilter": 19,
        "potenziell_lebende_marken": candidates,
        "status_manuell_pruefen": [],
        "nicht_lebende_marken": [],
        "abfragefehler": errors or [],
        "abfragen": [{"suchbegriff":"BETON", "seite":0}] if queries is None else queries,
        "vollstaendigkeit": "NICHT garantiert; begrenzte Teilstringabfragen",
    }


class GalleryTests(unittest.IsolatedAsyncioTestCase):
    async def test_ninth_tool_and_gallery_resource_registered(self):
        tools = {t.name:t for t in await mcp.list_tools()}
        self.assertEqual(len(tools),9)
        self.assertEqual(tools["euipo_aehnlichkeitsgalerie"].meta["ui"]["resourceUri"], GALLERY)
        self.assertEqual(tools["euipo_aehnlichkeitsgalerie"].meta["openai/outputTemplate"], GALLERY)
        self.assertTrue(tools["euipo_aehnlichkeitsgalerie"].annotations.readOnlyHint)
        resources = await mcp.list_resources()
        entry = next(x for x in resources if str(x.uri) == GALLERY)
        self.assertEqual(entry.mimeType, "text/html;profile=mcp-app")
        self.assertEqual(entry.meta["ui"]["csp"]["connectDomains"], [])

    async def test_gallery_reuses_existing_search_with_bounded_parameters(self):
        async def fake(**kwargs):
            self.assertEqual(kwargs["zeichen"],"BETON")
            self.assertEqual(kwargs["nizza_klasse"],19)
            self.assertEqual(kwargs["weitere_suchbegriffe"],["BOXBETON"])
            self.assertEqual(kwargs["seiten_pro_suche"],1)
            self.assertEqual(kwargs["seitenumfang"],25)
            return response([candidate("019440746"),candidate("019430321",form="WORD")])
        with patch("server.euipo_similarity_search", side_effect=fake):
            result = await euipo_aehnlichkeitsgalerie("BETON",19,["BOXBETON"])
        self.assertFalse(result.isError)
        self.assertEqual(result.structuredContent["gesamt_kandidaten"],2)
        self.assertEqual(len(result.structuredContent["kandidaten"]),2)
        self.assertEqual(result.structuredContent["kandidaten"][1]["markenform"],"WORD")
        self.assertNotIn("data:image",str(result.structuredContent))
        self.assertIn("Keine vollständige Kollisionsrecherche",result.content[0].text)

    async def test_candidate_limit_is_explicit(self):
        marks = [candidate(f"{19400000+i:09d}") for i in range(65)]
        async def fake(**_):
            return response(marks)
        with patch("server.euipo_similarity_search", side_effect=fake):
            result=await euipo_aehnlichkeitsgalerie("BETON")
        self.assertEqual(result.structuredContent["gesamt_kandidaten"],65)
        self.assertEqual(len(result.structuredContent["kandidaten"]),40)
        self.assertIn("40 für die Galerie",result.content[0].text)

    async def test_partial_failure_is_disclosed(self):
        async def fake(**_):
            return response([candidate("019440746")],
                            errors=[{"suchbegriff":"BETON","hinweis":"fehlgeschlagen"}])
        with patch("server.euipo_similarity_search",side_effect=fake):
            result=await euipo_aehnlichkeitsgalerie("BETON")
        self.assertEqual(result.structuredContent["abfragefehler"],1)
        self.assertIn("Teilabfragefehler: 1",result.content[0].text)

    async def test_total_failure_returns_error(self):
        async def fake(**_):
            return response([],queries=[])
        with patch("server.euipo_similarity_search",side_effect=fake):
            result=await euipo_aehnlichkeitsgalerie("BETON")
        self.assertTrue(result.isError)
        self.assertIsNone(result.structuredContent)

    async def test_exception_does_not_leak_internal_errors(self):
        async def fake(**_):
            raise RuntimeError("secret-fake-token")
        with patch("server.euipo_similarity_search",side_effect=fake):
            result=await euipo_aehnlichkeitsgalerie("BETON")
        self.assertTrue(result.isError)
        self.assertNotIn("secret-fake-token",result.content[0].text)

    async def test_ui_self_contained_and_uses_authorized_image_tool(self):
        html=euipo_aehnlichkeitsgalerie_ui()
        for needle in (
            "ui/initialize", "ui/notifications/tool-result", "tools/call",
            'name: "euipo_markenabbildung"', "Keine Abbildung verfügbar",
            "max-width", "Zurück", "Weitere Treffer", "Original anzeigen",
        ):
            self.assertIn(needle,html)
        self.assertNotIn("<script src=",html)
        self.assertNotIn("fetch(",html)
        self.assertNotIn("https://",html)
        self.assertNotIn("http://",html)


if __name__ == "__main__":
    unittest.main()
