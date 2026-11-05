"""Offline tests: no EUIPO credentials or live API requests needed."""
import unittest
from similarity import euipo_similarity_search, _status, _literal


class FakeEUIPO:
    def __init__(self):
        self.requests = []

    async def search_wordmarks(self, term, nice_class, status=None, page=0,
                               size=25, mark_basis="ALL"):
        self.requests.append((term, nice_class, status, page, size, mark_basis))
        return {
            "marken": [
                {"applicationNumber": "1", "markBasis": "EU_TRADEMARK",
                 "wordMarkSpecification": {"verbalElement": "XY"},
                 "status": "REGISTERED", "niceClasses": [19]},
                {"applicationNumber": "2", "markBasis": "EU_TRADEMARK",
                 "wordMarkSpecification": {"verbalElement": "XYZ"},
                 "status": "UNDER_EXAMINATION"},
                {"applicationNumber": "3", "markBasis": "EU_TRADEMARK",
                 "wordMarkSpecification": {"verbalElement": "XY"},
                 "status": "EXPIRED"},
                {"applicationNumber": "4", "markBasis": "EU_TRADEMARK",
                 "wordMarkSpecification": {"verbalElement": "XYY"},
                 "status": "APPEALED"},
                {"applicationNumber": "5", "markBasis": "EU_TRADEMARK",
                 "wordMarkSpecification": {"verbalElement": "X & Y"},
                 "status": "REGISTERED"},
            ],
            "treffer_gesamt": 5,
            "seiten_gesamt": 1,
        }


class TestSimilarity(unittest.IsolatedAsyncioTestCase):
    async def test_live_status_and_deduplication(self):
        client = FakeEUIPO()
        result = await euipo_similarity_search(
            "XY", 19, weitere_suchbegriffe=["X-Y"], client=client)
        self.assertEqual(len(result["potenziell_lebende_marken"]), 3)
        self.assertEqual(len(result["status_manuell_pruefen"]), 1)
        self.assertEqual(result["nicht_lebende_ausgefiltert"], 1)
        self.assertEqual(result["anzahl_identischer_lebender_treffer"], 1)
        self.assertEqual(len(client.requests), 2)
        self.assertTrue(all(query[2] is None for query in client.requests))
        self.assertTrue(all(
            len(hit["gefunden_ueber"]) == 2
            for hit in result["potenziell_lebende_marken"]))

    async def test_rejects_query_injection(self):
        for search in ("XY;status==REGISTERED", "a/b"):
            with self.assertRaises(ValueError):
                await euipo_similarity_search(search, client=FakeEUIPO())

    async def test_ambiguity(self):
        self.assertEqual(_status("APPEALED"), "Status manuell prüfen")
        self.assertEqual(_status("REFUSED"), "laut Status nicht lebend")
        self.assertEqual(_literal("X & Y"), "x & y")

    async def test_failed_api_does_not_leak_details(self):
        class Broken:
            async def search_wordmarks(self, *args, **kwargs):
                raise RuntimeError("EUIPO_CLIENT_SECRET=SENSITIVE")
        result = await euipo_similarity_search("XY", client=Broken())
        self.assertEqual(result["recherchestand"], "teilweise durchgeführt")
        self.assertNotIn("SENSITIVE", str(result))

    async def test_pagination_limit_is_disclosed(self):
        class Many:
            async def search_wordmarks(self, *args, **kwargs):
                return {
                    "marken": [{"applicationNumber": str(i),
                               "wordMarkSpecification": {"verbalElement": "XY"},
                               "status": "REGISTERED"} for i in range(25)],
                    "treffer_gesamt": 10000,
                    "seiten_gesamt": 400,
                }
        result = await euipo_similarity_search(
            "XY", seiten_pro_suche=1, client=Many())
        self.assertEqual(result["recherchestand"], "teilweise durchgeführt")


if __name__ == "__main__":
    unittest.main()
