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
from statsmodels.stats.power import NormalIndPower, TTestIndPower
from statsmodels.stats.proportion import proportion_effectsize
from statsmodels.stats.anova import anova_lm

from .design import arm_labels, encode_binary_outcome, ordered_levels
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
    outcome_type: str = "continuous"
    success_value: str | None = None


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
    if config.outcome_type == "binary":
        if config.success_value is None:
            raise DataProblem("Choose which observed binary value means success.")
        work["outcome"] = encode_binary_outcome(work["outcome"], config.success_value)
    elif config.outcome_type == "continuous":
        work["outcome"] = pd.to_numeric(work["outcome"], errors="coerce")
    else:
        raise DataProblem("Outcome type must be continuous or binary.")
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


def wilson_score_interval(successes: int, trials: int, alpha: float) -> tuple[float, float]:
    """Wilson (1927) score interval for one proportion."""
    if trials <= 0 or not 0 <= successes <= trials:
        raise DataProblem("A Wilson interval needs 0 ≤ successes ≤ trials with at least one trial.")
    z = float(stats.norm.ppf(1 - alpha / 2))
    proportion = successes / trials
    center = 2 * trials * proportion + z * z
    spread = z * math.sqrt(z * z + 4 * trials * proportion * (1 - proportion))
    denominator = 2 * (trials + z * z)
    return (center - spread) / denominator, (center + spread) / denominator


