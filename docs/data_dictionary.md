# Data Dictionary - InsureData Pipeline

All data is **synthetic** (`scripts/generate_sample_data.py`, seed 2024).

## customers.csv  (PK `customer_id`)
| Column | Type | Null? | Rule |
|---|---|---|---|
| customer_id | string upper/trim | No | missing -> reject `missing_customer_id` |
| full_name | string (Title Case) | Yes | |
| date_of_birth | date | Yes | invalid/unparseable, future, or age > 110 -> set null (warning `invalid_dob_set_null`); record kept |
| region | North/South/East/West/Unknown | Yes | case/space normalized; anything else -> `Unknown` |
| segment | string | Yes | Retail/SME/Premium |
| signup_date, updated_at | date | Yes | `updated_at` decides duplicates |
Duplicates: latest `updated_at` wins (tie: later row); others rejected as `superseded_duplicate`. Derived: `age` (years at as-of date).

## policies.json  (PK `policy_id`, FK `customer_id` -> customers)
| Column | Type | Rule |
|---|---|---|
| policy_id | string | missing -> `missing_policy_id`; later duplicates -> `duplicate_policy_id` |
| customer_id | string | not in curated customers -> `orphan_customer_ref` |
| policy_type | Auto/Home/Health/Life | alias map in config (`Motor`->Auto, `property`->Home ...); unknown -> `unknown_policy_type` |

#Updated
| start_date, end_date | date | invalid -> `invalid_dates`; end <= start -> `end_not_after_start`; duration > configured maximum (default 2 calendar years) -> `policy_term_exceeds_limit` |

| annual_premium | float > 0 | `$`/commas accepted; missing/<=0/text -> `invalid_premium` |
| coverage_limit | float | missing -> 0 (meaning "unknown", no cap) |
| status | Active/Lapsed | |

## claims_2022_2023.csv, claims_2024.csv  (PK `claim_id`, FK `policy_id` -> policies)
| Column | Type | Rule |
|---|---|---|
| claim_id | string | missing -> `missing_claim_id`; later duplicate -> `duplicate_claim_id` |
| policy_id | string | not in curated policies -> `orphan_policy_ref` |
| claim_date | date | invalid -> `invalid_claim_date`; outside [start_date, end_date] of its policy -> `claim_outside_policy_period` |
| claim_amount | float > 0 | else `invalid_amount` |
| claim_status | Open/Approved/Paid/Rejected | alias map (`denied`->Rejected, `pending`->Open); unknown -> `unknown_claim_status` |
| claim_type | string | |
Flag: `exceeds_coverage_limit` (amount > coverage_limit when limit > 0), kept, incurred capped.

## Curated tables
`dim_customer`; `dim_policy` = policies + customer attributes (`full_name, region, segment, age, age_band, premium_band, term_days`); `fact_claims` = claims + policy context (`policy_type, region, claim_month, days_since_policy_start, is_incurred, incurred_amount`).

## Metric definitions
- `claim_frequency` = number of valid claims / number of policies in the group (no exposure adjustment).
- `incurred_amount` = sum over claims with status != Rejected of min(claim_amount, coverage_limit) (no cap if limit = 0).
- `loss_ratio` = incurred_amount / sum(annual_premium) (written, not earned premium).
- `avg_claim_amount` = mean claim_amount of valid claims (includes Rejected, uncapped).
- `approval_rate` = (Approved + Paid) / (Approved + Paid + Rejected); Open excluded.
Units: currency amounts in a single unspecified currency.

## Intentionally injected errors (counts at generation)
Customers: 15 newer + 6 older duplicate versions; 8 lowercase/space IDs; 6 bad DOBs; 9 odd regions. Policies: 12 type aliases + 1 unknown type; ~20% `$` premiums; 6 invalid premiums; 5 end=start; 10 unknown customers; 6 duplicate rows. Claims: 25 unknown policies; 30 outside period; 8 invalid amounts; 6 status aliases/unknowns; 8 above coverage; 10 duplicate IDs; 5 lowercase/space IDs. Some injected faults overlap or cascade, so rejected counts in outputs are not simple sums.

## Output zones
`staging/` raw-as-text copy; `curated/`; `rejected/` (+ `reject_reasons`, `source_file`, `source_row`); `reporting/`.
