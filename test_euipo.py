"""Offline tests for EUIPO client query construction. No secrets or network required."""
import unittest
from euipo import build_query

class TestEuipoQueries(unittest.TestCase):
    def test_registered_query_uses_and(self):
        q=build_query("SYSTEMBETON",19,"REGISTERED","EU_TRADEMARK")
        self.assertIn("markFeature==WORD",q)
        self.assertIn("wordMarkSpecification.verbalElement==*SYSTEMBETON*",q)
        self.assertIn("niceClasses==19",q)
        self.assertIn("status==REGISTERED",q)
        self.assertIn(" and ",q)
        self.assertNotIn(";",q)

    def test_all_statuses_does_not_filter(self):
        q=build_query("XY",None,None)
        self.assertNotIn("status==",q)

    def test_exact_and_prefix_are_separate_server_side_queries(self):
        exact=build_query("SYSTEM",None,"REGISTERED","EU_TRADEMARK",match_mode="EXAKT")
        prefix=build_query("SYSTEM",None,"REGISTERED","EU_TRADEMARK",match_mode="WORTANFANG")
        self.assertIn("verbalElement==SYSTEM and",exact)
        self.assertNotIn("*",exact)
        self.assertIn("verbalElement==SYSTEM* and",prefix)
        self.assertNotIn("==*SYSTEM",prefix)
        self.assertIn('verbalElement=="SYSTEM BETON"',build_query("SYSTEM BETON",None,match_mode="EXAKT"))
        self.assertIn('verbalElement=="SYSTEM BETON*"',build_query("SYSTEM BETON",None,match_mode="WORTANFANG"))

    def test_modes_cannot_inject_search_syntax(self):
        for term in ("SYSTEM*", "SYSTEM;status==REGISTERED", 'SYSTEM"', "SYSTEM)"):
            with self.assertRaises(ValueError):build_query(term,None,match_mode="EXAKT")
        with self.assertRaises(ValueError):build_query("SYSTEM",None,match_mode="SYSTEM*")

    def test_reject_invalid_values(self):
        with self.assertRaises(ValueError):
            build_query("XY;status==REGISTERED",19)
        with self.assertRaises(ValueError):
            build_query("XY",46)

if __name__=="__main__":
    unittest.main()
