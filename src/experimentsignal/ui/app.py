"""Experiment Signal Streamlit UI.

Everything that draws the app runs inside ``render()`` (or the functions it calls), so it runs on every rerun,
both in the standalone ``app.py`` and inside Signal Hub. Module-level code here only defines constants and
functions. ``render()`` never calls ``st.set_page_config`` or ``st.navigation``.
"""

from __future__ import annotations

import hashlib
import inspect
import os
import traceback

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from experimentsignal import __version__
from experimentsignal.analysis import (
    AnalysisConfig,
    analyze_experiment,
    plan_two_arm_binary_sample,
    plan_two_arm_sample,
)
from experimentsignal.design import arm_labels, audit_experiment, classify_decision, ordered_levels
from experimentsignal.errors import DataProblem, friendly_message
from experimentsignal.examples import (
    binary_demo_dataframe,
    binary_demo_defaults,
    contract_templates,
    demo_dataframe,
    demo_defaults,
    starter_template,
)
from experimentsignal.io import (
    build_evidence_pack,
    dataframe_to_xlsx,
    evidence_to_csv_zip,
    evidence_to_excel,
    evidence_to_json,
    read_table,
)
from experimentsignal.ui import signal_theme as sig


NS = "experiment"


def k(name: str) -> str:
    """Namespace a session-state or widget key with the app slug, so apps can share one Hub session."""
    return f"{NS}:{name}"


SIDEBAR_TAGLINE = "Causal experiment evidence without the significance theatre."
MASTHEAD_KICKER = "DESIGN → ESTIMATE → DECIDE"
MASTHEAD_PROMISES = ["Practical effects", "Robust uncertainty", "Local evidence"]
FOOTER_LINE = "randomized contrasts do not manufacture randomization"
CAUTION = (
    "**Experiment Signal estimates contrasts; it does not manufacture randomization.** A causal reading also requires "
    "a valid assignment process, one observation per randomized unit, treatment before outcome, acceptable missingness, "
    "limited interference, and faithful implementation. P-values are never the decision rule."
)


def full_width(widget, *args, **kwargs):
    """Use Streamlit's current width API while retaining older compatibility."""
    try:
        parameters = inspect.signature(widget).parameters
    except (TypeError, ValueError):
        parameters = {}
    width_parameter = parameters.get("width")
    if width_parameter is not None and isinstance(width_parameter.default, str):
        kwargs["width"] = "stretch"
    elif "use_container_width" in parameters:
        kwargs["use_container_width"] = True
    return widget(*args, **kwargs)


def show_error(exc: Exception) -> None:
    st.error(friendly_message(exc))
    if not isinstance(exc, (DataProblem, ValueError)) and os.getenv("EXPERIMENTSIGNAL_DEBUG") == "1":
        with st.expander("Technical details"):
            st.code("".join(traceback.format_exception(exc)))


def _ensure_state() -> None:
    # On first run the fictional 2×2 factorial demo is preloaded, so the app opens on a working example.
    # The sidebar demo buttons restore or switch demos, and an upload replaces the demo.
    st.session_state.setdefault(k("upload_fingerprint"), None)
    st.session_state.setdefault(k("contract_rev"), 0)
    if k("data") not in st.session_state:
        load_demo()


def _contract_rev() -> int:
    return int(st.session_state.get(k("contract_rev"), 0))


def _replace_contract(contract: dict[str, object] | None) -> None:
    """Replace the saved contract from outside the contract form (demo, upload, template).

    The contract-form widget keys carry a revision number, so bumping it re-seeds every field from the new
    contract instead of keeping stale widget values.
    """
    if contract is None:
        st.session_state.pop(k("contract"), None)
    else:
        st.session_state[k("contract")] = contract
    st.session_state[k("contract_rev")] = _contract_rev() + 1


def reset_results() -> None:
    for name in ("audit", "analysis", "decision"):
        st.session_state.pop(k(name), None)


def load_demo() -> None:
    demo = demo_dataframe()
    st.session_state[k("data")] = demo
    st.session_state[k("source")] = {
        "source_filename": "experimentsignal-fictional-factorial-demo.csv",
        "source_sheet": "",
        "source_sha256": hashlib.sha256(demo.to_csv(index=False).encode("utf-8")).hexdigest(),
        "source_type": "deterministic synthetic demonstration",
    }
    _replace_contract(demo_defaults())
    reset_results()


def load_binary_demo() -> None:
    demo = binary_demo_dataframe()
    st.session_state[k("data")] = demo
    st.session_state[k("source")] = {
        "source_filename": "experimentsignal-fictional-binary-message-demo.csv",
        "source_sheet": "",
        "source_sha256": hashlib.sha256(demo.to_csv(index=False).encode("utf-8")).hexdigest(),
        "source_type": "deterministic synthetic demonstration",
    }
    _replace_contract(binary_demo_defaults())
    reset_results()


def _demo_active() -> bool:
    source = st.session_state.get(k("source"), {})
    return source.get("source_type") == "deterministic synthetic demonstration"


def select_index(options: list[str], value: object, fallback: int = 0) -> int:
    return options.index(value) if value in options else min(fallback, len(options) - 1)


