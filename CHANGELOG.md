# Changelog

## 1.3.0 — 2026-10-03

Larger datasets for large organisations. Estimates, intervals, decision rules and the evidence-pack schema are unchanged; on the fictional demos every number is identical to 1.2.0.

### Larger datasets

- Larger datasets: run locally, Experiment Signal has no built-in limit on file size, rows or columns any more (it was 50 MB, 250,000 rows and 500 columns); memory is the limit, and running out of memory is reported as a plain message instead of a crash. The public demo (`SIGNAL_PUBLIC=1`) keeps the old values as demo limits — 50 MB, 250,000 rows, 500 columns — plus at most 4,999 randomization permutations, and its messages say the downloaded app has none. All caps live in `experimentsignal/limits.py`.
- The sharp-null permutation test runs on a seeded random subsample of 100,000 complete rows when there are more, a visible approximation that keeps it within seconds; the result carries `rows_used` and a `subsample_note`, the note is shown on the effects page and repeated in the analysis warnings and the evidence pack. Below 100,000 rows it uses every row, exactly as before. The HC3 estimates, intervals, audit and term tests always use all rows.
- Faster and leaner on big tables: treatment cells and factors are pandas categoricals, which the model formula reads as integer codes (a 1,000,000-row 2×2 analysis with a covariate drops from about 11 s to under 2 s; 5,000,000 rows take about 8 s); the audit no longer copies the whole uploaded table; column roles for the design-contract form are computed once per distinct value and cached per loaded table, and the audit is cached per table and saved contract, so widget changes no longer re-scan every row; uploads are parsed without an extra copy. Reading and analysis show a spinner.
- Streamlit's upload cap is 10,000 MB: `.streamlit/config.toml` (synced from Signal Hub), both launchers (`run_app.bat` now honors `EXPERIMENTSIGNAL_MAX_UPLOAD_MB` like `run_app.command`, default 10000) and the Dockerfile (`STREAMLIT_SERVER_MAX_UPLOAD_SIZE=10000`).

### Suite

- Suite: Rival, Reach, Learn and Blueprint Signal added to the suite table.

## 1.2.0 — 2026-10-02

Signal brand refresh and Signal Hub entry point. The analysis, statistics, decision rules, data contract and exports are unchanged.

### Brand

- Display name written **Experiment Signal** (with a space) in the app, README, docs, launchers, citation and the evidence-pack product label. Package, file, schema and environment-variable names stay `experimentsignal` / `EXPERIMENTSIGNAL_*`.
- The app uses the shared `signal_theme` module (Organic Signal design, Decide family colour `#4f80a2`, Figtree): sidebar lockup, masthead, hero, cards, notes, decision card, footer and the mark as favicon replace the pasted styles.
- The pairwise contrast chart uses the per-app Plotly template and the shared semantic colours (estimate, interval, practical-threshold band, zero line); its meaning is unchanged.
- New banner, social preview and marks in `assets/`; the old banner SVG is removed. `.streamlit/config.toml` uses the family colours and keeps the 50 MB upload limit.
- README follows the Signal template; bug-report and feature-request issue templates added.
- Embedded Figtree font, no Google Fonts request: the theme ships the font as `signal_font.py`, so the app makes no outbound font request. Chart colours after the family accent follow a per-family contrast order.

### Signal Hub contract

- Opens with the fictional demo preloaded: the deterministic 2×2 factorial demo and its design contract load on first run, so the audit and analysis work without an upload. The demo buttons restore or switch demos, and an upload replaces the demo.
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
