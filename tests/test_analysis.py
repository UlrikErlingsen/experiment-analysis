from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from experimentsignal.analysis import (
    AnalysisConfig,
    analyze_experiment,
    newcombe_hybrid_interval,
    plan_two_arm_binary_sample,
    plan_two_arm_sample,
    wilson_score_interval,
)
from experimentsignal.examples import demo_dataframe, demo_defaults


def two_arm_frame() -> pd.DataFrame:
    baseline = np.tile(np.linspace(-1.5, 1.5, 30), 2)
    arm = np.repeat(["Control", "Treatment"], 30)
    noise = np.tile(np.linspace(-0.8, 0.8, 30), 2)
    outcome = 5 + 0.6 * baseline + noise + (arm == "Treatment") * 1.25
    return pd.DataFrame({"unit": range(60), "arm": arm, "baseline": baseline, "outcome": outcome})


def test_unadjusted_two_arm_difference_matches_means() -> None:
    frame = two_arm_frame()
    config = AnalysisConfig(
        outcome="outcome",
        factors=("arm",),
        covariates=(),
        control_arm="arm=Control",
        treatment_arm="arm=Treatment",
        permutations=199,
    )
    result = analyze_experiment(frame, config)

    expected = frame.loc[frame["arm"] == "Treatment", "outcome"].mean() - frame.loc[
        frame["arm"] == "Control", "outcome"
    ].mean()
    assert np.isclose(result.primary["estimate"], expected)
    assert result.primary["ci_low"] < expected < result.primary["ci_high"]
    assert result.permutation is not None
    assert result.permutation["permutations"] == 199


def test_covariate_adjusted_factorial_demo_recovers_planted_contrast() -> None:
    frame = demo_dataframe()
    defaults = demo_defaults()
    result = analyze_experiment(
        frame,
        AnalysisConfig(
            outcome=defaults["outcome"],
            factors=tuple(defaults["factors"]),
            covariates=tuple(defaults["covariates"]),
            control_arm=defaults["control_arm"],
            treatment_arm=defaults["treatment_arm"],
            minimum_effect=defaults["minimum_effect"],
        ),
    )

    assert 1.2 < result.primary["estimate"] < 1.9
    assert result.primary["ci_low"] > 0.9
    assert len(result.group_summary) == 4
    assert len(result.contrasts) == 6
    assert any(result.term_tests["term"].str.contains(":"))
    terms = result.term_tests["term"].tolist()
    assert "message_frame" in terms
    assert "message_frame:proof_badge" in terms
    assert "baseline_familiarity_0_10" in terms
    assert result.permutation is None


def test_holm_adjustment_is_never_smaller_than_raw_p_value() -> None:
    defaults = demo_defaults()
    result = analyze_experiment(
        demo_dataframe(),
        AnalysisConfig(
            outcome=defaults["outcome"],
            factors=tuple(defaults["factors"]),
            covariates=tuple(defaults["covariates"]),
            control_arm=defaults["control_arm"],
            treatment_arm=defaults["treatment_arm"],
        ),
    )
    finite = result.contrasts.dropna(subset=["p_value_exploratory", "p_value_holm"])
    assert (finite["p_value_holm"] >= finite["p_value_exploratory"] - 1e-15).all()
    assert (finite["p_value_holm"] <= 1).all()


def test_randomization_inference_is_deterministic() -> None:
    config = AnalysisConfig(
        outcome="outcome",
        factors=("arm",),
        covariates=(),
        control_arm="arm=Control",
        treatment_arm="arm=Treatment",
        permutations=499,
        seed=44,
    )
    first = analyze_experiment(two_arm_frame(), config).permutation
    second = analyze_experiment(two_arm_frame(), config).permutation
    assert first == second


def test_two_arm_power_planner_returns_plausible_and_attrition_inflated_counts() -> None:
    plan = plan_two_arm_sample(
        minimum_effect=0.4,
        outcome_sd=1.0,
        alpha=0.05,
        power=0.80,
        allocation_ratio=1.0,
        expected_attrition=0.10,
    )
    assert 95 <= plan["complete_control"] <= 105
    assert plan["complete_control"] == plan["complete_treatment"]
    assert plan["assign_total"] > plan["complete_total"]


