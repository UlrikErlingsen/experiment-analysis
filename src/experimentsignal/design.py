"""Design audit and decision rules for randomized between-subject experiments."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd

from .errors import DataProblem


def arm_categorical(frame: pd.DataFrame, factors: list[str] | tuple[str, ...]) -> pd.Series:
    """Cell labels as a categorical Series whose categories are the observed labels in sorted order.

    Labels are built once per distinct factor combination rather than once per row, so millions of rows cost
    integer codes instead of millions of label strings.
    """
    if not factors:
        raise DataProblem("Choose at least one treatment factor.")
    codes_so_far = np.zeros(len(frame), dtype=np.int64)
    labels_so_far: list[str] = [""]
    for factor in factors:
        if factor not in frame.columns:
            raise DataProblem(f"The treatment factor ‘{factor}’ is not in the data.")
        codes, uniques = pd.factorize(frame[factor], use_na_sentinel=True)
        names = [*pd.Index(uniques).astype("string").fillna("(missing)").astype(str), "(missing)"]
        codes = np.where(codes < 0, len(names) - 1, codes).astype(np.int64)
        pair_codes, pairs = pd.factorize(codes_so_far * len(names) + codes)
        labels_so_far = [
            (labels_so_far[pair // len(names)] + " · " if labels_so_far[pair // len(names)] else "")
            + f"{factor}={names[pair % len(names)]}"
            for pair in np.asarray(pairs, dtype=np.int64).tolist()
        ]
        codes_so_far = pair_codes.astype(np.int64)
    categories = sorted(set(labels_so_far))
    position = {label: index for index, label in enumerate(categories)}
    remap = np.array([position[label] for label in labels_so_far], dtype=np.int64)
    values = pd.Categorical.from_codes(remap[codes_so_far] if len(frame) else [], categories=categories)
    return pd.Series(values, index=frame.index, name="arm")


def arm_labels(frame: pd.DataFrame, factors: list[str] | tuple[str, ...]) -> pd.Series:
    """Create stable, readable cell labels from one to three treatment factors."""
    return arm_categorical(frame, factors).astype(str)


def ordered_levels(series: pd.Series) -> list[str]:
    """Return deterministic string levels without treating missing as an arm."""
    if isinstance(series.dtype, pd.CategoricalDtype):
        present = series.cat.remove_unused_categories().cat.categories
        return sorted({str(value) for value in present}, key=str.casefold)
    uniques = pd.unique(series.dropna())
    return sorted({str(value) for value in uniques}, key=str.casefold)


def encode_binary_outcome(series: pd.Series, success_value: object) -> pd.Series:
    """Encode a declared two-level outcome as 1=success and 0=other, retaining missing rows."""
    codes, uniques = pd.factorize(series, use_na_sentinel=True)
    names = np.array([str(value) for value in uniques], dtype=object)
    levels = sorted(set(names.tolist()), key=str.casefold)
    if len(levels) != 2:
        raise DataProblem("A binary outcome must contain exactly two observed non-missing values.")
    success = str(success_value)
    if success not in levels:
        raise DataProblem("The declared success value is not present in the observed binary outcome.")
    lookup = np.append((names == success).astype(float), np.nan)
    return pd.Series(lookup[codes], index=series.index, dtype=float)


def _distinct_text_count(uniques: np.ndarray) -> int:
    """Distinct values after text conversion, counted from the distinct raw values instead of every row."""
    if len(uniques) > 64:
        # Distinct values only collapse when different types print alike (1 and "1"); far above 8 either way.
        return len(uniques)
    return len({str(value) for value in uniques})


def column_roles(frame: pd.DataFrame) -> dict[str, list[str]]:
    """Columns usable as numeric outcomes or covariates, binary outcomes, and treatment factors (2–8 levels).

    Same rules as converting every cell to text or numbers, but evaluated once per distinct value so a
    multi-million-row upload stays responsive.
    """
    numeric: list[str] = []
    binary: list[str] = []
    factor: list[str] = []
    for column in frame.columns:
        series = frame[column]
        if pd.api.types.is_numeric_dtype(series.dtype):
            is_numeric = int(series.notna().sum()) >= 2
            uniques = pd.unique(series.dropna())
        else:
            codes, uniques = pd.factorize(series, use_na_sentinel=True)
            uniques = np.asarray(uniques, dtype=object)
            convertible = pd.to_numeric(pd.Series(uniques, dtype=object), errors="coerce").notna().to_numpy()
            if convertible.sum() >= 2:
                is_numeric = True
            elif convertible.any():
                is_numeric = int((codes == int(np.flatnonzero(convertible)[0])).sum()) >= 2
            else:
                is_numeric = False
        if is_numeric:
            numeric.append(column)
        distinct = _distinct_text_count(np.asarray(uniques))
        if distinct == 2:
            binary.append(column)
        if 2 <= distinct <= 8:
            factor.append(column)
    return {"numeric": numeric, "binary": binary, "factor": factor}


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
    outcome_type: str = "continuous",
    success_value: object | None = None,
) -> AuditResult:
    """Audit uniqueness, observed outcomes, cell sizes, and baseline balance."""
    if frame.empty:
        raise DataProblem("The dataset has no rows.")
    required = [outcome, *factors, *covariates]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise DataProblem("These selected columns are missing: " + ", ".join(missing))
    if outcome_type == "binary":
        if success_value is None:
            raise DataProblem("Choose which observed binary value means success.")
        observed_outcome = encode_binary_outcome(frame[outcome], success_value)
    elif outcome_type == "continuous":
        observed_outcome = pd.to_numeric(frame[outcome], errors="coerce")
        if observed_outcome.notna().sum() == 0:
            raise DataProblem("The primary continuous outcome must be numeric.")
    else:
        raise DataProblem("Outcome type must be continuous or binary.")

    factor_complete = frame[list(factors)].notna().all(axis=1).to_numpy()
    if not factor_complete.any():
        raise DataProblem("No rows have complete treatment assignment.")
    # Work on the selected columns of eligible rows only; never copy the whole uploaded table.
    arms = arm_categorical(frame.loc[factor_complete, list(factors)], factors)
    observed = pd.Series(observed_outcome.to_numpy()[factor_complete], index=arms.index).notna()
    outcome_observation = (
        observed.groupby(arms, observed=True)
        .agg(assigned_rows="size", observed_outcomes="sum", observation_rate="mean")
        .reset_index()
        .rename(columns={"index": "arm"})
    )
    outcome_observation["arm"] = outcome_observation["arm"].astype(str)
    outcome_observation = outcome_observation.sort_values("arm").reset_index(drop=True)
    arm_counts = outcome_observation[["arm", "assigned_rows"]].copy()

    balance_rows: list[dict[str, object]] = []
    levels = ordered_levels(arms)
    arm_codes = arms.cat.codes.to_numpy()
    arm_position = {str(label): code for code, label in enumerate(arms.cat.categories)}
    for covariate in covariates:
        numeric = pd.to_numeric(frame[covariate], errors="coerce").to_numpy(dtype=float)[factor_complete]
        for left, right in combinations(levels, 2):
            smd = _pooled_smd(
                pd.Series(numeric[arm_codes == arm_position[right]]),
                pd.Series(numeric[arm_codes == arm_position[left]]),
            )
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
            "assigned_rows": int(len(arms)),
            "treatment_cells": int(len(levels)),
            "minimum_cell_n": min_arm,
            "maximum_cell_n": max_arm,
            "duplicate_unit_rows": duplicate_units,
            "missing_unit_rows": missing_units,
            "outcome_observation_gap": observation_gap,
            "maximum_absolute_smd": max_abs_smd,
            "outcome_type": outcome_type,
            "success_value": str(success_value) if outcome_type == "binary" else None,
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
