<p align="center">
  <img src="assets/experimentsignal-banner.svg" alt="ExperimentSignal — did the treatment cause a change worth acting on?" width="100%">
</p>

<p align="center">
  <a href="https://github.com/UlrikErlingsen/experiment-analysis/actions/workflows/tests.yml"><img alt="Tests" src="https://github.com/UlrikErlingsen/experiment-analysis/actions/workflows/tests.yml/badge.svg"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-173C3A?logo=python&logoColor=white">
  <img alt="Streamlit" src="https://img.shields.io/badge/Streamlit-app-D95B40?logo=streamlit&logoColor=white">
  <a href="LICENSE"><img alt="License: AGPL-3.0-or-later" src="https://img.shields.io/badge/License-AGPL--3.0--or--later-36534E"></a>
</p>

<p align="center"><strong>Open experiment decision support — declare the contrast, audit the design, estimate the effect, preserve the uncertainty.</strong></p>

**ExperimentSignal** helps analysts, marketers, and product teams decide whether a randomized between-subject treatment caused a change large enough to matter. It combines a written design contract, assignment and missingness audit, robust adjusted cell means, pairwise contrast families, factorial decomposition, practical decision bounds, prospective power planning, and a reproducible evidence pack.

Everything runs locally with open-source Python packages. There is no account, telemetry, external AI call, remote database, or built-in persistence.

## Read this first

> **The app estimates contrasts; it does not manufacture randomization.** A causal interpretation requires a valid assignment process, one observation per randomized unit, treatment before outcome, acceptable outcome observation, limited interference, faithful implementation, and an analysis matched to the design.

ExperimentSignal never uses `p < .05` as a rollout rule. The declared treatment-minus-control estimate and confidence interval are compared with a minimum worthwhile effect in outcome units. P-values remain visible as supporting diagnostics and are explicitly labeled exploratory.

## Supported scope

Version 1.0 supports:

- individually randomized, between-subject experiments;
- one to three treatment factors, with two to eight levels per factor;
- a continuous numeric primary outcome;
- a declared cell-to-cell primary contrast;
- optional numeric **pre-treatment** covariates;
- covariate-adjusted cell means with cell-specific slopes and HC3 covariance;
- all pairwise cell contrasts with Holm-adjusted exploratory p-values;
- robust Type-II factorial term tests and descriptive partial eta-squared;
- Welch's unequal-variance omnibus diagnostic;
- fixed-seed sharp-null permutation inference for unadjusted two-arm, one-factor experiments;
- prospective two-arm independent-means sample-size planning.

It does **not** claim support for clustered assignment, repeated measures, paired or crossover studies, binary/count/survival outcomes, noncompliance estimands, adaptive or sequential designs, blocking-specific randomization inference, interference, missing-outcome correction, heterogeneous-effect discovery, or observational causal identification. Those designs need methods matched to their assignment and outcome structure.

## Try it in three minutes

1. Start the app and click **Load fictional 2×2 demo**.
2. Review the saved design contract: two randomized factors, one continuous primary outcome, one baseline covariate, and a 0.40-point minimum worthwhile effect.
3. Open the audit. Compare assigned counts, outcome observation rates, and baseline standardized differences across the four cells.
4. Run the declared analysis. Read the primary adjusted contrast and its HC3 confidence interval before opening the test-statistic details.
5. Review the factorial interaction and the full pairwise family without changing the primary contrast.
6. Open the decision page and export the privacy-minimized evidence record.

The example is deterministic synthetic data for a fictional service. It represents no real person, organization, course case, or empirical result.

## Data layout

Use one row per randomized unit. CSV, XLSX, and JSON are supported.

| unit_id | treatment | primary_outcome | baseline_measure |
|---|---|---:|---:|
| U001 | Control | 4.2 | 3.9 |
| U002 | Treatment | 5.1 | 4.1 |

