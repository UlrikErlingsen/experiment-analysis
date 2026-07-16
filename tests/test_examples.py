from __future__ import annotations

from experimentsignal.examples import demo_dataframe, demo_defaults, starter_template


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

