"""Generate reproducible SYNTHETIC insurance data into data/raw (seed fixed).

Intentional problems injected (also listed in docs/data_dictionary.md):
 customers: duplicate ids with different updated_at, lowercase/space ids, invalid/future DOBs, odd region text, missing region
 policies : type aliases (Motor, AUTO...), '$1,200.00' premiums, negative/missing premiums, duplicate ids,
            end date before start, mixed date formats, unknown customer ids, unknown type
 claims   : unknown policy ids, claim date outside policy period, negative/missing amounts, duplicate claim ids,
            status aliases (denied, pending), amounts above coverage limit, ids with whitespace
"""
from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "raw"
SEED = 2024
FIRST = ["Ava", "Liam", "Noah", "Mia", "Ethan", "Zoe", "Lucas", "Ivy", "Owen", "Nora", "Leo", "Ruby", "Jude", "Cleo"]
LAST = ["Carter", "Nguyen", "Okafor", "Silva", "Brandt", "Haddad", "Ivanov", "Moreau", "Tanaka", "Reyes", "Quinn"]
LIMIT = {"Auto": (15000, 60000), "Home": (80000, 400000), "Health": (20000, 150000), "Life": (50000, 500000)}
PREM = {"Auto": (500, 2200), "Home": (700, 3800), "Health": (900, 4200), "Life": (300, 2600)}
CLAIM = {"Auto": ["Collision", "Theft", "Glass"], "Home": ["Water Damage", "Fire", "Burglary"],
         "Health": ["Hospital", "Outpatient", "Dental"], "Life": ["Accidental", "Critical Illness"]}


def d_fmt(rng, d):
    return rng.choices([d.isoformat(), d.strftime("%d %b %Y"), d.strftime("%m/%d/%Y")], [8, 1, 1])[0]