def render_welcome() -> None:
    sig.hero(
        NS,
        eyebrow="EXPERIMENT DECISION SUPPORT",
        title="Did the treatment cause a change",
        em="worth acting on?",
        body=(
            "Turn a randomized between-subject experiment into an auditable decision record: declare the contrast, "
            "inspect assignment and observation, estimate effects with robust uncertainty, and compare the interval "
            "with a business threshold written before the result."
        ),
        pills=[
            "continuous & binary outcomes",
            "1–3 treatment factors",
            "HC3 intervals",
            "Holm multiplicity",
            "factorial decomposition",
            "a priori power",
            "privacy-minimized exports",
        ],
    )
    st.warning(CAUTION)
    sig.cards(
        [
            (
                "01 · CONTRACT",
                "Write the claim first",
                "Name the unit, population, outcome, treatment cells, primary contrast, minimum worthwhile effect, "
                "exclusions, and stopping rule.",
            ),
            (
                "02 · AUDIT",
                "Interrogate the design",
                "Check unique units, assigned-cell counts, outcome observation rates, baseline standardized "
                "differences, and complete-case retention.",
            ),
            (
                "03 · DECIDE",
                "Read magnitude with uncertainty",
                "Use the declared contrast and confidence interval for the decision. Treat omnibus tests and pairwise "
                "p-values as supporting diagnostics.",
            ),
        ]
    )
    st.markdown("### A deliberately bounded release")
    st.write(
        "Experiment Signal analyzes continuous and binary outcomes from individually randomized, between-subject designs. "
        "It supports one-way and factorial cells, optional numeric pre-treatment adjustment, robust cell contrasts, "
        "and two-arm power planning. It does not currently claim support for clustered assignment, crossover "
        "or repeated-measures designs, count/survival outcomes, adaptive stopping, noncompliance estimands, "
        "or observational causal identification."
    )
    if _demo_active():
        st.info(
            "A fictional demo is loaded, with its design contract saved: the 2×2 factorial demo opens by default, "
            "and the sidebar switches to the binary message demo. Open the steps in the sidebar to audit it and run "
            "the declared analysis. The data are deterministic synthetic records for a fictional service. Upload a "
            "CSV/XLSX/JSON table to replace the demo."
        )


