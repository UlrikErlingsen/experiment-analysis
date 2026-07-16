"""Design audit and decision rules for randomized between-subject experiments."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd

from .errors import DataProblem


def arm_labels(frame: pd.DataFrame, factors: list[str] | tuple[str, ...]) -> pd.Series:
    """Create stable, readable cell labels from one to three treatment factors."""
    if not factors:
        raise DataProblem("Choose at least one treatment factor.")
    parts = []
    for factor in factors:
        if factor not in frame.columns:
            raise DataProblem(f"The treatment factor ‘{factor}’ is not in the data.")
        values = frame[factor].astype("string").fillna("(missing)")
        parts.append(factor + "=" + values)
    result = parts[0]
    for part in parts[1:]:
        result = result + " · " + part
    return result.astype(str)


def ordered_levels(series: pd.Series) -> list[str]:
    """Return deterministic string levels without treating missing as an arm."""
    return sorted(series.dropna().astype(str).unique().tolist(), key=str.casefold)


@dataclass(frozen=True)
class AuditResult:
    summary: dict[str, object]
    arm_counts: pd.DataFrame
    outcome_observation: pd.DataFrame
    covariate_balance: pd.DataFrame
    warnings: tuple[str, ...]


def _pooled_smd(left: pd.Series, right: pd.Series) -> float:
    left_values = pd.to_numeric(left, errors="coerce").dropna().to_numpy(float)
    right_values = pd.to_numeric(right, errors="coerce").dropna().to_numpy(float)
    if len(left_values) < 2 or len(right_values) < 2:
        return np.nan
    pooled = np.sqrt((np.var(left_values, ddof=1) + np.var(right_values, ddof=1)) / 2)
    if not np.isfinite(pooled) or pooled <= 0:
        return 0.0 if np.isclose(np.mean(left_values), np.mean(right_values)) else np.nan
    return float((np.mean(left_values) - np.mean(right_values)) / pooled)


def audit_experiment(
    frame: pd.DataFrame,
    *,
    unit: str | None,
    outcome: str,
    factors: list[str] | tuple[str, ...],
    covariates: list[str] | tuple[str, ...] = (),
) -> AuditResult:
    """Audit uniqueness, observed outcomes, cell sizes, and baseline balance."""
    if frame.empty:
        raise DataProblem("The dataset has no rows.")
    required = [outcome, *factors, *covariates]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise DataProblem("These selected columns are missing: " + ", ".join(missing))
    numeric_outcome = pd.to_numeric(frame[outcome], errors="coerce")
    if numeric_outcome.notna().sum() == 0:
        raise DataProblem("The primary outcome must be numeric.")

    factor_complete = frame[list(factors)].notna().all(axis=1)
    eligible = frame.loc[factor_complete].copy()
    if eligible.empty:
        raise DataProblem("No rows have complete treatment assignment.")
    eligible["__arm__"] = arm_labels(eligible, factors)
    arm_counts = (
        eligible.groupby("__arm__", observed=True)
        .size()
        .rename("assigned_rows")
        .reset_index()
        .rename(columns={"__arm__": "arm"})
        .sort_values("arm")
        .reset_index(drop=True)
    )
    observed = pd.to_numeric(eligible[outcome], errors="coerce").notna()
    outcome_observation = (
        eligible.assign(__observed__=observed)
        .groupby("__arm__", observed=True)["__observed__"]
        .agg(assigned_rows="size", observed_outcomes="sum", observation_rate="mean")
        .reset_index()
        .rename(columns={"__arm__": "arm"})
        .sort_values("arm")
        .reset_index(drop=True)
    )

    balance_rows: list[dict[str, object]] = []
    levels = ordered_levels(eligible["__arm__"])
    for covariate in covariates:
        numeric = pd.to_numeric(eligible[covariate], errors="coerce")
        for left, right in combinations(levels, 2):
            smd = _pooled_smd(numeric[eligible["__arm__"] == right], numeric[eligible["__arm__"] == left])
            balance_rows.append(
                {
                    "covariate": covariate,
                    "contrast": f"{right} − {left}",
                    "standardized_mean_difference": smd,
                    "absolute_smd": abs(smd) if np.isfinite(smd) else np.nan,
                }
            )
    covariate_balance = pd.DataFrame(
        balance_rows,
        columns=["covariate", "contrast", "standardized_mean_difference", "absolute_smd"],
    )

    duplicate_units = 0
    missing_units = 0
    if unit and unit in frame.columns:
        missing_units = int(frame[unit].isna().sum())
        duplicate_units = int(frame.loc[frame[unit].notna(), unit].duplicated(keep=False).sum())
    rates = outcome_observation["observation_rate"].astype(float)
    observation_gap = float(rates.max() - rates.min()) if len(rates) else np.nan
    min_arm = int(arm_counts["assigned_rows"].min())
    max_arm = int(arm_counts["assigned_rows"].max())
    max_abs_smd = (
        float(covariate_balance["absolute_smd"].max())
        if not covariate_balance.empty and covariate_balance["absolute_smd"].notna().any()
        else np.nan
    )
    warnings: list[str] = []
    if duplicate_units:
        warnings.append("The selected unit identifier repeats; independence may be false or the data may be long-form.")
    if missing_units:
        warnings.append("Some rows have no unit identifier, so uniqueness cannot be fully checked.")
    if len(levels) < 2:
        warnings.append("Fewer than two treatment cells are available.")
    if min_arm < 10:
        warnings.append("At least one treatment cell has fewer than 10 assigned rows; robust intervals can be unstable.")
    if np.isfinite(observation_gap) and observation_gap > 0.10:
        warnings.append("Outcome observation rates differ by more than 10 percentage points across cells.")
    if np.isfinite(max_abs_smd) and max_abs_smd > 0.25:
        warnings.append("A declared baseline covariate has |SMD| above 0.25; inspect assignment and chance imbalance.")

    return AuditResult(
        summary={
            "source_rows": int(len(frame)),
            "assigned_rows": int(len(eligible)),
            "treatment_cells": int(len(levels)),
            "minimum_cell_n": min_arm,
            "maximum_cell_n": max_arm,
            "duplicate_unit_rows": duplicate_units,
            "missing_unit_rows": missing_units,
            "outcome_observation_gap": observation_gap,
            "maximum_absolute_smd": max_abs_smd,
        },
        arm_counts=arm_counts,
        outcome_observation=outcome_observation,
        covariate_balance=covariate_balance,
        warnings=tuple(warnings),
    )


def classify_decision(
    *,
    estimate: float,
    ci_low: float,
    ci_high: float,
    minimum_effect: float,
    randomized_confirmed: bool,
    audit: AuditResult,
) -> dict[str, str]:
    """Apply a transparent interval-and-design decision rule; never gate on p alone."""
    threshold = max(0.0, float(minimum_effect))
    summary = audit.summary
    severe_design_risk = (
        int(summary["duplicate_unit_rows"]) > 0
        or int(summary["minimum_cell_n"]) < 10
        or float(summary["outcome_observation_gap"]) > 0.10
    )
    if not randomized_confirmed:
        return {
            "status": "ASSOCIATION ONLY",
            "meaning": "Random assignment is not confirmed, so the contrast is descriptive rather than causal.",
            "action": "Resolve the assignment mechanism or describe this as an adjusted association.",
        }
    if severe_design_risk:
        return {
            "status": "DESIGN AT RISK",
            "meaning": "A severe uniqueness, cell-size, or outcome-observation warning limits the causal claim.",
            "action": "Investigate the flagged design issue before acting on the estimated effect.",
        }
    if threshold <= 0:
        return {
            "status": "DIRECTIONAL ONLY",
            "meaning": (
                "No positive minimum worthwhile effect was declared, so this reading is only a zero-null "
                "significance statement, not a practical decision."
            ),
            "action": (
                "Declare a minimum worthwhile effect in outcome units, from economics or policy, "
                "then re-read the decision."
            ),
        }
    if ci_low > threshold:
        return {
            "status": "MEANINGFUL LIFT",
            "meaning": "The full confidence interval is above the declared minimum worthwhile effect.",
            "action": "Check guardrails and implementation fidelity before scaling the tested treatment.",
        }
    if ci_high < -threshold:
        return {
            "status": "POTENTIAL HARM",
            "meaning": "The full confidence interval is below the negative practical threshold.",
            "action": "Do not scale; inspect mechanism, implementation, and adverse outcomes.",
        }
    if threshold > 0 and ci_low >= -threshold and ci_high <= threshold:
        return {
            "status": "BOUNDED SMALL",
            "meaning": "The full confidence interval lies inside the declared not-worth-acting band.",
            "action": "Treat the tested change as practically small at this precision; revisit only if costs or stakes change.",
        }
    direction = "positive" if estimate >= 0 else "negative"
    return {
        "status": "UNCERTAIN",
        "meaning": f"The {direction} point estimate is not precise enough to clear a practical decision boundary.",
        "action": "Keep the decision open; improve precision, fidelity, or the design rather than reading p as a verdict.",
    }
