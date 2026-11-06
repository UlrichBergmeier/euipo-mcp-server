"""Offline tests for EUIPO Trademark Search API 1.1.0 extensions."""
import unittest
from unittest.mock import patch
from euipo import build_query, validate_application_number
from euipo_extensions import build_advanced_query, advanced_search, get_trademark_image
from similarity import euipo_similarity_search


class QueryTests(unittest.TestCase):
    def test_legacy_wordmark_filter(self):
        q = build_query("SYSTEMBETON", 19, "REGISTERED", "EU_TRADEMARK")
        self.assertIn("markFeature==WORD", q)
        self.assertIn("status==REGISTERED", q)
        self.assertIn("niceClasses==19", q)

    def test_no_default_status_and_optional_all_features(self):
        self.assertNotIn("status==", build_query("SYSTEMBETON", 19))
        self.assertNotIn("markFeature==WORD", build_query("XY", None, mark_feature="ALL"))

    def test_official_euipo_registration_numbers(self):
        for number in ("019430321", "W00843427", "W00843427A"):
            self.assertEqual(validate_application_number(number), number)
        for number in ("123", "w00843427A", "019430321X", "W0084342A"):
            with self.assertRaises(ValueError):
                validate_application_number(number)

    def test_combined_advanced_filters(self):
        q = build_advanced_query(suchbegriff="SYSTEM BETON",
            nizza_klassen=[19, 37], registerstatus=["REGISTERED", "UNDER_EXAMINATION"],
            markenformen=["WORD", "FIGURATIVE"], anmelder="Muster Bau",
            angemeldet_ab="2024-01-01", angemeldet_bis="2026-11-01")
        self.assertIn('wordMarkSpecification.verbalElement=="*SYSTEM BETON*"', q)
        self.assertIn("niceClasses=in=(19,37)", q)
        self.assertIn("status=in=(REGISTERED,UNDER_EXAMINATION)", q)
        self.assertIn("markFeature=in=(WORD,FIGURATIVE)", q)
        self.assertIn('applicants.name=="*Muster Bau*"', q)

    def test_all_classes(self):
        self.assertEqual(build_advanced_query(nizza_klassen=[19,37],klassenmodus="ALL"),
                         "niceClasses=all=(19,37)")

    def test_no_user_controlled_rsql(self):
        for values in ({"suchbegriff": "XY;status==REGISTERED"},
                       {"anmelder": "X) or status==REGISTERED"},
                       {"registerstatus": ["REGISTERED", "INVALID"]},
                       {"markenformen": ["BLAH"]},
                       {"nizza_klassen": [19, True]},
                       {"angemeldet_ab": "2026-02-30"},
                       {"angemeldet_ab": "2026-11-30", "angemeldet_bis": "2026-11-01"},
                       {}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                build_advanced_query(**values)


class MockEUIPO:
    async def _token(self, _): return "fake-token"
    def _headers(self, _): return {"Authorization": "Bearer fake-token"}


class Response:
    def __init__(self, data=None, raw=b"\x89PNG\r\n\x1a\ntest"):
        self.data = data or {"trademarks": [], "page": 0, "size": 20,
                             "totalElements": 0, "totalPages": 0}
        self.raw = raw
        self.headers = {"Content-Type": "image/png", "Content-Length": str(len(raw))}
    def json(self): return self.data
    def raise_for_status(self): pass
    async def aiter_bytes(self): yield self.raw


class HTTP:
    last = None
    def __init__(self, **kwargs): HTTP.last = self
    async def __aenter__(self): return self
    async def __aexit__(self, *_): pass
    async def get(self, url, params=None, headers=None):
        self.params = params
        return Response({"trademarks": [{"applicationNumber": "019430321",
                         "status": "UNDER_EXAMINATION"}], "page": 0, "size": 20,
                         "totalElements": 1, "totalPages": 1})
    def stream(self, method, url, headers=None):
        self.url = url
        self.sent_headers = headers
        self.response = Response()
        return self
    def raise_for_status(self): pass
    @property
    def headers(self): return self.response.headers
    async def aiter_bytes(self):
        async for part in self.response.aiter_bytes(): yield part


class AsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_structured_query_transport(self):
        with patch("euipo_extensions.httpx.AsyncClient", HTTP):
            result = await advanced_search(MockEUIPO(), suchbegriff="XY")
        self.assertEqual(result["treffer_gesamt"], 1)
        self.assertEqual(HTTP.last.params["query"], "wordMarkSpecification.verbalElement==*XY*")
        self.assertNotIn("fake-token", str(result))

    async def test_authenticated_image_download(self):
        with patch("euipo_extensions.httpx.AsyncClient", HTTP):
            data, fmt = await get_trademark_image(MockEUIPO(), "019430321", True)
        self.assertEqual(fmt, "png")
        self.assertTrue(data.startswith(b"\x89PNG"))
        self.assertTrue(HTTP.last.url.endswith("/019430321/image/thumbnail"))
        self.assertEqual(HTTP.last.sent_headers["Accept"], "image/*")

    async def test_image_size_limit(self):
        class Huge(HTTP):
            def stream(self, method, url, headers=None):
                self.url = url
                self.response = Response(raw=b"x"*512001)
                return self
        with patch("euipo_extensions.httpx.AsyncClient", Huge):
            with self.assertRaises(ValueError):
                await get_trademark_image(MockEUIPO(), "019430321", True)

    async def test_fig_verbal_marks_candidate(self):
        class Search:
            def __init__(self): self.called = False
            async def search_verbal_marks(self, *args, **kwargs):
                self.called = True
                return {"marken":[{"applicationNumber":"019430321",
                    "markFeature":"FIGURATIVE", "markBasis":"EU_TRADEMARK",
                    "wordMarkSpecification":{"verbalElement":"XY"},
                    "status":"REGISTERED", "niceClasses":[19]}], "seiten_gesamt":1}
        client = Search()
        result = await euipo_similarity_search("XY", 19, client=client)
        self.assertTrue(client.called)
        self.assertEqual(result["potenziell_lebende_marken"][0]["markenform"], "FIGURATIVE")


if __name__ == "__main__":
    unittest.main()