def render_contract() -> None:
    sig.header(
        "Step 1",
        "Design contract",
        "Declare the analysis roles and decision boundary. The app will not infer them from whichever result looks best.",
    )
    if k("data") not in st.session_state:
        st.info("Load or upload experiment data first.")
        return
    data: pd.DataFrame = st.session_state[k("data")]

    templates = contract_templates()
    with st.expander("Start from a template · optional"):
        template_name = st.selectbox(
            "Template",
            list(templates),
            key=k("contract_template"),
            help="Prefills the claim wording and outcome type. It never invents data, columns, or thresholds.",
        )
        selected_template = dict(templates[template_name])
        st.caption(str(selected_template.pop("note", "")))
        if st.button("Apply template", key=k("apply_template")):
            merged = dict(st.session_state.get(k("contract"), {}))
            merged.update(selected_template)
            _replace_contract(merged)
            reset_results()
            st.success(f"Applied the “{template_name}” template. Review every field before saving.")

    current = dict(st.session_state.get(k("contract"), {}))
    rev = _contract_rev()
    st.markdown("#### Data roles")
    outcome_type = st.selectbox(
        "Primary outcome type",
        ["continuous", "binary"],
        index=0 if current.get("outcome_type", "continuous") == "continuous" else 1,
        key=k(f"c{rev}:outcome_type"),
        help="Binary outcomes can be encoded with any two labels; you will declare which label means success.",
    )
    numeric_columns = [column for column in data.columns if pd.to_numeric(data[column], errors="coerce").notna().sum() >= 2]
    binary_columns = [column for column in data.columns if data[column].dropna().astype(str).nunique() == 2]
    outcome_candidates = numeric_columns if outcome_type == "continuous" else binary_columns
    factor_candidates = [
        column for column in data.columns if 2 <= data[column].dropna().astype(str).nunique() <= 8
    ]
    unit_options = ["(use row number)", *map(str, data.columns)]
    unit_value = current.get("unit") or "(use row number)"
    col1, col2 = st.columns(2)
    with col1:
        unit = st.selectbox(
            "Randomized unit identifier",
            unit_options,
            index=select_index(unit_options, unit_value),
            key=k(f"c{rev}:unit"),
            help="Used to detect repeated rows for the same randomized unit.",
        )
        if not outcome_candidates:
            st.error(f"No {outcome_type} outcome candidate was detected.")
            return
        outcome = st.selectbox(
            "Primary outcome",
            outcome_candidates,
            index=select_index(outcome_candidates, current.get("outcome")),
            key=k(f"c{rev}:outcome:{outcome_type}"),
        )
        success_value = None
        if outcome_type == "binary":
            success_levels = ordered_levels(data[outcome].dropna().astype(str))
            success_value = st.selectbox(
                "Value that means success",
                success_levels,
                index=select_index(success_levels, current.get("success_value"), fallback=len(success_levels) - 1),
                key=k(f"c{rev}:success_value:{outcome}"),
                help="The other observed value is encoded as 0; this value is encoded as 1.",
            )
    with col2:
        factors_default = [item for item in current.get("factors", []) if item in factor_candidates]
        factors = st.multiselect(
            "Treatment factor(s) · choose 1–3",
            factor_candidates,
            default=factors_default,
            max_selections=3,
            key=k(f"c{rev}:factors"),
            help="Columns that encode randomized treatment levels—not segments discovered after the result.",
        )
        covariate_options = [column for column in numeric_columns if column != outcome and column not in factors]
        covariates = st.multiselect(
            "Pre-treatment numeric covariates · optional",
            covariate_options,
            default=[item for item in current.get("covariates", []) if item in covariate_options],
            key=k(f"c{rev}:covariates"),
            help="Only measures determined before treatment. Post-treatment adjustment can bias the estimand.",
        )

    if not factors:
        st.info("Choose at least one treatment factor to define the primary contrast.")
        return
    try:
        labels = ordered_levels(arm_labels(data.dropna(subset=factors), factors))
    except Exception as exc:
        show_error(exc)
        return
    if len(labels) < 2:
        st.error("The selected treatment factors create fewer than two complete cells.")
        return
    cells = "|".join(factors)
    col1, col2, col3 = st.columns([1, 1, 0.7])
    with col1:
        control = st.selectbox(
            "Primary control cell",
            labels,
            index=select_index(labels, current.get("control_arm")),
            key=k(f"c{rev}:control:{cells}"),
        )
    treatment_options = [label for label in labels if label != control]
    with col2:
        treatment = st.selectbox(
            "Primary treatment cell",
            treatment_options,
            index=select_index(treatment_options, current.get("treatment_arm")),
            key=k(f"c{rev}:treatment:{cells}:{control}"),
        )
    with col3:
        if outcome_type == "binary":
            minimum_effect_pp = st.number_input(
                "Minimum worthwhile lift · percentage points",
                min_value=0.0,
                max_value=100.0,
                value=min(100 * float(current.get("minimum_effect", 0.0)), 100.0),
                step=0.5,
                key=k(f"c{rev}:minimum_effect_pp"),
                help="Enter 3 for a 3-percentage-point lift. Set it before reading the estimate.",
            )
            minimum_effect = minimum_effect_pp / 100
        else:
            minimum_effect = st.number_input(
                "Minimum worthwhile effect",
                min_value=0.0,
                value=float(current.get("minimum_effect", 0.0)),
                step=0.10,
                key=k(f"c{rev}:minimum_effect"),
                help="In outcome units. Set from economics, customer value, or policy—not from the observed estimate.",
            )

    st.markdown("#### Claim and protocol")
    question = st.text_input("Decision question", value=str(current.get("question", "")), key=k(f"c{rev}:question"))
    population = st.text_input(
        "Target population", value=str(current.get("population", "")), key=k(f"c{rev}:population")
    )
    col1, col2 = st.columns(2)
    with col1:
        assignment_method = st.text_area(
            "Assignment mechanism",
            value=str(current.get("assignment_method", "")),
            height=92,
            key=k(f"c{rev}:assignment_method"),
        )
        analysis_population = st.text_area(
            "Analysis population and exclusions",
            value=str(current.get("analysis_population", "")),
            height=92,
            key=k(f"c{rev}:analysis_population"),
        )
    with col2:
        stopping_rule = st.text_area(
            "Sample-size / stopping rule",
            value=str(current.get("stopping_rule", "")),
            height=92,
            key=k(f"c{rev}:stopping_rule"),
        )
        guardrail = st.text_area(
            "Guardrail outcome or harm check",
            value=str(current.get("guardrail", "")),
            height=92,
            key=k(f"c{rev}:guardrail"),
        )

    st.markdown("#### Design confirmations")
    col1, col2 = st.columns(2)
    with col1:
        randomized_confirmed = st.checkbox(
            "Treatment was assigned by a known random mechanism",
            value=bool(current.get("randomized_confirmed", False)),
            key=k(f"c{rev}:randomized_confirmed"),
        )
        outcome_prespecified = st.checkbox(
            "Primary outcome and contrast were set before reading results",
            value=bool(current.get("outcome_prespecified", False)),
            key=k(f"c{rev}:outcome_prespecified"),
        )
    with col2:
        treatment_precedes_outcome = st.checkbox(
            "Treatment assignment preceded outcome measurement",
            value=bool(current.get("treatment_precedes_outcome", False)),
            key=k(f"c{rev}:treatment_precedes_outcome"),
        )
        stopping_prespecified = st.checkbox(
            "The stopping rule did not depend on interim outcome significance",
            value=bool(current.get("stopping_prespecified", False)),
            key=k(f"c{rev}:stopping_prespecified"),
        )
    if st.button("Save design contract", type="primary", key=k("save_contract")):
        if float(minimum_effect) <= 0:
            st.error(
                "Set the minimum worthwhile effect above zero. With a zero threshold the reading collapses "
                "into a bare significance statement, which Experiment Signal refuses to present as a decision."
            )
            return
        # Saved from the form itself, so the widgets already hold these values: no revision bump.
        st.session_state[k("contract")] = {
            "unit": None if unit == "(use row number)" else unit,
            "outcome": outcome,
            "factors": list(factors),
            "covariates": list(covariates),
            "control_arm": control,
            "treatment_arm": treatment,
            "minimum_effect": float(minimum_effect),
            "outcome_type": outcome_type,
            "success_value": success_value,
            "randomized_confirmed": randomized_confirmed,
            "outcome_prespecified": outcome_prespecified,
            "treatment_precedes_outcome": treatment_precedes_outcome,
            "stopping_prespecified": stopping_prespecified,
            "question": question,
            "population": population,
            "assignment_method": assignment_method,
            "analysis_population": analysis_population,
            "stopping_rule": stopping_rule,
            "guardrail": guardrail,
        }
        reset_results()
        st.success("Design contract saved. Continue to the randomization audit.")