def main() -> None:
    rng = random.Random(SEED)
    OUT.mkdir(parents=True, exist_ok=True)
    asof = date(2024, 12, 31)
    customers = []
    for i in range(1, 801):
        dob = date(1950, 1, 1) + timedelta(days=rng.randint(0, 18 * 365 + 40 * 365 - 2000))
        customers.append(dict(customer_id=f"CUST-{i:04d}", full_name=f"{rng.choice(FIRST)} {rng.choice(LAST)}",
                              date_of_birth=dob.isoformat(), region=rng.choice(["North", "South", "East", "West"]),
                              segment=rng.choice(["Retail", "Retail", "Retail", "SME", "Premium"]),
                              signup_date=(date(2019, 1, 1) + timedelta(days=rng.randint(0, 1500))).isoformat(),
                              updated_at="2024-01-15"))
    policies, claims = [], []
    pid = 0
    for c in customers:
        for _ in range(rng.choice([1, 1, 1, 2])):
            pid += 1
            ptype = rng.choice(list(LIMIT))
            start = date(2022, 1, 1) + timedelta(days=rng.randint(0, 900))
            end = start + timedelta(days=364)
            prem = round(rng.uniform(*PREM[ptype]), 2)
            policies.append(dict(policy_id=f"POL-{pid:05d}", customer_id=c["customer_id"], policy_type=ptype,
                                 start_date=start, end_date=end, annual_premium=prem,
                                 coverage_limit=rng.randrange(*LIMIT[ptype], 5000), status=rng.choice(["Active", "Active", "Lapsed"])))
    cid = 0
    for p in policies:
        for _ in range(rng.choices([0, 1, 2, 3], [60, 28, 9, 3])[0]):
            cid += 1
            lo = p["start_date"]; hi = min(p["end_date"], asof)
            if hi <= lo: continue
            cdate = lo + timedelta(days=rng.randint(0, (hi - lo).days))
            amt = round(rng.lognormvariate(7.4, 1.0), 2)
            claims.append(dict(claim_id=f"CLM-{cid:06d}", policy_id=p["policy_id"], claim_date=cdate,
                               claim_amount=amt, claim_status=rng.choices(["Paid", "Approved", "Rejected", "Open"], [45, 20, 20, 15])[0],
                               claim_type=rng.choice(CLAIM[p["policy_type"]])))

    # ---- inject customer problems
    extra = []
    for k in range(15):
        dup = dict(customers[10 + k * 20]); dup["updated_at"] = "2024-06-30"; dup["region"] = "Central"; extra.append(dup)
    for k in range(6):
        old = dict(customers[400 + k]); old["updated_at"] = "2023-01-01"; extra.append(old)
    customers += extra
    for k in range(8):  customers[30 + k * 11]["customer_id"] = " " + customers[30 + k * 11]["customer_id"].lower()
    for k in range(6):  customers[100 + k]["date_of_birth"] = rng.choice(["2031-05-05", "1890-01-01", "not-a-date"])
    for k in range(9):  customers[200 + k]["region"] = rng.choice(["", "north ", "WEST", "Atlantis"])
    # ---- inject policy problems
    for k in range(12): policies[20 + k * 13]["policy_type"] = rng.choice(["Motor", "AUTO", "property", "medical", "car"])
    policies[7]["policy_type"] = "Pet"
    out_pol = []
    for p in policies:
        out_pol.append(dict(p, start_date=d_fmt(rng, p["start_date"]), end_date=d_fmt(rng, p["end_date"]),
                            annual_premium=(f"${p['annual_premium']:,.2f}" if rng.random() < 0.2 else p["annual_premium"])))
    for k in range(6):  out_pol[50 + k * 17]["annual_premium"] = rng.choice(["-250", "", "0", "free"])
    for k in range(5):  out_pol[300 + k]["end_date"] = out_pol[300 + k]["start_date"]
    for k in range(10): out_pol[400 + k]["customer_id"] = f"CUST-9{k:03d}"
    for k in range(6):  out_pol.append(dict(out_pol[500 + k * 9]))
    # ---- inject claim problems
    pol_by = {p["policy_id"]: p for p in policies}
    for k in range(25):  claims[10 + k * 7]["policy_id"] = f"POL-9{k:04d}"
    for k in range(30):
        p = pol_by.get(claims[300 + k * 3]["policy_id"])
        if p: claims[300 + k * 3]["claim_date"] = p["end_date"] + timedelta(days=rng.randint(5, 200))
    for k in range(8):   claims[100 + k * 5]["claim_amount"] = rng.choice(["-50", "", "abc", "0"])
    for k in range(6):   claims[150 + k]["claim_status"] = rng.choice(["denied", "pending", "PAID", "unknown??"])
    for k in range(8):   claims[200 + k]["claim_amount"] = round(900000 + rng.random() * 100000, 2)  # above any limit
    claims += [dict(claims[50 + k * 11]) for k in range(10)]                                          # duplicate claim ids
    for k in range(5):   claims[250 + k]["claim_id"] = " " + claims[250 + k]["claim_id"].lower()
    for c in claims:
        c["claim_date"] = d_fmt(rng, c["claim_date"]) if not isinstance(c["claim_date"], str) else c["claim_date"]
    rng.shuffle(customers)

    with (OUT / "customers.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(customers[0])); w.writeheader(); w.writerows(customers)
    def default(o): return o.isoformat() if isinstance(o, date) else str(o)
    (OUT / "policies.json").write_text(json.dumps({"records": out_pol}, indent=1, default=default), encoding="utf-8")
    part1 = [c for c in claims if str(c["claim_id"]).strip().upper() <= "CLM-000900"]
    part2 = [c for c in claims if c not in part1]
    for name, rows in (("claims_2022_2023.csv", part1), ("claims_2024.csv", part2)):
        with (OUT / name).open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(claims[0])); w.writeheader(); w.writerows(rows)
    print(f"customers={len(customers)} policies={len(out_pol)} claims={len(claims)} -> {OUT}")


if __name__ == "__main__":
    main()
