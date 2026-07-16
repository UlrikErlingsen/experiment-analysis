# ExperimentSignal decision guide

## Before opening the outcome

1. Name the randomized unit and assignment mechanism.
2. Freeze the target population, primary outcome, primary cell contrast, analysis population, exclusions, and stopping rule.
3. Set the smallest effect worth acting on in outcome units.
4. Declare guardrails and the action attached to each possible result.
5. Confirm that baseline covariates precede treatment and were selected for precision, not because they change significance.

If these choices are reconstructed after reading outcomes, label the analysis exploratory and replicate it prospectively.

## Read the audit before the estimate

- Repeated unit IDs can mean the data are long-form, the randomization unit is wrong, or observations are dependent.
- Small cells make robust covariance unstable and interactions fragile.
- Differential outcome observation can break comparability after randomization.
- Large baseline SMDs deserve a check of the randomization pipeline and a covariate-adjusted sensitivity analysis.
- Small SMDs do not verify random assignment.

Never delete assigned rows merely to make the cells look balanced.

## Read the primary interval

Start with outcome units and the declared minimum effect. Ask which operationally important effects remain compatible with the interval. A narrow interval around a trivial effect can be more useful than a statistically significant but economically small estimate.

Then inspect:

- whether guardrails moved adversely;
- whether treatment was delivered as assigned;
- whether novelty, seasonality, measurement, or interference limits generalization;
- whether the sample matches the rollout population;
- whether the exact implementation can be repeated.

## Treat other contrasts as a family

The Holm-adjusted table helps control false positives across displayed pairwise tests, but it does not rescue outcome-driven contrast selection. If the primary contrast disappoints and a secondary cell looks attractive, call it a new hypothesis and run a confirmation experiment.

Factorial main effects average over other factors. When an interaction is present, report concrete cell means and contrasts rather than speaking as though one universal main effect applies.

## Status is not authorization

`MEANINGFUL LIFT` says the declared interval clears the declared effect threshold under the app's assumptions. It does not certify profitability, fairness, safety, legality, brand fit, technical feasibility, or external validity.

`UNCERTAIN` is an information state, not a failed experiment. Decide whether the value of additional information justifies a larger, cleaner, or better measured test.

`BOUNDED SMALL` is often a useful answer: at the achieved precision, effects large enough to justify action are not compatible with the interval. Revisit only if the decision threshold or implementation changes.

## Write the handoff

Record:

- assignment mechanism and unit;
- target and analysis populations;
- primary outcome and time window;
- primary contrast and effect threshold;
- cell counts, outcome-observation rates, and baseline audit;
- point estimate and interval in outcome units;
- guardrails, fidelity, and adverse events;
- exact decision and owner;
- unresolved threats and the next learning action.

Keep the evidence pack with the analysis plan and experiment log, not as a substitute for them.

