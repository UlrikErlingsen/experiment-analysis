from __future__ import annotations

from experimentsignal.analysis import AnalysisConfig, analyze_experiment
from experimentsignal.examples import (
    BINARY_TRUE_CONTROL_RATE,
    BINARY_TRUE_TREATMENT_RATE,
    binary_demo_dataframe,
    binary_demo_defaults,
    contract_templates,
    demo_dataframe,
    demo_defaults,
    starter_template,
)


def test_demo_is_deterministic_and_wholly_synthetic_shape() -> None:
    first = demo_dataframe()
    second = demo_dataframe()
    assert first.equals(second)
    assert len(first) == 480
    assert first["unit_id"].is_unique
    assert set(first["message_frame"]) == {"Clarity", "Momentum"}
    assert set(first["proof_badge"]) == {"Absent", "Verified"}
    assert demo_defaults()["minimum_effect"] == 0.40


def test_starter_template_exposes_required_roles() -> None:
    template = starter_template()
    assert list(template.columns) == ["unit_id", "treatment", "primary_outcome", "baseline_measure"]


def test_binary_demo_is_deterministic_with_two_arms_and_two_outcome_values() -> None:
    first = binary_demo_dataframe()
    second = binary_demo_dataframe()
    assert first.equals(second)
    assert len(first) == 800
    assert first["unit_id"].is_unique
    assert set(first["message_variant"]) == {"Standard message", "Benefit-led message"}
    assert set(first["recalled_key_claim"]) == {"recalled", "not_recalled"}
    assert first["message_variant"].value_counts().tolist() == [400, 400]


def test_binary_demo_analysis_interval_covers_the_true_six_point_lift() -> None:
    defaults = binary_demo_defaults()
    result = analyze_experiment(
        binary_demo_dataframe(),
        AnalysisConfig(
            outcome=str(defaults["outcome"]),
            factors=tuple(defaults["factors"]),
            covariates=(),
            control_arm=str(defaults["control_arm"]),
            treatment_arm=str(defaults["treatment_arm"]),
            outcome_type="binary",
            success_value=str(defaults["success_value"]),
            permutations=0,
        ),
    )
    true_lift = BINARY_TRUE_TREATMENT_RATE - BINARY_TRUE_CONTROL_RATE
    assert result.primary["interval_method"] == "Newcombe hybrid Wilson score"
    assert float(result.primary["ci_low"]) < true_lift < float(result.primary["ci_high"])
    assert abs(float(result.primary["estimate"]) - true_lift) < 0.05


def test_contract_templates_prefill_fields_only_and_never_fabricate_data() -> None:
    templates = contract_templates()
    assert list(templates) == ["Communication test", "Price test", "Feature rollout"]
    assert templates["Communication test"]["outcome_type"] == "binary"
    assert templates["Price test"]["outcome_type"] == "binary"
    assert templates["Feature rollout"]["outcome_type"] == "continuous"
    assert "PriceSignal" in str(templates["Price test"]["note"])
    for template in templates.values():
        # Templates carry wording and outcome type, never column choices, thresholds, or data.
        for forbidden in ("outcome", "factors", "covariates", "control_arm", "treatment_arm", "minimum_effect", "data"):
            assert forbidden not in template

