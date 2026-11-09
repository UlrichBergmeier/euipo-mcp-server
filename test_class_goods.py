"""Offline regression tests for exact EUIPO class goods and lexical shortlisting."""
import unittest
from unittest.mock import patch
from class_goods import parse_class_goods, validate_reference_terms
from server import euipo_klassendetails, euipo_aehnlichkeitsgalerie, mcp


def detail(with_german=True):
    descriptions = [{"language":"en","terms":["Concrete","Building materials","Prefabricated panels"]}]
    if with_german:
        descriptions.append({"language":"de","terms":["Beton","Baustoffe","Vorgefertigte Bauplatten"]})
    return {
        "applicationNumber":"019440746", "applicationLanguage":"en", "secondLanguage":"de",
        "goodsAndServices":[
            {"classNumber":19,"description":descriptions},
            {"classNumber":37,"description":[{"language":"de","terms":["Bauarbeiten","Reparaturleistungen"]}]},
        ],
    }


class RegisterGoodsTests(unittest.IsolatedAsyncioTestCase):
    async def test_german_terms_preserved_without_fabrication(self):
        info=parse_class_goods(detail(),19,["Beton"])
        self.assertEqual(info["begriffe"],["Beton","Baustoffe","Vorgefertigte Bauplatten"])
        self.assertEqual(info["sprache"],"de")
        self.assertTrue(info["deutsche_registerfassung"])
        self.assertEqual(info["technisch_naechster_begriff"]["wortlaut"],"Beton")
        self.assertEqual(info["technisch_naechster_begriff"]["technische_textaehnlichkeit"],1.0)

    async def test_language_fallback_not_claimed_to_be_german(self):
        info=parse_class_goods(detail(with_german=False),19,["Beton"])
        self.assertEqual(info["sprache"],"en")
        self.assertFalse(info["deutsche_registerfassung"])
        self.assertEqual(info["begriffe"][0],"Concrete")
        self.assertIn("Keine deutsche Registerfassung",info["hinweis"])

    async def test_no_reference_means_no_similarity_ranking(self):
        info=parse_class_goods(detail(),19)
        self.assertIsNone(info["technisch_naechster_begriff"])
        self.assertFalse(info["vergleichsbegriffe"])

    async def test_separate_classes_have_separate_candidates(self):
        info=parse_class_goods(detail(),37,["Bauarbeiten"])
        self.assertEqual(info["begriffe"],["Bauarbeiten","Reparaturleistungen"])
        self.assertEqual(info["technisch_naechster_begriff"]["wortlaut"],"Bauarbeiten")

    async def test_explicit_missing_class_does_not_invent_goods(self):
        info=parse_class_goods(detail(),41,["Bildung"])
        self.assertEqual(info["begriffe"],[])
        self.assertIsNone(info["technisch_naechster_begriff"])

    async def test_preserves_long_and_duplicate_terms_unmodified(self):
        data=detail()
        data["goodsAndServices"][0]["description"][1]["terms"]=["Beton","Beton","Künstliche Steine; Pflastersteine"]
        info=parse_class_goods(data,19,["Beton"])
        self.assertEqual(info["begriffe"],["Beton","Künstliche Steine; Pflastersteine"])

    async def test_rejects_invalid_class_and_reference_data(self):
        for klass in (0,46,19.0,"19"):
            with self.assertRaises(ValueError):
                parse_class_goods(detail(),klass)
        for refs in ([""],["a"*181],["ok"]*16,["ok",5]):
            with self.assertRaises(ValueError):
                validate_reference_terms(refs)

    async def test_tool_calls_only_one_registered_mark_detail(self):
        class FakeClient:
            async def trademark_detail(self,number):
                self.number=number
                return detail()
        with patch("server.EUIPOClient",return_value=FakeClient()):
            value=await euipo_klassendetails("019440746",19,["Beton"])
        self.assertEqual(value["technisch_naechster_begriff"]["wortlaut"],"Beton")
        self.assertEqual(value["anmeldenummer"],"019440746")
        self.assertNotIn("applicants",value)

    async def test_tech_identical_and_similar_goods_candidates(self):
        data=detail()
        data["goodsAndServices"][0]["description"][1]["terms"]=[
            "Beton","Betonbau", "Vorgefertigte Bauplatten", "Mineralische Baustoffe"
        ]
        record=parse_class_goods(data,19,["Beton"])
        classified={item["wortlaut"]:item["art"] for item in record["passende_positionen"]}
        self.assertEqual(classified["Beton"],"identisch")
        self.assertEqual(classified["Betonbau"],"textlich_aehnlich")
        self.assertNotIn("Mineralische Baustoffe",classified)

    async def test_all_class_summary_is_compact_one_api_call(self):
        calls=[]
        class FakeClient:
            async def trademark_detail(self, number):
                calls.append(number)
                return detail()
        with patch("server.EUIPOClient",return_value=FakeClient()):
            result=await euipo_klassendetails("019440746",0,["Beton"])
        self.assertEqual(calls,["019440746"])
        self.assertEqual(result["nizza_klasse"],0)
        self.assertEqual({c["nizza_klasse"] for c in result["klassen"]},{19,37})
        self.assertNotIn("begriffe",result["klassen"][0])
        cl19=next(c for c in result["klassen"] if c["nizza_klasse"]==19)
        self.assertEqual(cl19["passende_positionen"][0]["art"],"identisch")
        self.assertEqual(cl19["passende_positionen"][0]["wortlaut"],"Beton")

    async def test_invalid_input_rejected_before_api(self):
        with patch("server.EUIPOClient") as mock:
            out=await euipo_klassendetails("019440746/../../etc",19)
            self.assertIn("fehler",out)
            mock.assert_not_called()

    async def test_gallery_passes_bounded_reference_terms(self):
        async def fake(**kwargs):
            return {
                "zeichen":"BETON","nizza_klasse_vorfilter":19,
                "potenziell_lebende_marken":[], "status_manuell_pruefen":[],
                "nicht_lebende_marken":[], "abfragefehler":[],
                "abfragen":[{"suchbegriff":"BETON"}],
                "recherchestand":"API-Teilrecherche durchgeführt",
                "vollstaendigkeit":"NICHT garantiert",
            }
        with patch("server.euipo_similarity_search",side_effect=fake):
            value=await euipo_aehnlichkeitsgalerie("BETON",19,
                referenzwaren_dienstleistungen=["Beton","Zement"])
        self.assertEqual(value.structuredContent["referenzwaren_dienstleistungen"],["Beton","Zement"])

    async def test_ten_tools_present(self):
        names={x.name for x in await mcp.list_tools()}
        self.assertEqual(len(names),10)
        self.assertIn("euipo_klassendetails",names)
        self.assertIn("euipo_aehnlichkeitsgalerie",names)


if __name__=="__main__":
    unittest.main()