For a factorial design, use one column per randomized factor. Treatment labels should describe assignment, not observed exposure after noncompliance. Keep rows with missing outcomes so the audit can compare outcome-observation rates by assigned cell. See the [data guide](docs/data-guide.md).

## Analysis contract

The app requires a named:

- randomized unit identifier;
- primary continuous outcome;
- one to three treatment factors;
- control and treatment cells for the primary contrast;
- minimum worthwhile effect in outcome units;
- target population, assignment mechanism, analysis population, stopping rule, and guardrail;
- optional pre-treatment covariates.

Covariates are centered at their complete-sample means. The adjusted model interacts each treatment cell with each declared covariate, then standardizes cell predictions to those centered values. This follows the logic of agnostic regression adjustment for randomized experiments while keeping the specific cell contrast primary. See [methods](docs/methods.md).

## Reading the decision status

- **MEANINGFUL LIFT:** the full interval is above the positive minimum worthwhile effect.
- **POTENTIAL HARM:** the full interval is below the negative boundary.
- **BOUNDED SMALL:** the full interval lies inside the symmetric not-worth-acting band.
- **UNCERTAIN:** the interval crosses a practical boundary.
- **DIRECTIONAL ONLY:** no positive minimum worthwhile effect was declared, so the reading is only a zero-null significance statement, never presented as a decision. The contract page refuses to save a zero threshold.
- **ASSOCIATION ONLY:** random assignment is not confirmed.
- **DESIGN AT RISK:** a severe uniqueness, cell-size, or outcome-observation audit flag is present.

These are transparent evidence readings, not automatic launch approvals. Costs, guardrails, external validity, treatment fidelity, novelty effects, ethics, and operational feasibility remain outside the estimator. See the [decision guide](docs/decision-guide.md).

## Evidence pack

Excel, CSV-ZIP, and JSON exports include:

- source filename, sheet, and SHA-256 fingerprint;
- the design contract and causal-status statement;
- software version and exact analysis settings;
- cell counts, outcome observation, and baseline-balance tables;
- adjusted cell means, primary and pairwise contrasts, factorial term tests, and diagnostics;
- the interval-based decision rule and warnings.

Unit-level identifiers, outcomes, covariates, fitted values, and residuals are excluded. Exported text is neutralized against spreadsheet-formula interpretation.

## Run locally

You need Python 3.10 or newer and a local copy of this folder.

**macOS:** double-click `run_app.command`.

**Windows:** double-click `run_app.bat`.

The first launch creates a private `.venv` and downloads open-source dependencies. Later launches reuse it. Or use a terminal:

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

ExperimentSignal prefers local port `8592` and falls back to another free port on macOS. The macOS launcher honors the `EXPERIMENTSIGNAL_PORT`, `EXPERIMENTSIGNAL_NO_BROWSER`, and `EXPERIMENTSIGNAL_MAX_UPLOAD_MB` environment variables; the Windows launcher honors `EXPERIMENTSIGNAL_PORT` only. Setting `EXPERIMENTSIGNAL_DEBUG=1` in the app's environment reveals technical error details on either platform. Uploads are always capped at ExperimentSignal's 50 MB safety limit, so `EXPERIMENTSIGNAL_MAX_UPLOAD_MB` can only lower the Streamlit upload limit below 50 MB, never raise it.

### Docker

```bash
docker build -t experimentsignal .
docker run --rm -p 8592:8592 experimentsignal
```

Then open `http://127.0.0.1:8592`. The container runs as a non-root user.

## No install? Give this file to an AI

[AI_ANALYST.md](AI_ANALYST.md) is a standalone analysis protocol for a capable AI assistant. It contains the same scope limits, calculations, honesty rules, and output structure. A local app is the more private option: a cloud AI sees whatever you upload or paste.

## Development checks

```bash
python -m pip install -e ".[test]"
python -m pytest
python -m ruff check .
python -m build
```

The suite checks known two-arm calculations, synthetic factorial recovery, HC3 interval structure, Holm multiplicity, deterministic randomization inference, SMD auditing, missing outcomes, decision boundaries, power calculations, safe imports/exports, example generation, and every Streamlit page.