def render_audit() -> None:
    sig.header(
        "Step 2",
        "Data & randomization audit",
        "Diagnostics can reveal trouble. They cannot prove that assignment was random or that interference is absent.",
    )
    if k("data") not in st.session_state or k("contract") not in st.session_state:
        st.info("Load data and save the design contract first.")
        return
    data: pd.DataFrame = st.session_state[k("data")]
    contract: dict[str, object] = st.session_state[k("contract")]
    required = ("outcome", "factors", "control_arm", "treatment_arm")
    if any(not contract.get(key) for key in required):
        st.info("Complete the data roles and primary contrast on the design-contract page.")
        return
    try:
        audit = audit_experiment(
            data,
            unit=contract.get("unit"),
            outcome=str(contract["outcome"]),
            factors=list(contract["factors"]),
            covariates=list(contract.get("covariates", [])),
            outcome_type=str(contract.get("outcome_type", "continuous")),
            success_value=contract.get("success_value"),
        )
    except Exception as exc:
        show_error(exc)
        return
    summary = audit.summary
    columns = st.columns(4)
    columns[0].metric("Assigned rows", f"{int(summary['assigned_rows']):,}")
    columns[1].metric("Treatment cells", f"{int(summary['treatment_cells'])}")
    columns[2].metric("Smallest cell", f"{int(summary['minimum_cell_n']):,}")
    columns[3].metric("Outcome-rate gap", f"{100 * float(summary['outcome_observation_gap']):.1f} pp")
    if audit.warnings:
        for warning in audit.warnings:
            st.warning(warning)
    else:
        st.success("No automatic severe audit flag was triggered. This is not proof of design validity.")

    tab1, tab2, tab3 = st.tabs(["Cell counts", "Outcome observation", "Baseline balance"])
    with tab1:
        full_width(st.dataframe, audit.arm_counts, hide_index=True)
    with tab2:
        display = audit.outcome_observation.copy()
        display["observation_rate"] = (100 * display["observation_rate"]).round(1).astype(str) + "%"
        full_width(st.dataframe, display, hide_index=True)
        st.caption("Observation-rate differences may reflect attrition or measurement failure after assignment.")
    with tab3:
        if audit.covariate_balance.empty:
            st.info("No pre-treatment covariates were declared.")
        else:
            full_width(st.dataframe, audit.covariate_balance.round(3), hide_index=True)
            st.caption("SMD is a magnitude diagnostic, not a randomization p-test and not an automatic rerandomization rule.")

    st.markdown("#### Estimation settings")
    col1, col2 = st.columns(2)
    with col1:
        confidence = st.select_slider(
            "Confidence level", options=[0.90, 0.95, 0.99], value=0.95, key=k("confidence")
        )
    with col2:
        permutations = st.select_slider(
            "Randomization permutations",
            options=[0, 999, 4999, 9999],
            value=4999,
            key=k("permutations"),
            help="Available only for unadjusted two-arm, one-factor data in this release.",
        )
    st.caption("HC3 intervals are primary. A sharp-null permutation p-value is a design-based sensitivity check where supported.")
    if st.button("Run declared analysis", type="primary", key=k("run_analysis")):
        try:
            config = AnalysisConfig(
                outcome=str(contract["outcome"]),
                factors=tuple(contract["factors"]),
                covariates=tuple(contract.get("covariates", [])),
                control_arm=str(contract["control_arm"]),
                treatment_arm=str(contract["treatment_arm"]),
                alpha=1 - float(confidence),
                minimum_effect=float(contract.get("minimum_effect", 0.0)),
                permutations=int(permutations),
                outcome_type=str(contract.get("outcome_type", "continuous")),
                success_value=(
                    str(contract.get("success_value"))
                    if contract.get("outcome_type", "continuous") == "binary"
                    else None
                ),
            )
            analysis = analyze_experiment(data, config)
            decision = classify_decision(
                estimate=float(analysis.primary["estimate"]),
                ci_low=float(analysis.primary["ci_low"]),
                ci_high=float(analysis.primary["ci_high"]),
                minimum_effect=float(contract.get("minimum_effect", 0.0)),
                randomized_confirmed=bool(contract.get("randomized_confirmed", False)),
                audit=audit,
            )
            st.session_state[k("audit")] = audit
            st.session_state[k("analysis")] = analysis
            st.session_state[k("decision")] = decision
            st.success("Analysis complete. Continue to effects and uncertainty.")
        except Exception as exc:
            show_error(exc)