def test_binary_outcome_reports_adjusted_risk_difference_and_descriptive_ratios() -> None:
    frame = pd.DataFrame(
        {
            "unit": range(200),
            "arm": ["Control"] * 100 + ["Treatment"] * 100,
            "converted": ["yes"] * 20 + ["no"] * 80 + ["yes"] * 35 + ["no"] * 65,
        }
    )
    result = analyze_experiment(
        frame,
        AnalysisConfig(
            outcome="converted",
            factors=("arm",),
            covariates=(),
            control_arm="arm=Control",
            treatment_arm="arm=Treatment",
            outcome_type="binary",
            success_value="yes",
            permutations=199,
        ),
    )
    assert np.isclose(result.primary["estimate"], 0.15)
    assert np.isclose(result.primary["risk_ratio_descriptive"], 1.75)
    assert result.primary["effect_scale"] == "risk difference"
    assert result.diagnostics["outcome_type"] == "binary"
    assert np.isnan(result.primary["hedges_g_descriptive"])


def test_newcombe_interval_matches_hand_checked_published_example() -> None:
    # Newcombe (1998), example (a): 56/70 versus 48/80 at 95% confidence.
    low, high = wilson_score_interval(56, 70, alpha=0.05)
    assert low == pytest.approx(0.6918335550, abs=1e-9)
    assert high == pytest.approx(0.8769526075, abs=1e-9)
    lower, upper = newcombe_hybrid_interval(48, 80, 56, 70, alpha=0.05)
    assert lower == pytest.approx(0.0524314724, abs=1e-9)
    assert upper == pytest.approx(0.3338726540, abs=1e-9)
    # Boundary counts stay estimable and inside [-1, 1].
    boundary = newcombe_hybrid_interval(0, 40, 40, 40, alpha=0.05)
    assert -1.0 <= boundary[0] <= boundary[1] <= 1.0


def _two_arm_binary_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "unit": range(150),
            "arm": ["Control"] * 80 + ["Treatment"] * 70,
            "converted": ["yes"] * 48 + ["no"] * 32 + ["yes"] * 56 + ["no"] * 14,
        }
    )


def test_unadjusted_binary_contrast_is_proportion_difference_with_newcombe_interval() -> None:
    result = analyze_experiment(
        _two_arm_binary_frame(),
        AnalysisConfig(
            outcome="converted",
            factors=("arm",),
            covariates=(),
            control_arm="arm=Control",
            treatment_arm="arm=Treatment",
            outcome_type="binary",
            success_value="yes",
            permutations=499,
        ),
    )
    # The LPM contrast without covariates equals the raw proportion difference exactly.
    assert result.primary["estimate"] == pytest.approx(56 / 70 - 48 / 80, abs=1e-12)
    assert result.primary["interval_method"] == "Newcombe hybrid Wilson score"
    assert result.primary["ci_low"] == pytest.approx(0.0524314724, abs=1e-9)
    assert result.primary["ci_high"] == pytest.approx(0.3338726540, abs=1e-9)
    assert result.diagnostics["interval_method"] == "Newcombe hybrid Wilson score"
    # The sharp-null permutation check is enabled: difference in proportions is the mean difference.
    assert result.permutation is not None
    assert result.permutation["statistic"] == "absolute difference in success proportions"
    assert 0 < float(result.permutation["two_sided_p_value"]) <= 1


def test_adjusted_binary_outcome_keeps_hc3_lpm_interval_and_withholds_permutation() -> None:
    rng = np.random.default_rng(11)
    frame = _two_arm_binary_frame()
    frame["baseline"] = rng.normal(5, 1, len(frame)).round(2)
    result = analyze_experiment(
        frame,
        AnalysisConfig(
            outcome="converted",
            factors=("arm",),
            covariates=("baseline",),
            control_arm="arm=Control",
            treatment_arm="arm=Treatment",
            outcome_type="binary",
            success_value="yes",
        ),
    )
    assert result.primary["interval_method"] == "HC3 t"
    assert result.permutation is None
    assert any("linear-probability" in warning for warning in result.warnings)


def test_binary_power_planner_uses_absolute_probability_lift() -> None:
    plan = plan_two_arm_binary_sample(
        control_rate=0.10,
        minimum_lift=0.03,
        alpha=0.05,
        power=0.80,
        expected_attrition=0.10,
    )
    assert plan["treatment_rate"] == pytest.approx(0.13)
    assert plan["complete_total"] > 1000
    assert plan["assign_total"] > plan["complete_total"]