## Relationship to the Signal tools

- **[WorthSignal](https://github.com/UlrikErlingsen/customer-value-analytics)** asks what customers and relationships are worth.
- **[SegmentSignal](https://github.com/UlrikErlingsen/customer-segmentation)** asks whether customers form stable, useful groups.
- **[ChoiceSignal](https://github.com/UlrikErlingsen/conjoint-analysis)** asks how product attributes drive choice.
- **[AdoptSignal](https://github.com/UlrikErlingsen/adoption-forecasting)** asks when a new product gets adopted.
- **[PositionSignal](https://github.com/UlrikErlingsen/brand-positioning)** asks where brands sit relative to competitors.
- **[AllocSignal](https://github.com/UlrikErlingsen/marketing-mix-allocation)** asks where the next marketing budget should go.
- **[DriverSignal](https://github.com/UlrikErlingsen/survey-driver-analysis)** asks which measured experiences move with satisfaction and deserve a causal test.
- **[GateSignal](https://github.com/UlrikErlingsen/launch-decision-gate)** asks whether a concept should receive the next bounded investment.
- **[MeasureSignal](https://github.com/UlrikErlingsen/measurement-validation)** asks whether a multi-item score measures what you think it does.
- **[TextSignal](https://github.com/UlrikErlingsen/open-text-analysis)** asks what recurring language patterns appear in open-ended responses.
- **ExperimentSignal** asks whether an assigned treatment caused a practically meaningful change.

## Method references

- Neyman, J. (1923/1990). On the Application of Probability Theory to Agricultural Experiments. *Statistical Science, 5*(4), 465–472. https://doi.org/10.1214/ss/1177012031
- Rubin, D. B. (1974). Estimating causal effects of treatments in randomized and nonrandomized studies. *Journal of Educational Psychology, 66*, 688–701. https://doi.org/10.1037/h0037350
- Welch, B. L. (1951). On the Comparison of Several Mean Values: An Alternative Approach. *Biometrika, 38*, 330–336. https://doi.org/10.1093/biomet/38.3-4.330
- MacKinnon, J. G., & White, H. (1985). Some heteroskedasticity-consistent covariance matrix estimators with improved finite sample properties. *Journal of Econometrics, 29*, 305–325. https://doi.org/10.1016/0304-4076(85)90158-7
- Long, J. S., & Ervin, L. H. (2000). Using heteroscedasticity consistent standard errors in the linear regression model. *The American Statistician, 54*(3), 217–224. https://doi.org/10.1080/00031305.2000.10474549
- Holm, S. (1979). A Simple Sequentially Rejective Multiple Test Procedure. *Scandinavian Journal of Statistics, 6*, 65–70. https://www.jstor.org/stable/4615733
- Lin, W. (2013). Agnostic notes on regression adjustments to experimental data. *Annals of Applied Statistics, 7*, 295–318. https://doi.org/10.1214/12-AOAS583
- Wasserstein, R. L., & Lazar, N. A. (2016). The ASA Statement on p-Values. *The American Statistician, 70*, 129–133. https://doi.org/10.1080/00031305.2016.1154108
- Lakens, D. (2013). Calculating and reporting effect sizes to facilitate cumulative science. *Frontiers in Psychology, 4*, 863. https://doi.org/10.3389/fpsyg.2013.00863

## Originality and license

ExperimentSignal is an independent implementation based on public statistical literature and original synthetic examples. It does not reproduce lecture slides, institution-specific cases, teaching diagrams, exercises, assessment questions, or proprietary wording. See [sources and originality](docs/sources-and-originality.md).

The software and documentation are free under **AGPL-3.0-or-later**. The license covers this project's expression, not ownership of the published statistical methods it implements.

This application was developed with AI coding assistance and checked through source review, analytical fixtures, deterministic synthetic recovery, automated app tests, and visual inspection. Verify material decisions independently; no warranty is provided.

