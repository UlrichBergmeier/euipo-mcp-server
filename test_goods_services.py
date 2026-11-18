"""Offline tests for Goods & Services API contract and normalization.

No real credentials, EUIPO API calls, or network required.
"""
from __future__ import annotations
import unittest
from goods_services import _clean_term, _entries, harmonize, suggestions, translations

class FakeGoodsServices:
    def __init__(self, result: dict):
        self.result = result
        self.payload = None
        self.maximum = None

    async def validate(self, payload: dict) -> dict:
        self.payload = payload
        return self.result

    async def suggest(self, payload: dict, maximum: int) -> dict:
        self.payload, self.maximum = payload, maximum
        return self.result

    async def translate(self, payload: dict) -> dict:
        self.payload = payload
        return self.result

class Tests(unittest.IsolatedAsyncioTestCase):
    async def test_trailing_period_preserves_original(self):
        fake = FakeGoodsServices({
            "sourceLanguage": "de",
            "goodsAndServices": [{
                "classNumber": 19,
                "terms": [
                    {"text": "Beton", "harmonized": True, "conceptId": "123"},
                    {"text": "Baumaterialien", "harmonized": False,
                     "warnings": [{"type": "/problems/example"}]},
                ],
            }],
        })
        result = await harmonize(
            [{"classNumber": 19, "terms": ["  Beton. ", "Baumaterialien."]}],
            client=fake,
        )
        self.assertEqual(fake.payload["goodsAndServices"][0]["terms"],
                         ["Beton", "Baumaterialien"])
        row = result["goodsAndServices"][0]["terms"][0]
        self.assertEqual(row["original"], "  Beton. ")
        self.assertEqual(row["abgefragt"], "Beton")
        self.assertTrue(row["abschlusspunkt_entfernt"])
        self.assertEqual(row["status"], "harmonisiert")
        self.assertEqual(row["conceptId"], "123")
        self.assertEqual(result["goodsAndServices"][0]["terms"][1]["status"],
                         "nicht_harmonisiert")

    async def test_result_not_attributable_never_claims_match(self):
        fake = FakeGoodsServices({
            "goodsAndServices": [{
                "classNumber": 19,
                "terms": [{"text": "Falscher Begriff", "harmonized": True}],
            }]
        })
        result = await harmonize(
            [{"classNumber": 19, "terms": ["Beton."]}], client=fake
        )
        row = result["goodsAndServices"][0]["terms"][0]
        self.assertEqual(row["status"], "manuell_pruefen")
        self.assertIsNone(row["conceptId"])

    async def test_class_mismatch_never_claims_match(self):
        fake = FakeGoodsServices({
            "goodsAndServices": [{
                "classNumber": 35,
                "terms": [{"text": "Beton", "harmonized": True}],
            }]
        })
        result = await harmonize(
            [{"classNumber": 19, "terms": ["Beton"]}], client=fake
        )
        self.assertEqual(result["goodsAndServices"][0]["terms"][0]["status"],
                         "manuell_pruefen")

    async def test_suggestions_class_and_punctuation(self):
        fake = FakeGoodsServices({"suggestions": []})
        data = await suggestions(
            ["Beton.", "Tragbare Bauteile"],
            sprache="de",
            nizza_klasse=19,
            max_vorschlaege=50,
            client=fake,
        )
        self.assertEqual(fake.payload, {
            "language": "de",
            "texts": ["Beton", "Tragbare Bauteile"],
            "classNumber": 19,
        })
        self.assertEqual(fake.maximum, 50)
        self.assertEqual(data["vorschlaege"], [])

    async def test_translation_uses_api_schema(self):
        fake = FakeGoodsServices({"translations": {"en": [{
            "classNumber": 19, "terms": ["Concrete"]
        }]}})
        response = await translations(
            [{"classNumber": 19, "terms": ["Beton."]}],
            quell_sprache="de",
            ziel_sprachen=["en"],
            client=fake,
        )
        self.assertEqual(fake.payload["sourceLanguage"], "de")
        self.assertEqual(fake.payload["languagesToTranslate"], ["en"])
        self.assertEqual(fake.payload["goodsAndServices"][0]["terms"], ["Beton"])
        self.assertEqual(response["uebersetzungen"]["en"][0]["terms"], ["Concrete"])

    async def test_no_double_class(self):
        with self.assertRaises(ValueError):
            _entries([{"classNumber":19,"terms":["Beton"]},
                      {"classNumber":19,"terms":["Stein"]}])

    async def test_bad_class(self):
        with self.assertRaises(ValueError):
            _entries([{"classNumber":0,"terms":["Beton"]}])

    async def test_bad_language(self):
        with self.assertRaises(ValueError):
            await harmonize([{"classNumber":19,"terms":["Beton"]}],
                            sprache="xx",client=FakeGoodsServices({}))

    async def test_bad_target_language(self):
        with self.assertRaises(ValueError):
            await translations([{"classNumber":19,"terms":["Beton"]}],
                               "de",["de"],client=FakeGoodsServices({}))

    async def test_never_delete_inner_full_stop(self):
        self.assertEqual(_clean_term("E-Mail-Dienstleistungen, z. B. Support."),
                         "E-Mail-Dienstleistungen, z. B. Support")

    async def test_missing_api_response_fails_closed(self):
        with self.assertRaises(RuntimeError):
            await harmonize([{"classNumber":19,"terms":["Beton"]}],
                            client=FakeGoodsServices({}))

if __name__ == "__main__":
    unittest.main()
