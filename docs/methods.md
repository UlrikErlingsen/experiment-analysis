# ExperimentSignal methods

## Analysis contract

ExperimentSignal estimates mean contrasts for individually randomized, between-subject experiments with a continuous outcome. The primary estimand is the declared treatment-cell mean minus the declared control-cell mean for the declared target population and analysis population.

Potential outcomes motivate the causal interpretation: each unit has an outcome under each treatment condition, but only the assigned condition is observed. Random assignment supports exchangeability of treatment groups in repeated assignments. Identification also requires treatment versions and interference to be acceptably controlled, outcome measurement to be comparable, and missingness not to destroy exchangeability.

## Design audit

Before estimation, the app reports:

- source and treatment-assigned rows;
- assigned count per treatment cell;
- duplicate and missing unit identifiers;
- observed primary outcomes and observation rate per assigned cell;
- the maximum observation-rate gap;
- pairwise standardized mean differences for declared baseline covariates.

For baseline covariate `X`, the pairwise SMD is:

`SMD = (mean_treatment − mean_control) / sqrt((variance_treatment + variance_control) / 2)`

SMD is not a test of the randomization mechanism. A randomized experiment can show imbalance by chance, and balanced observed covariates do not prove randomization or balance unmeasured variables. The app flags |SMD| above 0.25 for inspection, not automatic adjustment or rejection.

## Adjusted cell-mean model

Let `A` denote the full treatment cell created by all selected factors and let `X_c` be centered pre-treatment covariates. ExperimentSignal fits:

`Y = cell indicators + X_c + cell × X_c interactions + error`

This is a saturated treatment-cell interaction adjustment. It allows covariate slopes to differ by cell, following the conservative regression-adjustment logic discussed by Lin (2013). Adjusted cell means are predictions at `X_c = 0`, the complete-sample average declared covariate profile.

The primary contrast is a linear combination of those adjusted means. Confidence intervals use HC3 heteroskedasticity-consistent covariance and a residual-degrees-of-freedom t critical value. HC3 addresses heteroskedasticity and some finite-sample leverage behavior; it does not address clustering, repeated outcomes, selection, interference, noncompliance, model extrapolation, or post-treatment controls.

Without covariates, adjusted means equal ordinary treatment-cell sample means and contrasts reduce to differences in means.

## Effect sizes

Every contrast is reported in the original outcome units. A descriptive Hedges' g also divides the unadjusted difference in observed cell means by the pooled within-cell standard deviation and applies the small-sample correction:

`J = 1 − 3 / (4(n_t + n_c − 2) − 1)`

`g = J × (mean_t − mean_c) / pooled_SD`

The raw-unit effect is primary because the practical decision boundary is expressed on the same outcome scale. Generic small/medium/large labels are not used.

## Pairwise multiplicity

With `k` treatment cells, the app constructs all `k(k−1)/2` pairwise contrasts. Their exploratory two-sided p-values use the same HC3 covariance and receive Holm's sequentially rejective Bonferroni adjustment across the displayed family. Holm adjustment strongly controls familywise Type-I error under arbitrary dependence.

The primary confidence interval is not widened for the exploratory family because the primary contrast is declared separately. If several contrasts are genuinely co-primary, the analysis plan needs simultaneous intervals or another explicit multiplicity allocation.

## Factorial term tests

For multiple selected factors, a separate factorial model estimates all selected factor interactions plus additive declared covariates. A robust Type-II ANOVA table reports omnibus F tests. Type-II terms average over the other terms subject to the model parameterization; when interactions are present, a specific cell contrast is generally easier to interpret.

Partial eta-squared is reported descriptively as:

`partial eta² = SS_term / (SS_term + SS_residual)`

Its sums of squares are model-based and should not be confused with the robust F-test covariance or with a causal effect in outcome units.

## Welch omnibus diagnostic

The app also reports Welch's unequal-variance one-way omnibus comparison across complete treatment cells. It tests whether all cell means are equal without assuming equal variances. It does not say which contrast matters and does not replace the declared effect estimate.

## Randomization inference

