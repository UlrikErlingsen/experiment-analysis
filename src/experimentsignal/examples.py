"""Deterministic, wholly fictional example data for ExperimentSignal."""

from __future__ import annotations

import numpy as np
import pandas as pd


SEED = 260716


def demo_dataframe(n_per_cell: int = 120) -> pd.DataFrame:
    """Create a balanced fictional 2×2 randomized experiment with a known interaction."""
    rng = np.random.default_rng(SEED)
    cells = [(frame, proof) for frame in ("Clarity", "Momentum") for proof in ("Absent", "Verified")]
    assignments = np.repeat(np.asarray(cells, dtype=object), n_per_cell, axis=0)
    assignments = assignments[rng.permutation(len(assignments))]
    n = len(assignments)
    baseline = np.clip(rng.normal(4.8, 1.35, n), 0, 10)
    frame_signal = (assignments[:, 0] == "Momentum").astype(float)
    proof_signal = (assignments[:, 1] == "Verified").astype(float)
    outcome = (
        4.25
        + 0.43 * (baseline - baseline.mean())
        + 0.28 * frame_signal
        + 0.38 * proof_signal
        + 0.86 * frame_signal * proof_signal
        + rng.normal(0, 1.12, n)
    )
    outcome = np.clip(outcome, 0, 10)
    guardrail = np.clip(2.7 - 0.14 * frame_signal - 0.12 * proof_signal + rng.normal(0, 0.8, n), 0, 10)
    frame = pd.DataFrame(
        {
            "unit_id": [f"PX-{index:04d}" for index in range(1, n + 1)],
            "message_frame": assignments[:, 0],
            "proof_badge": assignments[:, 1],
            "baseline_familiarity_0_10": np.round(baseline, 2),
            "activation_score_0_10": np.round(outcome, 2),
            "friction_guardrail_0_10": np.round(guardrail, 2),
            "assignment_batch": rng.choice(["Batch A", "Batch B", "Batch C"], n),
        }
    )
    frame.loc[rng.random(n) < 0.025, "activation_score_0_10"] = np.nan
    return frame


BINARY_TRUE_CONTROL_RATE = 0.30
BINARY_TRUE_TREATMENT_RATE = 0.36


def binary_demo_dataframe(n_per_arm: int = 400) -> pd.DataFrame:
    """Create a seeded fictional two-arm message test with a binary recall outcome.

    True success probabilities are 0.30 (control) and 0.36 (treatment), a 6-percentage-point lift.
    """
    rng = np.random.default_rng(SEED)
    arms = np.array(["Standard message"] * n_per_arm + ["Benefit-led message"] * n_per_arm, dtype=object)
    arms = arms[rng.permutation(len(arms))]
    rates = np.where(arms == "Benefit-led message", BINARY_TRUE_TREATMENT_RATE, BINARY_TRUE_CONTROL_RATE)
    recalled = np.where(rng.random(len(arms)) < rates, "recalled", "not_recalled")
    return pd.DataFrame(
        {
            "unit_id": [f"MSG-{index:04d}" for index in range(1, len(arms) + 1)],
            "message_variant": arms,
            "recalled_key_claim": recalled,
            "exposure_channel": rng.choice(["Email", "In-app"], len(arms)),
        }
    )


def binary_demo_defaults() -> dict[str, object]:
    """Return the explicit analysis plan attached to the fictional binary message test."""
    return {
        "unit": "unit_id",
        "outcome": "recalled_key_claim",
        "factors": ["message_variant"],
        "covariates": [],
        "control_arm": "message_variant=Standard message",
        "treatment_arm": "message_variant=Benefit-led message",
        "minimum_effect": 0.02,
        "outcome_type": "binary",
        "success_value": "recalled",
        "randomized_confirmed": True,
        "outcome_prespecified": True,
        "treatment_precedes_outcome": True,
        "stopping_prespecified": True,
        "question": "Does the benefit-led message lift key-claim recall enough to justify switching?",
        "population": "Eligible recipients in the fictional campaign window",
        "assignment_method": "Equal-probability individual random assignment to two message variants",
        "analysis_population": "All assigned units with an observed recall outcome",
        "stopping_rule": "Fixed sample: 400 assignments per arm",
        "guardrail": "Unsubscribe rate should not increase materially",
    }


def contract_templates() -> dict[str, dict[str, object]]:
    """Contract-field prefills only. Templates never fabricate data, columns, or thresholds."""
    return {
        "Communication test": {
            "outcome_type": "binary",
            "question": "Does the new message lift recall of the key claim enough to justify switching?",
            "population": "Eligible recipients in the declared campaign window",
            "assignment_method": "Equal-probability individual random assignment to message variants",
            "analysis_population": "All assigned units with an observed recall outcome",
            "stopping_rule": "Fixed sample declared before launch",
            "guardrail": "Opt-outs or complaints should not increase materially",
            "note": "Declare which recorded value means the claim was recalled or recognized.",
        },
        "Price test": {
            "outcome_type": "binary",
            "question": "Does the tested price change purchase conversion enough to justify adopting it?",
            "population": "Eligible visitors or accounts in the declared selling window",
            "assignment_method": "Equal-probability individual random assignment to price conditions",
            "analysis_population": "All assigned units with an observed purchase outcome",
            "stopping_rule": "Fixed sample declared before launch",
            "guardrail": "Revenue per visitor and refund rate should be checked separately",
            "note": (
                "This tests one purchase outcome at declared price points. Deeper pricing questions—"
                "price ladders, willingness to pay, elasticity—belong to TagSignal, the pricing sibling."
            ),
        },
        "Feature rollout": {
            "outcome_type": "continuous",
            "question": "Does the new feature improve the primary usage or satisfaction score enough to roll out?",
            "population": "Eligible active users in the declared rollout window",
            "assignment_method": "Equal-probability individual random assignment to feature on/off",
            "analysis_population": "All assigned units with an observed primary outcome",
            "stopping_rule": "Fixed sample declared before launch",
            "guardrail": "Support contacts or task time should not worsen materially",
            "note": "Use a numeric outcome measured the same way in every arm.",
        },
    }


def starter_template() -> pd.DataFrame:
    """Return a small data-role template; values are placeholders, not an analyzable study."""
    return pd.DataFrame(
        {
            "unit_id": ["U001", "U002", "U003", "U004"],
            "treatment": ["Control", "Treatment", "Control", "Treatment"],
            "primary_outcome": [4.2, 5.1, 4.7, 5.4],
            "baseline_measure": [3.9, 4.1, 4.5, 4.8],
        }
    )


def demo_defaults() -> dict[str, object]:
    """Return the explicit analysis plan attached to the fictional demonstration."""
    return {
        "unit": "unit_id",
        "outcome": "activation_score_0_10",
        "factors": ["message_frame", "proof_badge"],
        "covariates": ["baseline_familiarity_0_10"],
        "control_arm": "message_frame=Clarity · proof_badge=Absent",
        "treatment_arm": "message_frame=Momentum · proof_badge=Verified",
        "minimum_effect": 0.40,
        "randomized_confirmed": True,
        "outcome_prespecified": True,
        "treatment_precedes_outcome": True,
        "stopping_prespecified": True,
        "question": "Does the combined message-and-proof treatment improve activation enough to justify rollout?",
        "population": "Eligible visitors in the fictional launch window",
        "assignment_method": "Equal-probability individual random assignment to four cells",
        "analysis_population": "All assigned units with an observed primary outcome and baseline measure",
        "stopping_rule": "Fixed sample: 120 assignments per cell",
        "guardrail": "Friction score should not increase materially",
    }
