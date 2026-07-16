from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from experimentsignal.design import arm_labels, audit_experiment, classify_decision
from experimentsignal.errors import DataProblem
from experimentsignal.examples import demo_dataframe, demo_defaults


def test_arm_labels_are_stable_and_explicit() -> None:
    frame = pd.DataFrame({"factor_a": ["B", "A"], "factor_b": ["On", "Off"]})
    assert arm_labels(frame, ["factor_a", "factor_b"]).tolist() == [
        "factor_a=B · factor_b=On",
        "factor_a=A · factor_b=Off",
    ]


def test_demo_audit_reports_balanced_assignment_and_no_duplicate_units() -> None:
    defaults = demo_defaults()
    audit = audit_experiment(
        demo_dataframe(),
        unit=defaults["unit"],
        outcome=defaults["outcome"],
        factors=defaults["factors"],
        covariates=defaults["covariates"],
    )
    assert audit.summary["treatment_cells"] == 4
    assert audit.summary["minimum_cell_n"] == 120
    assert audit.summary["maximum_cell_n"] == 120
    assert audit.summary["duplicate_unit_rows"] == 0
    assert audit.summary["outcome_observation_gap"] < 0.10


def test_audit_detects_duplicate_units_and_differential_outcome_observation() -> None:
    frame = pd.DataFrame(
        {
            "unit": [1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
            "arm": ["A"] * 10 + ["B"] * 10,
            "outcome": [np.nan] * 4 + list(range(6)) + list(range(10)),
        }
    )
    audit = audit_experiment(frame, unit="unit", outcome="outcome", factors=["arm"])
    assert audit.summary["duplicate_unit_rows"] == 2
    assert audit.summary["outcome_observation_gap"] == 0.4
    assert len(audit.warnings) >= 2


def test_audit_rejects_an_outcome_with_no_numeric_values() -> None:
    frame = pd.DataFrame({"arm": ["A", "B"], "outcome": ["low", "high"]})
    with pytest.raises(DataProblem, match="must be numeric"):
        audit_experiment(frame, unit=None, outcome="outcome", factors=["arm"])


def _demo_audit():
    defaults = demo_defaults()
    return audit_experiment(
        demo_dataframe(),
        unit=defaults["unit"],
        outcome=defaults["outcome"],
        factors=defaults["factors"],
        covariates=defaults["covariates"],
    )


def test_decision_rule_uses_design_and_interval_not_p_value() -> None:
    audit = _demo_audit()
    meaningful = classify_decision(
        estimate=1.0,
        ci_low=0.7,
        ci_high=1.3,
        minimum_effect=0.4,
        randomized_confirmed=True,
        audit=audit,
    )
    association = classify_decision(
        estimate=1.0,
        ci_low=0.7,
        ci_high=1.3,
        minimum_effect=0.4,
        randomized_confirmed=False,
        audit=audit,
    )
    small = classify_decision(
        estimate=0.05,
        ci_low=-0.2,
        ci_high=0.25,
        minimum_effect=0.4,
        randomized_confirmed=True,
        audit=audit,
    )
    assert meaningful["status"] == "MEANINGFUL LIFT"
    assert association["status"] == "ASSOCIATION ONLY"
    assert small["status"] == "BOUNDED SMALL"


def test_decision_rule_flags_potential_harm_when_interval_is_below_negative_threshold() -> None:
    harm = classify_decision(
        estimate=-1.0,
        ci_low=-1.3,
        ci_high=-0.7,
        minimum_effect=0.4,
        randomized_confirmed=True,
        audit=_demo_audit(),
    )
    assert harm["status"] == "POTENTIAL HARM"


def test_decision_rule_stays_uncertain_when_interval_crosses_a_practical_boundary() -> None:
    uncertain = classify_decision(
        estimate=0.5,
        ci_low=0.1,
        ci_high=0.9,
        minimum_effect=0.4,
        randomized_confirmed=True,
        audit=_demo_audit(),
    )
    assert uncertain["status"] == "UNCERTAIN"


def test_zero_minimum_effect_degenerates_to_directional_only_not_meaningful_lift() -> None:
    # With threshold 0, "interval excludes zero" is just p < alpha in disguise.
    directional = classify_decision(
        estimate=1.0,
        ci_low=0.7,
        ci_high=1.3,
        minimum_effect=0.0,
        randomized_confirmed=True,
        audit=_demo_audit(),
    )
    assert directional["status"] == "DIRECTIONAL ONLY"
    assert "significance" in directional["meaning"]


def test_demo_contract_declares_a_positive_minimum_worthwhile_effect() -> None:
    assert float(demo_defaults()["minimum_effect"]) > 0
