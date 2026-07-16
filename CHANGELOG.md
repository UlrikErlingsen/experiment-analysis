# Changelog

## 1.1.0 — 2026-07-16

- Added declared binary outcomes for clicks, conversions, purchases, recall, disclosure recognition, and other two-level endpoints.
- Added Newcombe (1998) hybrid Wilson score intervals for unadjusted binary risk differences, and HC3 linear-probability intervals for covariate-adjusted risk differences, with the bounded-outcome caveat flagged.
- Added descriptive risk/odds ratios, binary audit preservation, two-proportion sample-size planning via Cohen's arcsine effect, and the sharp-null permutation check for unadjusted two-arm binary data.
- Added contract templates — communication test, price test, feature rollout — that prefill contract fields only and never fabricate data.
- Added a seeded two-arm binary message demonstration (n = 800, true rates 0.30 vs 0.36) with its own demo button and example files.
- Declared the binary minimum worthwhile effect in percentage points; it must still be positive.
- Kept the risk difference primary and labels ratio estimates as descriptive rather than silently switching estimands.

## 1.0.0 — 2026-07-16

- First public-ready release.
- Added one-way and factorial between-subject experiment analysis.
- Added adjusted cell means, HC3 intervals, Holm-adjusted pairwise tests, Welch omnibus diagnostics, and limited sharp-null permutation inference.
- Added design auditing, practical decision bounds, prospective two-arm power planning, and privacy-minimized evidence exports.
