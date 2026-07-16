# ExperimentSignal data guide

## One row per randomized unit

The analysis unit should match the randomization unit. If a person was randomized, use one row per person. If a store, market, household, team, session, or device was randomized, version 1.0 is not automatically appropriate: outcomes within those units may be dependent and cluster-aware inference is required.

Choose an identifier only for duplicate detection. The app excludes row-level identifiers from its evidence pack.

## Keep assignment, not only exposure

Treatment columns should record the randomized assignment. Replacing assignment with observed exposure can break the randomized comparison when units do not comply. ExperimentSignal does not estimate complier effects or per-protocol causal effects.

For factorial designs, use one column per randomized factor:

| unit_id | message_frame | proof_badge | primary_outcome |
|---|---|---|---:|
| U001 | Clarity | Absent | 4.2 |
| U002 | Momentum | Verified | 5.8 |

The app creates cell labels such as `message_frame=Momentum · proof_badge=Verified` and asks for a primary cell-to-cell contrast.

## Keep rows with missing outcomes

Do not delete assigned rows merely because the primary outcome is missing. Leave the outcome blank so the audit can calculate observation rates by assigned cell. The estimator uses complete cases across outcome, treatment factors, and declared covariates; it does not impute missing values or correct attrition bias.

Outcome missingness can destroy the comparability created by random assignment. Similar observation rates are reassuring only in a limited sense; missingness can still be outcome-related inside every cell.

## Outcome

Version 1.0 treats the selected primary outcome as continuous and fits a linear mean model. A bounded rating may be defensible as approximately interval-scaled, but the assumption should be stated. Binary conversion, counts, ordered categories, durations, and time-to-event outcomes need different outcome models and uncertainty calculations.

Use one primary outcome for the decision. Guardrails and secondary outcomes should be declared and analyzed with a multiplicity plan outside this release.

## Treatment factors

Choose one to three treatment columns with two to eight observed levels each. Do not use post-randomization segments, data-driven clusters, or outcome-defined categories as treatment factors. Empty cells, tiny cells, or treatment combinations that were never randomized can make factorial terms unidentified.

## Baseline covariates

Optional covariates must be numeric and determined before assignment could affect them. Useful candidates include a pre-period outcome, a stratification variable encoded appropriately, or a stable pre-treatment measure strongly related to the outcome.

Do not control for mediators, treatment receipt, post-treatment satisfaction, downstream engagement, or any field affected by treatment. ExperimentSignal centers covariates and allows their outcome slopes to differ by treatment cell. Constant covariates are rejected.

## Accepted files and safety

- CSV: one header row and one rectangular table.
- XLSX: the first worksheet is read; macros are not executed.
- JSON: an array of row objects or an object with a `data` array.

Uploads are limited to 50 MB, 250,000 rows, and 500 columns. Remove direct identifiers, contact data, free text, precise locations, and unnecessary sensitive attributes before upload.