def newcombe_hybrid_interval(
    successes_control: int,
    trials_control: int,
    successes_treatment: int,
    trials_treatment: int,
    alpha: float,
) -> tuple[float, float]:
    """Newcombe (1998) method 10 hybrid Wilson score interval for a difference in proportions.

    The interval is for treatment risk minus control risk, on the probability scale.
    """
    p_control = successes_control / trials_control if trials_control else np.nan
    p_treatment = successes_treatment / trials_treatment if trials_treatment else np.nan
    low_control, high_control = wilson_score_interval(successes_control, trials_control, alpha)
    low_treatment, high_treatment = wilson_score_interval(successes_treatment, trials_treatment, alpha)
    difference = p_treatment - p_control
    lower = difference - math.sqrt((p_treatment - low_treatment) ** 2 + (high_control - p_control) ** 2)
    upper = difference + math.sqrt((high_treatment - p_treatment) ** 2 + (p_control - low_control) ** 2)
    return float(lower), float(upper)


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
    outcome_type: str,
    use_newcombe: bool = False,
) -> dict[str, object]:
    vector = x_right - x_left
    estimate = float(vector @ params)
    variance = float(vector @ covariance @ vector)
    standard_error = math.sqrt(max(variance, 0.0))
    statistic = estimate / standard_error if standard_error > 0 else np.nan
    p_value = float(2 * stats.t.sf(abs(statistic), df_resid)) if np.isfinite(statistic) else np.nan
    critical = float(stats.t.ppf(1 - alpha / 2, df_resid))
    left_values = outcomes[arms == left].dropna().to_numpy(float)
    right_values = outcomes[arms == right].dropna().to_numpy(float)
    left_rate = float(np.mean(left_values)) if len(left_values) else np.nan
    right_rate = float(np.mean(right_values)) if len(right_values) else np.nan
    risk_ratio = right_rate / left_rate if outcome_type == "binary" and left_rate > 0 else np.nan
    left_odds = left_rate / (1 - left_rate) if outcome_type == "binary" and 0 < left_rate < 1 else np.nan
    right_odds = right_rate / (1 - right_rate) if outcome_type == "binary" and 0 < right_rate < 1 else np.nan
    if use_newcombe and len(left_values) and len(right_values):
        ci_low, ci_high = newcombe_hybrid_interval(
            int(round(left_values.sum())),
            len(left_values),
            int(round(right_values.sum())),
            len(right_values),
            alpha,
        )
        interval_method = "Newcombe hybrid Wilson score"
    else:
        ci_low = estimate - critical * standard_error
        ci_high = estimate + critical * standard_error
        interval_method = "HC3 t"
    return {
        "control_arm": left,
        "treatment_arm": right,
        "contrast": f"{right} − {left}",
        "estimate": estimate,
        "standard_error_hc3": standard_error,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "interval_method": interval_method,
        "p_value_exploratory": p_value,
        "effect_scale": "risk difference" if outcome_type == "binary" else "mean difference",
        "hedges_g_descriptive": (
            _hedges_g(outcomes, arms, left, right) if outcome_type == "continuous" else np.nan
        ),
        "risk_ratio_descriptive": risk_ratio,
        "odds_ratio_descriptive": right_odds / left_odds if np.isfinite(left_odds) and left_odds > 0 else np.nan,
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
        "statistic": (
            "absolute difference in success proportions"
            if config.outcome_type == "binary"
            else "absolute difference in means"
        ),
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
    use_newcombe = config.outcome_type == "binary" and not config.covariates
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
            outcome_type=config.outcome_type,
            use_newcombe=use_newcombe,
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
        outcome_type=config.outcome_type,
        use_newcombe=use_newcombe,
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
    if config.outcome_type == "binary":
        if use_newcombe:
            warnings.append(
                "Binary contrasts without covariates are raw risk differences with Newcombe hybrid Wilson score intervals; "
                "exploratory p-values come from the HC3 linear-probability model."
            )
        else:
            warnings.append(
                "Covariate-adjusted binary outcomes use an HC3 linear-probability model; "
                "the primary estimate is an adjusted risk difference."
            )
        adjusted = group_summary["adjusted_mean"].to_numpy(float)
        if np.any((adjusted < 0) | (adjusted > 1)):
            warnings.append(
                "At least one adjusted probability falls outside 0–1; treat the linear adjustment as locally descriptive."
            )

    welch_p = np.nan
    if config.outcome_type == "continuous":
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
            "outcome_type": config.outcome_type,
            "effect_measure": (
                ("risk difference" if use_newcombe else "adjusted risk difference")
                if config.outcome_type == "binary"
                else "adjusted mean difference"
            ),
            "interval_method": str(primary["interval_method"]),
            "success_value": config.success_value if config.outcome_type == "binary" else None,
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


def plan_two_arm_binary_sample(
    *,
    control_rate: float,
    minimum_lift: float,
    alpha: float,
    power: float,
    allocation_ratio: float = 1.0,
    expected_attrition: float = 0.0,
) -> dict[str, float | int]:
    """Approximate fixed-sample planning for a two-sided independent-proportions comparison."""
    treatment_rate = control_rate + minimum_lift
    if not 0 < control_rate < 1 or not 0 < treatment_rate < 1:
        raise DataProblem("Control rate and control rate plus minimum lift must both lie strictly between 0 and 1.")
    if not 0 < alpha < 0.5 or not 0.5 < power < 1:
        raise DataProblem("Use alpha between 0 and 0.5 and power between 0.5 and 1.")
    if allocation_ratio <= 0 or not 0 <= expected_attrition < 0.8:
        raise DataProblem("Allocation ratio must be positive and attrition must be between 0% and 80%.")
    effect_size = abs(float(proportion_effectsize(treatment_rate, control_rate)))
    n_control_complete = int(
        math.ceil(
            NormalIndPower().solve_power(
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
        "control_rate": float(control_rate),
        "treatment_rate": float(treatment_rate),
        "minimum_lift": float(minimum_lift),
        "arcsine_effect": effect_size,
        "complete_control": n_control_complete,
        "complete_treatment": n_treatment_complete,
        "complete_total": n_control_complete + n_treatment_complete,
        "assign_control": n_control_assign,
        "assign_treatment": n_treatment_assign,
        "assign_total": n_control_assign + n_treatment_assign,
    }
