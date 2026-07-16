"""Robust estimation for randomized between-subject experiments."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import math

import numpy as np
import pandas as pd
import patsy
import scipy.stats as stats
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.oneway import anova_oneway
from statsmodels.stats.power import TTestIndPower
from statsmodels.stats.anova import anova_lm

from .design import arm_labels, ordered_levels
from .errors import DataProblem


@dataclass(frozen=True)
class AnalysisConfig:
    outcome: str
    factors: tuple[str, ...]
    covariates: tuple[str, ...]
    control_arm: str
    treatment_arm: str
    alpha: float = 0.05
    minimum_effect: float = 0.0
    permutations: int = 4999
    seed: int = 260716


@dataclass(frozen=True)
class AnalysisResult:
    config: AnalysisConfig
    group_summary: pd.DataFrame
    contrasts: pd.DataFrame
    term_tests: pd.DataFrame
    diagnostics: dict[str, object]
    primary: dict[str, object]
    permutation: dict[str, object] | None
    warnings: tuple[str, ...]
    model_formula: str


def _prepare(frame: pd.DataFrame, config: AnalysisConfig) -> tuple[pd.DataFrame, dict[str, str]]:
    selected = [config.outcome, *config.factors, *config.covariates]
    missing = [column for column in selected if column not in frame.columns]
    if missing:
        raise DataProblem("These selected columns are missing: " + ", ".join(missing))
    if not 1 <= len(config.factors) <= 3:
        raise DataProblem("Choose one to three between-subject treatment factors.")
    work = frame[selected].copy()
    rename = {config.outcome: "outcome"}
    rename.update({name: f"factor_{index}" for index, name in enumerate(config.factors, start=1)})
    rename.update({name: f"covariate_{index}" for index, name in enumerate(config.covariates, start=1)})
    work = work.rename(columns=rename)
    work["outcome"] = pd.to_numeric(work["outcome"], errors="coerce")
    for old_name in config.covariates:
        work[rename[old_name]] = pd.to_numeric(work[rename[old_name]], errors="coerce")
    factor_names = [rename[name] for name in config.factors]
    for name in factor_names:
        work[name] = work[name].astype("string")
    complete_columns = ["outcome", *factor_names, *[rename[name] for name in config.covariates]]
    work = work.dropna(subset=complete_columns).copy()
    if len(work) < 20:
        raise DataProblem("Fewer than 20 complete rows remain; this release withholds model-based inference.")
    for name in factor_names:
        levels = ordered_levels(work[name])
        if len(levels) < 2:
            raise DataProblem(f"Treatment factor ‘{name}’ has fewer than two observed levels.")
        if len(levels) > 8:
            raise DataProblem(f"Treatment factor ‘{name}’ has more than eight levels; check that it is really a factor.")
    original_factor_names = list(config.factors)
    temp_for_arms = work.rename(columns={rename[name]: name for name in original_factor_names})
    work["arm"] = arm_labels(temp_for_arms, original_factor_names).to_numpy()
    for index, old_name in enumerate(config.covariates, start=1):
        new_name = f"covariate_{index}"
        sd = float(work[new_name].std(ddof=1))
        if not np.isfinite(sd) or sd <= 0:
            raise DataProblem(f"Baseline covariate ‘{old_name}’ is constant in the complete analysis sample.")
        work[new_name] = work[new_name] - float(work[new_name].mean())
    return work, rename


def _prediction_vector(model, arm: str, covariate_count: int) -> np.ndarray:
    values: dict[str, object] = {"arm": arm}
    values.update({f"covariate_{index}": 0.0 for index in range(1, covariate_count + 1)})
    matrix = patsy.build_design_matrices([model.model.data.design_info], pd.DataFrame([values]))[0]
    return np.asarray(matrix, dtype=float)[0]


def _hedges_g(outcomes: pd.Series, arms: pd.Series, left: str, right: str) -> float:
    left_values = outcomes[arms == left].dropna().to_numpy(float)
    right_values = outcomes[arms == right].dropna().to_numpy(float)
    if len(left_values) < 2 or len(right_values) < 2:
        return np.nan
    degrees = len(left_values) + len(right_values) - 2
    pooled_var = (
        (len(left_values) - 1) * np.var(left_values, ddof=1)
        + (len(right_values) - 1) * np.var(right_values, ddof=1)
    ) / degrees
    if pooled_var <= 0:
        return np.nan
    correction = 1 - 3 / (4 * degrees - 1) if degrees > 1 else 1.0
    return float(correction * (np.mean(right_values) - np.mean(left_values)) / np.sqrt(pooled_var))


def _contrast_row(
    *,
    left: str,
    right: str,
    x_left: np.ndarray,
    x_right: np.ndarray,
    params: np.ndarray,
    covariance: np.ndarray,
    df_resid: float,
    alpha: float,
    outcomes: pd.Series,
    arms: pd.Series,
) -> dict[str, object]:
    vector = x_right - x_left
    estimate = float(vector @ params)
    variance = float(vector @ covariance @ vector)
    standard_error = math.sqrt(max(variance, 0.0))
    statistic = estimate / standard_error if standard_error > 0 else np.nan
    p_value = float(2 * stats.t.sf(abs(statistic), df_resid)) if np.isfinite(statistic) else np.nan
    critical = float(stats.t.ppf(1 - alpha / 2, df_resid))
    return {
        "control_arm": left,
        "treatment_arm": right,
        "contrast": f"{right} − {left}",
        "estimate": estimate,
        "standard_error_hc3": standard_error,
        "ci_low": estimate - critical * standard_error,
        "ci_high": estimate + critical * standard_error,
        "p_value_exploratory": p_value,
        "hedges_g_descriptive": _hedges_g(outcomes, arms, left, right),
    }


def _term_tests(work: pd.DataFrame, config: AnalysisConfig) -> pd.DataFrame:
    factor_terms = " * ".join(f"C(factor_{index})" for index in range(1, len(config.factors) + 1))
    covariate_terms = " + ".join(f"covariate_{index}" for index in range(1, len(config.covariates) + 1))
    formula = "outcome ~ " + factor_terms + (" + " + covariate_terms if covariate_terms else "")
    model = smf.ols(formula, data=work).fit()
    if model.df_resid <= 0 or int(model.model.rank) < len(model.params):
        return pd.DataFrame(columns=["term", "df", "F_hc3", "p_value_exploratory", "partial_eta_squared_descriptive"])
    table = anova_lm(model, typ=2, robust="hc3").reset_index().rename(
        columns={"index": "term", "df": "df", "F": "F_hc3", "PR(>F)": "p_value_exploratory"}
    )
    residual_ss = float(table.loc[table["term"] == "Residual", "sum_sq"].iloc[0])
    table = table[table["term"] != "Residual"].copy()
    table["partial_eta_squared_descriptive"] = table["sum_sq"] / (table["sum_sq"] + residual_ss)
    declared_names = {f"C(factor_{index})": name for index, name in enumerate(config.factors, start=1)}
    declared_names.update({f"covariate_{index}": name for index, name in enumerate(config.covariates, start=1)})
    table["term"] = table["term"].map(
        lambda term: ":".join(declared_names.get(part, part) for part in str(term).split(":"))
    )
    return table[["term", "df", "F_hc3", "p_value_exploratory", "partial_eta_squared_descriptive"]]


def _permutation_test(work: pd.DataFrame, config: AnalysisConfig) -> dict[str, object] | None:
    levels = ordered_levels(work["arm"])
    if len(config.factors) != 1 or len(levels) != 2 or config.covariates or config.permutations <= 0:
        return None
    if config.control_arm not in levels or config.treatment_arm not in levels:
        return None
    values = work["outcome"].to_numpy(float)
    labels = work["arm"].to_numpy(str)
    observed = float(values[labels == config.treatment_arm].mean() - values[labels == config.control_arm].mean())
    rng = np.random.default_rng(config.seed)
    extreme = 0
    for _ in range(config.permutations):
        permuted = rng.permutation(labels)
        effect = float(values[permuted == config.treatment_arm].mean() - values[permuted == config.control_arm].mean())
        extreme += int(abs(effect) >= abs(observed) - 1e-12)
    return {
        "sharp_null": "No unit's outcome changes under either treatment",
        "observed_difference": observed,
        "permutations": int(config.permutations),
        "seed": int(config.seed),
        "two_sided_p_value": float((extreme + 1) / (config.permutations + 1)),
    }


def analyze_experiment(frame: pd.DataFrame, config: AnalysisConfig) -> AnalysisResult:
    """Estimate adjusted cell means and HC3 pairwise contrasts."""
    if not 0 < config.alpha < 0.5:
        raise DataProblem("Alpha must be between 0 and 0.5.")
    work, _ = _prepare(frame, config)
    levels = ordered_levels(work["arm"])
    if config.control_arm not in levels or config.treatment_arm not in levels:
        raise DataProblem("The selected primary contrast is not present in the complete analysis sample.")
    if config.control_arm == config.treatment_arm:
        raise DataProblem("Control and treatment must be different cells.")

    covariate_terms = " + ".join(f"covariate_{index}" for index in range(1, len(config.covariates) + 1))
    formula = "outcome ~ C(arm)" + (f" * ({covariate_terms})" if covariate_terms else "")
    ordinary = smf.ols(formula, data=work).fit()
    if ordinary.df_resid <= 0 or int(ordinary.model.rank) < len(ordinary.params):
        raise DataProblem("The adjusted model is rank deficient. Reduce factors/covariates or collect more complete cells.")
    robust = ordinary.get_robustcov_results(cov_type="HC3")
    params = np.asarray(robust.params, dtype=float)
    covariance = np.asarray(robust.cov_params(), dtype=float)
    vectors = {level: _prediction_vector(ordinary, level, len(config.covariates)) for level in levels}

    group_summary = (
        work.groupby("arm", observed=True)["outcome"]
        .agg(n="size", observed_mean="mean", observed_sd="std", observed_median="median")
        .reset_index()
        .sort_values("arm")
        .reset_index(drop=True)
    )
    group_summary["adjusted_mean"] = [float(vectors[level] @ params) for level in group_summary["arm"]]
    group_summary["adjusted_mean_se_hc3"] = [
        math.sqrt(max(float(vectors[level] @ covariance @ vectors[level]), 0.0)) for level in group_summary["arm"]
    ]

    contrast_rows = [
        _contrast_row(
            left=left,
            right=right,
            x_left=vectors[left],
            x_right=vectors[right],
            params=params,
            covariance=covariance,
            df_resid=float(robust.df_resid),
            alpha=config.alpha,
            outcomes=work["outcome"],
            arms=work["arm"],
        )
        for left, right in combinations(levels, 2)
    ]
    contrasts = pd.DataFrame(contrast_rows)
    finite = contrasts["p_value_exploratory"].notna()
    contrasts["p_value_holm"] = np.nan
    if finite.any():
        contrasts.loc[finite, "p_value_holm"] = multipletests(
            contrasts.loc[finite, "p_value_exploratory"].to_numpy(float), method="holm"
        )[1]
    primary = _contrast_row(
        left=config.control_arm,
        right=config.treatment_arm,
        x_left=vectors[config.control_arm],
        x_right=vectors[config.treatment_arm],
        params=params,
        covariance=covariance,
        df_resid=float(robust.df_resid),
        alpha=config.alpha,
        outcomes=work["outcome"],
        arms=work["arm"],
    )
    matching = contrasts[
        ((contrasts["control_arm"] == config.control_arm) & (contrasts["treatment_arm"] == config.treatment_arm))
        | ((contrasts["control_arm"] == config.treatment_arm) & (contrasts["treatment_arm"] == config.control_arm))
    ]
    primary["p_value_holm_family"] = float(matching["p_value_holm"].iloc[0]) if len(matching) else np.nan

    warnings: list[str] = []
    complete_rate = len(work) / len(frame)
    if complete_rate < 0.80:
        warnings.append("Fewer than 80% of source rows enter the complete-case adjusted model.")
    if any(group_summary["n"] < max(10, len(ordinary.params) + 2)):
        warnings.append("At least one cell is small relative to model complexity; HC3 intervals may still be unstable.")
    if len(config.covariates):
        warnings.append("Regression adjustment uses centered pre-treatment covariates and arm-specific slopes.")
    if len(config.factors) > 1:
        warnings.append("Factorial term tests are model-based decomposition; the declared cell contrast remains primary.")

    welch_p = np.nan
    try:
        groups = [work.loc[work["arm"] == level, "outcome"].to_numpy(float) for level in levels]
        welch_p = float(anova_oneway(groups, use_var="unequal", welch_correction=True).pvalue)
    except (ValueError, ZeroDivisionError, FloatingPointError):
        warnings.append("Welch's omnibus comparison could not be estimated for these cells.")

    return AnalysisResult(
        config=config,
        group_summary=group_summary,
        contrasts=contrasts,
        term_tests=_term_tests(work, config),
        diagnostics={
            "source_rows": int(len(frame)),
            "complete_analysis_rows": int(len(work)),
            "complete_case_rate": float(complete_rate),
            "parameters": int(len(ordinary.params)),
            "residual_df": float(robust.df_resid),
            "r_squared_descriptive": float(ordinary.rsquared),
            "adjusted_r_squared_descriptive": float(ordinary.rsquared_adj),
            "welch_omnibus_p_exploratory": welch_p,
            "covariance": "HC3",
        },
        primary=primary,
        permutation=_permutation_test(work, config),
        warnings=tuple(warnings),
        model_formula=formula,
    )


def plan_two_arm_sample(
    *,
    minimum_effect: float,
    outcome_sd: float,
    alpha: float,
    power: float,
    allocation_ratio: float = 1.0,
    expected_attrition: float = 0.0,
) -> dict[str, float | int]:
    """Approximate fixed-sample planning for a two-sided independent-means test."""
    if minimum_effect <= 0 or outcome_sd <= 0:
        raise DataProblem("Minimum effect and expected outcome SD must both be positive.")
    if not 0 < alpha < 0.5 or not 0.5 < power < 1:
        raise DataProblem("Use alpha between 0 and 0.5 and power between 0.5 and 1.")
    if allocation_ratio <= 0 or not 0 <= expected_attrition < 0.8:
        raise DataProblem("Allocation ratio must be positive and attrition must be between 0% and 80%.")
    effect_size = minimum_effect / outcome_sd
    n_control_complete = int(
        math.ceil(
            TTestIndPower().solve_power(
                effect_size=effect_size,
                nobs1=None,
                alpha=alpha,
                power=power,
                ratio=allocation_ratio,
                alternative="two-sided",
            )
        )
    )
    n_treatment_complete = int(math.ceil(n_control_complete * allocation_ratio))
    inflation = 1 / (1 - expected_attrition)
    n_control_assign = int(math.ceil(n_control_complete * inflation))
    n_treatment_assign = int(math.ceil(n_treatment_complete * inflation))
    return {
        "standardized_effect": float(effect_size),
        "complete_control": n_control_complete,
        "complete_treatment": n_treatment_complete,
        "complete_total": n_control_complete + n_treatment_complete,
        "assign_control": n_control_assign,
        "assign_treatment": n_treatment_assign,
        "assign_total": n_control_assign + n_treatment_assign,
    }