def contrast_figure(frame: pd.DataFrame, minimum_effect: float) -> go.Figure:
    roles = sig.roles(NS)
    ordered = frame.sort_values("estimate").copy()
    figure = go.Figure()
    # The not-worth-acting band: ± the declared minimum worthwhile effect (the practical threshold).
    figure.add_vrect(x0=-minimum_effect, x1=minimum_effect, fillcolor=roles["threshold"], opacity=0.17, line_width=0)
    figure.add_vline(x=0, line_color=roles["zero"], line_dash="dot")
    figure.add_trace(
        go.Scatter(
            x=ordered["estimate"],
            y=ordered["contrast"],
            mode="markers",
            marker={"color": roles["estimate"], "size": 10},
            error_x={
                "type": "data",
                "symmetric": False,
                "array": ordered["ci_high"] - ordered["estimate"],
                "arrayminus": ordered["estimate"] - ordered["ci_low"],
                "color": roles["interval"],
                "thickness": 2,
            },
            hovertemplate="%{y}<br>Effect %{x:.3f}<extra></extra>",
        )
    )
    figure.update_layout(
        template=sig.template(NS),
        height=max(360, 58 * len(ordered)),
        margin={"l": 20, "r": 25, "t": 25, "b": 55},
        xaxis_title="Adjusted outcome difference with confidence interval",
        yaxis_title="",
        showlegend=False,
    )
    return figure


def render_effects() -> None:
    sig.header(
        "Step 3",
        "Effects & uncertainty",
        "The declared treatment-minus-control contrast is primary. Every other comparison is a labeled family.",
    )
    if k("analysis") not in st.session_state:
        st.info("Run the declared analysis on the audit page first.")
        return
    analysis = st.session_state[k("analysis")]
    contract = st.session_state[k("contract")]
    primary = analysis.primary
    binary = analysis.config.outcome_type == "binary"
    adjusted = bool(analysis.config.covariates)
    effect_label = ("Adjusted lift" if adjusted else "Estimated lift") if binary else "Adjusted effect"
    effect_value = f"{100 * float(primary['estimate']):.2f} pp" if binary else f"{float(primary['estimate']):.3f}"
    interval_value = (
        f"[{100 * float(primary['ci_low']):.2f}, {100 * float(primary['ci_high']):.2f}] pp"
        if binary
        else f"[{float(primary['ci_low']):.3f}, {float(primary['ci_high']):.3f}]"
    )
    threshold_value = (
        f"{100 * float(contract.get('minimum_effect', 0)):.2f} pp"
        if binary
        else f"{float(contract.get('minimum_effect', 0)):.3f}"
    )
    columns = st.columns(4)
    columns[0].metric(effect_label, effect_value)
    columns[1].metric("Interval", interval_value)
    columns[2].metric("Minimum worthwhile", threshold_value)
    if binary:
        rr = float(primary["risk_ratio_descriptive"])
        columns[3].metric("Risk ratio · raw", f"{rr:.2f}" if pd.notna(rr) else "not estimable")
    else:
        columns[3].metric("Hedges' g", f"{float(primary['hedges_g_descriptive']):.2f}")
    estimand = (
        ("adjusted success probability (risk)" if adjusted else "success probability (risk)")
        if binary
        else "mean outcome"
    )
    adjustment_text = (
        "standardized to the sample-average declared baseline covariates"
        if adjusted
        else "with no covariate adjustment declared"
    )
    estimate_text = effect_value if binary else f"{float(primary['estimate']):.3f} outcome units"
    interval_method = str(primary.get("interval_method", "HC3 t"))
    # sig.note HTML-escapes the whole text, including the user-supplied treatment-arm labels.
    sig.note(
        "info",
        f"**Primary estimand:** {estimand} under `{primary['treatment_arm']}` minus {estimand} under "
        f"`{primary['control_arm']}`, {adjustment_text}. The estimate is **{estimate_text}** with a "
        f"{interval_method} interval.",
    )
    for warning in analysis.warnings:
        st.warning(warning)
    st.markdown("#### Adjusted cell means")
    display_groups = analysis.group_summary.copy()
    full_width(st.dataframe, display_groups.round(3), hide_index=True)
    st.markdown("#### Pairwise contrast family")
    sig.chart(NS, contrast_figure(analysis.contrasts, float(contract.get("minimum_effect", 0))), key=k("contrast_chart"))
    st.caption(
        f"Shaded band: ± the declared minimum worthwhile effect. Intervals are {interval_method}; "
        "no multiplicity adjustment is applied to interval width."
    )

    with st.expander("Exploratory tests, factorial decomposition, and model diagnostics"):
        contrast_columns = [
            "contrast",
            "estimate",
            "ci_low",
            "ci_high",
            "p_value_exploratory",
            "p_value_holm",
            "hedges_g_descriptive",
            "risk_ratio_descriptive",
            "odds_ratio_descriptive",
        ]
        full_width(st.dataframe, analysis.contrasts[contrast_columns].round(4), hide_index=True)
        st.caption("Holm adjustment controls familywise error across the displayed pairwise p-value family. It is not the decision threshold.")
        if not analysis.term_tests.empty:
            st.markdown("**Factorial term tests**")
            full_width(st.dataframe, analysis.term_tests.round(4), hide_index=True)
            st.caption("Robust Type-II model decomposition; partial eta-squared is descriptive. The declared cell contrast stays primary.")
        diagnostics = pd.DataFrame(
            [{"diagnostic": key, "value": str(value)} for key, value in analysis.diagnostics.items()]
        )
        st.markdown("**Model diagnostics**")
        full_width(st.dataframe, diagnostics, hide_index=True)
        if analysis.permutation:
            st.markdown("**Randomization inference**")
            st.json(analysis.permutation)
            st.caption("This test targets Fisher's sharp null, which differs from a zero average treatment effect.")
        else:
            st.info("Sharp-null permutation testing is withheld because this is not an unadjusted two-arm one-factor analysis.")


