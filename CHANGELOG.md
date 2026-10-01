# Changelog

## 1.2.0 — 2026-10-02

Signal brand refresh and Signal Hub entry point. The analysis, statistics, decision rules, data contract and exports are unchanged.

### Brand

- Display name written **Experiment Signal** (with a space) in the app, README, docs, launchers, citation and the evidence-pack product label. Package, file, schema and environment-variable names stay `experimentsignal` / `EXPERIMENTSIGNAL_*`.
- The app uses the shared `signal_theme` module (Organic Signal design, Decide family colour `#4f80a2`, Figtree): sidebar lockup, masthead, hero, cards, notes, decision card, footer and the mark as favicon replace the pasted styles.
- The pairwise contrast chart uses the per-app Plotly template and the shared semantic colours (estimate, interval, practical-threshold band, zero line); its meaning is unchanged.
- New banner, social preview and marks in `assets/`; the old banner SVG is removed. `.streamlit/config.toml` uses the family colours and keeps the 50 MB upload limit.
- README follows the Signal template; bug-report and feature-request issue templates added.

### Signal Hub contract

- `experimentsignal.ui` exposes `APP_INFO` and `render()`, so Signal Hub can embed the app; `app.py` is now a thin standalone entry point.
- All session-state and widget keys are namespaced `experiment:` (including the page selector). Loading a demo, uploading a file or applying a template still re-seeds the contract form.
- `streamlit` and `plotly` moved to a `ui` extra (also in `test`); the analysis core installs without them. `requirements.txt` still lists everything.
- The UI reads no repository-root files: demos are generated in code and the marks ship as package data.
- New tests: no Streamlit/Plotly import outside `experimentsignal.ui`, `render()` runs from a script without a page config and from a copy holding only the packaged files, every widget key is namespaced, and the README follows the Signal template.

## 1.1.1 — 2026-07-16

### Security

- Export sanitizer now also neutralizes formula-like column headers and strips control characters; Docker images keep application code root-owned; defusedxml hardens workbook XML parsing. Treatment-arm labels are HTML-escaped in the primary-estimand note.

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
