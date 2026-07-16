from __future__ import annotations

import numpy as np
import pandas as pd

from experimentsignal.analysis import AnalysisConfig, analyze_experiment, plan_two_arm_sample
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