def render_decision() -> None:
    sig.header(
        "Step 4",
        "Decision & export",
        "A compact handoff that preserves the design claim, uncertainty, audit, and exact analysis settings.",
    )
    if k("analysis") not in st.session_state or k("decision") not in st.session_state:
        st.info("Run the declared analysis first.")
        return
    decision = st.session_state[k("decision")]
    analysis = st.session_state[k("analysis")]
    audit = st.session_state[k("audit")]
    contract = st.session_state[k("contract")]
    sig.cards(
        [
            (
                "DECLARED-CONTRAST READING",
                str(decision["status"]),
                f"{decision['meaning']} Next move: {decision['action']}",
            )
        ]
    )
    st.warning(CAUTION)
    confirmations = pd.DataFrame(
        [
            {"design condition": "Known random assignment", "confirmed": bool(contract.get("randomized_confirmed"))},
            {"design condition": "Outcome and contrast pre-specified", "confirmed": bool(contract.get("outcome_prespecified"))},
            {"design condition": "Treatment preceded outcome", "confirmed": bool(contract.get("treatment_precedes_outcome"))},
            {"design condition": "Outcome-independent stopping", "confirmed": bool(contract.get("stopping_prespecified"))},
        ]
    )
    full_width(st.dataframe, confirmations, hide_index=True)
    if not confirmations["confirmed"].all():
        st.warning("At least one design confirmation is missing. Keep that limitation in the decision record.")

    pack = build_evidence_pack(
        source=dict(st.session_state.get(k("source"), {})),
        contract=contract,
        audit=audit,
        analysis=analysis,
        decision=decision,
    )
    st.markdown("#### Privacy-minimized evidence pack")
    st.write(
        "Exports contain aggregate cell counts, observation rates, balance diagnostics, adjusted cell means, contrasts, "
        "term tests, the decision rule, source fingerprint, and software settings. Unit-level IDs, outcomes, covariates, "
        "fitted values, and residuals are excluded."
    )
    col1, col2, col3 = st.columns(3)
    col1.download_button(
        "Download Excel evidence pack",
        evidence_to_excel(pack),
        file_name="experimentsignal-evidence-pack.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=k("download_xlsx"),
    )
    col2.download_button(
        "Download CSV ZIP",
        evidence_to_csv_zip(pack),
        file_name="experimentsignal-evidence-pack.zip",
        mime="application/zip",
        key=k("download_zip"),
    )
    col3.download_button(
        "Download JSON record",
        evidence_to_json(pack),
        file_name="experimentsignal-evidence-pack.json",
        mime="application/json",
        key=k("download_json"),
    )