For unadjusted data with exactly one two-level factor, treatment labels are permuted with their observed group sizes fixed. The statistic is the absolute difference in cell means. With `B` random permutations, the reported two-sided Monte Carlo p-value is:

`p = (1 + number(|T_perm| ≥ |T_observed|)) / (B + 1)`

The fixed seed makes the calculation reproducible. The null is Fisher's sharp null that every unit's outcome would be identical under either assignment. That is stronger than a zero average treatment effect. Covariate adjustment, factorial assignment, blocking, clustering, and restricted randomization require design-matched permutation procedures and are withheld.

## Missing data

The estimator uses rows complete on the outcome, all selected treatment factors, and all declared covariates. It reports source rows and complete-case retention and performs no imputation. The audit retains rows with observed assignment but missing outcomes when calculating observation rates.

Complete-case estimates can be biased if outcome or covariate observation depends on treatment and potential outcomes. Similar observed rates do not establish ignorability. Sensitivity analysis, weighting, multiple imputation, bounds, or follow-up recovery may be needed.

## Decision bounds

Let `delta` be the declared minimum worthwhile effect, with symmetric boundaries `−delta` and `+delta`.

- `MEANINGFUL LIFT` if the entire confidence interval is above `+delta`.
- `POTENTIAL HARM` if the entire interval is below `−delta`.
- `BOUNDED SMALL` if the entire interval lies inside `[−delta, +delta]` and `delta > 0`.
- `UNCERTAIN` otherwise.

This interval logic is intentionally more demanding than point-estimate or p-value thresholding. It is not a full economic model and does not replace guardrail analysis. Randomization or audit failures override the effect status with `ASSOCIATION ONLY` or `DESIGN AT RISK`.

With `delta = 0` the rule degenerates: "the interval excludes zero" is mathematically identical to the `p < alpha` significance rule that ExperimentSignal refuses to present as a decision. The contract page therefore blocks saving a zero minimum worthwhile effect, and if a zero threshold nevertheless reaches the classifier, the status becomes `DIRECTIONAL ONLY` — a statement that only a zero-null significance reading is available, with a request to declare a positive threshold in outcome units before any practical decision is read.

## Prospective power

The planner solves the conventional fixed-sample, two-sided independent-means t-test for a standardized effect `d = delta / expected_SD`, alpha, target power, and allocation ratio. The result is inflated by `1/(1−expected_attrition)` and rounded upward by arm.

This is approximate planning—not achieved power, post-hoc power, or assurance. The SD and minimum effect should come from prior data, a pilot, economics, measurement resolution, or stakeholder consequences. Clustered, repeated, sequential, covariate-adjusted, and multiple-outcome designs need dedicated planning.

## References

- Neyman, J. (1923/1990). *Statistical Science, 5*(4), 465–472. https://doi.org/10.1214/ss/1177012031
- Rubin, D. B. (1974). *Journal of Educational Psychology, 66*, 688–701. https://doi.org/10.1037/h0037350
- Welch, B. L. (1951). *Biometrika, 38*, 330–336. https://doi.org/10.1093/biomet/38.3-4.330
- MacKinnon, J. G., & White, H. (1985). *Journal of Econometrics, 29*, 305–325. https://doi.org/10.1016/0304-4076(85)90158-7
- Long, J. S., & Ervin, L. H. (2000). Using heteroscedasticity consistent standard errors in the linear regression model. *The American Statistician, 54*(3), 217–224. https://doi.org/10.1080/00031305.2000.10474549
- Holm, S. (1979). *Scandinavian Journal of Statistics, 6*, 65–70. https://www.jstor.org/stable/4615733
- Lin, W. (2013). *Annals of Applied Statistics, 7*, 295–318. https://doi.org/10.1214/12-AOAS583
- Wasserstein, R. L., & Lazar, N. A. (2016). *The American Statistician, 70*, 129–133. https://doi.org/10.1080/00031305.2016.1154108
- Lakens, D. (2013). *Frontiers in Psychology, 4*, 863. https://doi.org/10.3389/fpsyg.2013.00863

