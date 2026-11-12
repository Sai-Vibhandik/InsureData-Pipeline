import unittest

import _path  # noqa: F401
from _fixtures import CFG, claims, customers, dup, policies, with_
from insuredata import validation as v


class CustomerTests(unittest.TestCase):
    def test_clean_customer_standardized(self):
        c, r, w = v.validate_customers(customers(), CFG)
        self.assertEqual((len(c), len(r)), (1, 0))
        self.assertEqual((c.region.iloc[0], c.full_name.iloc[0]), ("North", "Ann Lee"))
        self.assertEqual(int(c.age.iloc[0]), 39)

    def test_latest_duplicate_wins_old_preserved_as_rejected(self):
        df = dup(customers(), 0, updated_at="2024-06-01", region="South")
        c, r, _ = v.validate_customers(df, CFG)
        self.assertEqual((len(c), len(r)), (1, 1))
        self.assertEqual(c.region.iloc[0], "South")
        self.assertEqual(r.reject_reasons.iloc[0], "superseded_duplicate")

    def test_bad_dob_nulls_but_keeps_record_and_unknown_region(self):
        for dob in ("2031-01-01", "1850-01-01", "garbage"):
            c, r, w = v.validate_customers(with_(customers(), 0, date_of_birth=dob, region="Atlantis"), CFG)
            self.assertEqual(len(c), 1); self.assertTrue(c.date_of_birth.isna().iloc[0])
            self.assertEqual(c.region.iloc[0], "Unknown"); self.assertEqual(w[0]["records"], 1)

    def test_missing_id_rejected_and_empty_input(self):
        c, r, _ = v.validate_customers(with_(customers(), 0, customer_id=None), CFG)
        self.assertEqual(r.reject_reasons.iloc[0], "missing_customer_id")
        c, r, _ = v.validate_customers(customers([]).reindex(columns=customers().columns), CFG)
        self.assertTrue(c.empty and r.empty)


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.cust, _, _ = v.validate_customers(customers(), CFG)

    def run_p(self, df):
        return v.validate_policies(df, self.cust, CFG)

    def test_valid_policy_normalized(self):
        p, r, _ = self.run_p(policies())
        self.assertEqual((len(p), len(r)), (1, 0))
        self.assertEqual(p.policy_type.iloc[0], "Auto"); self.assertEqual(p.annual_premium.iloc[0], 1000.0)

    def test_each_rule(self):
        cases = {"unknown_policy_type": dict(policy_type="Pet"), "invalid_premium": dict(annual_premium="-5"),
                 "invalid_dates": dict(start_date="nope"), "end_not_after_start": dict(end_date="2024-01-01"),
                 "policy_term_exceeds_limit": dict(end_date="2026-01-02"),
                 "orphan_customer_ref": dict(customer_id="CUST-404"), "missing_policy_id": dict(policy_id=None)}
        for rule, chg in cases.items():
            p, r, _ = self.run_p(with_(policies(), 0, **chg))
            self.assertTrue(p.empty, rule)
            self.assertIn(rule, r.reject_reasons.iloc[0])
    
    def test_policy_term_exactly_two_years_is_accepted(self):
        p, r, _ = self.run_p(
            with_(policies(), 0, end_date="2026-01-01")
        )

        self.assertEqual(len(p), 1)
        self.assertTrue(r.empty)

    def test_duplicate_policy_id_keeps_first_and_multiple_reasons_combined(self):
        p, r, _ = self.run_p(dup(policies(), 0))
        self.assertEqual((len(p), len(r)), (1, 1)); self.assertEqual(r.reject_reasons.iloc[0], "duplicate_policy_id")
        p, r, _ = self.run_p(with_(policies(), 0, annual_premium="x", customer_id="NOPE"))
        self.assertEqual(set(r.reject_reasons.iloc[0].split(";")), {"invalid_premium", "orphan_customer_ref"})


class ClaimTests(unittest.TestCase):
    def setUp(self):
        cust, _, _ = v.validate_customers(customers(), CFG)
        self.pol, _, _ = v.validate_policies(policies(), cust, CFG)

    def run_c(self, df):
        return v.validate_claims(df, self.pol, CFG)

    def test_valid_and_status_mapping(self):
        k, r, w = self.run_c(claims())
        self.assertEqual((len(k), len(r)), (1, 0)); self.assertEqual(k.claim_status.iloc[0], "Paid")
        k, r, _ = self.run_c(with_(claims(), 0, claim_status="denied"))
        self.assertEqual(k.claim_status.iloc[0], "Rejected")

    def test_each_rule(self):
        cases = {"orphan_policy_ref": dict(policy_id="POL-404"), "invalid_amount": dict(claim_amount="-3"),
                 "invalid_claim_date": dict(claim_date="x"), "unknown_claim_status": dict(claim_status="??"),
                 "claim_outside_policy_period": dict(claim_date="2025-03-01"), "missing_claim_id": dict(claim_id=None)}
        for rule, chg in cases.items():
            k, r, _ = self.run_c(with_(claims(), 0, **chg))
            self.assertTrue(k.empty, rule)
            self.assertIn(rule, r.reject_reasons.iloc[0])

    def test_duplicates_and_coverage_flag(self):
        k, r, _ = self.run_c(dup(claims(), 0))
        self.assertEqual((len(k), len(r)), (1, 1))
        k, r, w = self.run_c(with_(claims(), 0, claim_amount="99999"))
        self.assertTrue(bool(k.exceeds_coverage_limit.iloc[0])); self.assertEqual(w[0]["records"], 1)


if __name__ == "__main__":
    unittest.main()
