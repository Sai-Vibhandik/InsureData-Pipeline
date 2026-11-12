import unittest

import pandas as pd

import _path  # noqa: F401
from _fixtures import CFG, claims, customers, dup, policies, with_
from insuredata import analytics, transformations as t, validation as v


def build(cust, pol, clm):
    c, _, _ = v.validate_customers(cust, CFG)
    p, _, _ = v.validate_policies(pol, c, CFG)
    k, _, _ = v.validate_claims(clm, p, CFG)
    dp = t.build_dim_policy(p, c)
    return dp, t.build_fact_claims(k, dp)


class TransformTests(unittest.TestCase):
    def test_join_does_not_multiply_rows(self):
        dp, f = build(customers(), policies(), claims())
        self.assertEqual((len(dp), len(f)), (1, 1))
        self.assertEqual(f.policy_type.iloc[0], "Auto"); self.assertEqual(f.claim_month.iloc[0], "2024-06")
        self.assertEqual(dp.age_band.iloc[0], "30-49")

    def test_rejected_claims_not_incurred_and_cap_applied(self):
        k = pd.concat([claims(), with_(claims(), 0, claim_id="CLM-2", claim_status="denied"),
                       with_(claims(), 0, claim_id="CLM-3", claim_amount="50000")], ignore_index=True)
        _, f = build(customers(), policies(), k)
        inc = f.set_index("claim_id").incurred_amount
        self.assertEqual((inc["CLM-1"], inc["CLM-2"], inc["CLM-3"]), (2500.0, 0.0, 10000.0))   # cap = coverage limit

    def test_metric_formulas(self):
        k = pd.concat([claims(), with_(claims(), 0, claim_id="CLM-2", claim_amount="500", claim_status="open")], ignore_index=True)
        dp, f = build(customers(), policies(), k)
        m = analytics.by_policy_type(dp, f).iloc[0]
        self.assertEqual((m.policies, m.claims), (1, 2))
        self.assertAlmostEqual(m.claim_frequency, 2.0)
        self.assertAlmostEqual(m.loss_ratio, 3000 / 1000)
        kp = analytics.portfolio_kpis(dp, f)
        self.assertEqual(kp["approval_rate"], 1.0)               # only 1 decided claim (Paid)
        self.assertEqual(kp["avg_days_to_claim"], 152.0) #updated

    def test_pivot_and_crosstab_shapes(self):
        dp, f = build(customers(), policies(), claims())
        self.assertIn("Total", analytics.pivot_incurred(f)["policy_type"].tolist())
        self.assertEqual(analytics.crosstab_status(f).loc[0, "Paid"], 1)

    def test_no_claims_gives_zero_not_error(self):
        dp, f = build(customers(), policies(), claims().iloc[0:0])
        m = analytics.by_policy_type(dp, f).iloc[0]
        self.assertEqual((m.claims, m.loss_ratio), (0, 0))
        self.assertIsNone(analytics.portfolio_kpis(dp, f)["approval_rate"])


if __name__ == "__main__":
    unittest.main()