def render_power() -> None:
    sig.header(
        "Planning",
        "Power planner",
        "Prospective planning only: choose the smallest effect worth detecting before collecting or inspecting outcomes.",
    )
    outcome_type = st.selectbox("Planning outcome", ["continuous", "binary"], key=k("power_outcome_type"))
    st.warning(
        "This approximation is for a fixed, two-sided, two-arm individually randomized design. "
        "It does not account for clustering, repeated measures, covariate gain, noncompliance, sequential looks, or multiple outcomes."
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        if outcome_type == "continuous":
            minimum = st.number_input(
                "Minimum worthwhile raw effect", min_value=0.001, value=0.40, step=0.05, key=k("power_minimum")
            )
            sd = st.number_input("Expected outcome SD", min_value=0.001, value=1.50, step=0.10, key=k("power_sd"))
        else:
            control_rate = st.number_input(
                "Expected control success rate · %", min_value=0.1, max_value=99.9, value=12.0, step=0.5,
                key=k("power_control_rate"),
            ) / 100
            minimum_lift = st.number_input(
                "Minimum worthwhile lift · percentage points", min_value=0.1, max_value=99.0, value=2.5, step=0.5,
                key=k("power_minimum_lift"),
                help="Enter 2.5 for a 2.5-percentage-point lift.",
            ) / 100
    with col2:
        alpha = st.select_slider(
            "Two-sided alpha", options=[0.01, 0.025, 0.05, 0.10], value=0.05, key=k("power_alpha")
        )
        power = st.select_slider(
            "Target power", options=[0.70, 0.80, 0.85, 0.90, 0.95], value=0.80, key=k("power_target")
        )
    with col3:
        ratio = st.number_input(
            "Treatment ÷ control allocation", min_value=0.10, max_value=10.0, value=1.0, step=0.10,
            key=k("power_ratio"),
        )
        attrition = st.slider(
            "Expected outcome loss", min_value=0, max_value=60, value=10, step=1, key=k("power_attrition")
        )
    if st.button("Plan sample", type="primary", key=k("plan_sample")):
        try:
            if outcome_type == "continuous":
                plan = plan_two_arm_sample(
                    minimum_effect=float(minimum), outcome_sd=float(sd), alpha=float(alpha), power=float(power),
                    allocation_ratio=float(ratio), expected_attrition=float(attrition) / 100,
                )
                first_label = "Standardized effect"
                first_value = f"{float(plan['standardized_effect']):.3f}"
            else:
                plan = plan_two_arm_binary_sample(
                    control_rate=float(control_rate), minimum_lift=float(minimum_lift), alpha=float(alpha), power=float(power),
                    allocation_ratio=float(ratio), expected_attrition=float(attrition) / 100,
                )
                first_label = "Planned rates"
                first_value = f"{100 * float(plan['control_rate']):.1f}% → {100 * float(plan['treatment_rate']):.1f}%"
            columns = st.columns(4)
            columns[0].metric(first_label, first_value)
            columns[1].metric("Complete total", f"{int(plan['complete_total']):,}")
            columns[2].metric("Assign total", f"{int(plan['assign_total']):,}")
            columns[3].metric("Control / treatment", f"{int(plan['assign_control'])} / {int(plan['assign_treatment'])}")
            st.caption(
                "Round operationally upward and justify the SD and minimum effect with prior data, a pilot, economics, "
                "measurement resolution, or stakeholder consequences—not generic small/medium/large labels."
            )
        except Exception as exc:
            show_error(exc)


def render_methods() -> None:
    sig.header(
        "Methods and limits",
        "What Experiment Signal calculates",
        "Estimands, uncertainty, multiplicity, audit conventions, the decision rule, and what this release does not handle.",
    )
    st.warning(CAUTION)
    st.markdown(
        """
        ### Estimand before test statistic

        The primary output is the declared treatment-cell mean minus the declared control-cell mean for the primary
        continuous mean or binary risk outcome. With baseline covariates, Experiment Signal centers those pre-treatment measures and fits
        cell-specific slopes; the displayed adjusted means are standardized to the sample-average covariate values.
        HC3 covariance supplies the interval. This regression adjustment can improve precision, but cannot repair
        non-random assignment, post-treatment adjustment, measurement failure, interference, or selective attrition.

        For a binary outcome without declared covariates, the primary risk difference gets a Newcombe (1998)
        hybrid Wilson score interval instead of the model interval. With declared covariates, the covariate-adjusted
        risk difference comes from an HC3 linear probability model, and the app flags any adjusted probability
        outside 0–1 because a linear model can extrapolate beyond the outcome's range.

        ### Multiple cells and factorial designs

        All cell pairs are shown as one comparison family and exploratory p-values receive Holm's step-down familywise
        adjustment. Factorial main effects and interactions use a robust Type-II model decomposition. These terms answer
        different questions from a specific cell contrast, especially when an interaction is present. Partial eta-squared
        is descriptive because its sum-of-squares basis is not itself an HC3 effect-size estimator.

        ### Randomization and model-based inference

        For an unadjusted, one-factor, two-arm dataset, the app also permutes treatment labels while preserving observed
        group sizes. Its two-sided p-value targets Fisher's sharp null that no unit changes under treatment. The HC3
        interval instead targets an average contrast under a model-assisted repeated-sampling interpretation. Neither
        quantity is the probability that the hypothesis is true, and neither measures business importance.

        ### Audit conventions

        The audit reports assigned-cell counts, unique-ID problems, outcome observation rates by assigned cell, and
        pairwise standardized mean differences for declared baseline measures. SMDs are magnitude diagnostics—not tests
        that randomization succeeded. A large imbalance can occur by chance; a small imbalance cannot verify the assignment
        system. The app uses complete cases for the outcome, treatment factors, and declared covariates and reports retention.

        ### Decision rule

        `MEANINGFUL LIFT` requires the full confidence interval to exceed the positive minimum worthwhile effect.
        `POTENTIAL HARM` requires it to lie below the negative boundary. `BOUNDED SMALL` requires the interval to fit
        entirely inside the symmetric not-worth-acting band. Otherwise the result is `UNCERTAIN`. Missing randomization
        confirmation changes the reading to `ASSOCIATION ONLY`; severe uniqueness, cell-size, or observation-rate flags
        change it to `DESIGN AT RISK`. A zero minimum worthwhile effect would collapse this rule into a bare
        significance statement, so the contract page refuses to save it and a zero threshold reads as
        `DIRECTIONAL ONLY` rather than a decision. No status is triggered by p < .05.

        ### Explicit non-support in version 1.2

        Do not use this release as if it handled clustered or market-level assignment, repeated observations, paired or
        crossover studies, blocking/stratification-specific randomization inference, count/ordered/survival outcomes,
        instrumental variables, treatment noncompliance, network interference, adaptive experiments, sequential stopping,
        missing-outcome correction, heterogeneous-treatment-effect discovery, or observational causal identification.
        Those designs need estimators and uncertainty calculations matched to their assignment and outcome structure.

        ### Primary references

        - Neyman, J. (1923/1990). *On the Application of Probability Theory to Agricultural Experiments: Essay on Principles, Section 9*. Statistical Science, 5(4), 465–472.
        - Rubin, D. B. (1974). *Estimating causal effects of treatments in randomized and nonrandomized studies*. Journal of Educational Psychology, 66, 688–701.
        - Welch, B. L. (1951). *On the Comparison of Several Mean Values: An Alternative Approach*. Biometrika, 38, 330–336.
        - MacKinnon, J. G., & White, H. (1985). *Some heteroskedasticity-consistent covariance matrix estimators with improved finite sample properties*. Journal of Econometrics, 29, 305–325.
        - Long, J. S., & Ervin, L. H. (2000). *Using heteroscedasticity consistent standard errors in the linear regression model*. The American Statistician, 54(3), 217–224.
        - Holm, S. (1979). *A Simple Sequentially Rejective Multiple Test Procedure*. Scandinavian Journal of Statistics, 6, 65–70.
        - Wilson, E. B. (1927). *Probable inference, the law of succession, and statistical inference*. Journal of the American Statistical Association, 22, 209–212.
        - Newcombe, R. G. (1998). *Interval estimation for the difference between independent proportions: comparison of eleven methods*. Statistics in Medicine, 17(8), 873–890.
        - Lin, W. (2013). *Agnostic notes on regression adjustments to experimental data*. Annals of Applied Statistics, 7, 295–318.
        - Wasserstein, R. L., & Lazar, N. A. (2016). *The ASA Statement on p-Values: Context, Process, and Purpose*. The American Statistician, 70, 129–133.
        - Lakens, D. (2013). *Calculating and reporting effect sizes to facilitate cumulative science*. Frontiers in Psychology, 4, 863.
        """
    )
    st.info(
        "Experiment Signal is an independent implementation built from public statistical literature and original "
        "synthetic examples. It does not reproduce course slides, proprietary cases, exam questions, teaching diagrams, "
        "or institution-specific wording."
    )


PAGES = {
    "Welcome": render_welcome,
    "1 · Design contract": render_contract,
    "2 · Data & randomization audit": render_audit,
    "3 · Effects & uncertainty": render_effects,
    "4 · Decision & export": render_decision,
    "Power planner": render_power,
    "Methods & limits": render_methods,
}


def _handle_upload(upload) -> None:
    raw = upload.getvalue()
    fingerprint = hashlib.sha256(raw).hexdigest()
    if fingerprint == st.session_state.get(k("upload_fingerprint")):
        return
    try:
        frame, source = read_table(raw, upload.name)
        st.session_state[k("data")] = frame
        st.session_state[k("source")] = source
        st.session_state[k("upload_fingerprint")] = fingerprint
        _replace_contract(None)
        reset_results()
        st.success(f"Loaded {len(frame):,} rows × {len(frame.columns):,} columns.")
    except Exception as exc:
        show_error(exc)


def _sidebar() -> str:
    """Draw the sidebar lockup, data controls, page selector and status caption; return the selected page."""
    sig.sidebar_brand(NS, SIDEBAR_TAGLINE)
    with st.sidebar:
        if st.button("Load fictional 2×2 demo", key=k("load_demo")):
            load_demo()
        if st.button("Load fictional binary message demo", key=k("load_binary_demo")):
            load_binary_demo()
        upload = st.file_uploader("Upload experiment data", type=["csv", "xlsx", "json"], key=k("upload"))
        if upload is not None:
            _handle_upload(upload)
        st.download_button(
            "Download starter template",
            dataframe_to_xlsx(starter_template()),
            file_name="experimentsignal-starter-template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=k("download_template"),
        )
        if k("data") in st.session_state:
            data = st.session_state[k("data")]
            st.caption(f"Active data · {len(data):,} rows × {len(data.columns):,} columns")
        page = st.radio("Navigate", list(PAGES), label_visibility="collapsed", key=k("page"))
        st.caption("Local mode · no telemetry · no external AI calls · uploads stay in this Python process")
    return page


def render() -> None:
    """Draw the whole Experiment Signal app on the current page. Never calls st.set_page_config or st.navigation."""
    sig.apply(NS)
    _ensure_state()
    page = _sidebar()
    sig.masthead(NS, MASTHEAD_PROMISES, MASTHEAD_KICKER)
    try:
        PAGES[page]()
    except Exception as exc:
        show_error(exc)
    sig.footer(NS, __version__, FOOTER_LINE)
