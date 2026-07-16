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
