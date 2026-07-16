from __future__ import annotations

import os

# Keep Arrow serialization stable on macOS. This must be set before Streamlit imports Arrow.
os.environ.setdefault("ARROW_DEFAULT_MEMORY_POOL", "system")

import base64
import hashlib
import html
import inspect
from pathlib import Path
import sys
import traceback

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

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


PAGES = [
    "Welcome",
    "1 · Design contract",
    "2 · Data & randomization audit",
    "3 · Effects & uncertainty",
    "4 · Decision & export",
    "Power planner",
    "Methods & limits",
]
COLORS = {
    "ink": "#17322E",
    "deep": "#102C2A",
    "teal": "#173C3A",
    "coral": "#D95B40",
    "mint": "#83D2B4",
    "gold": "#F2C66D",
    "paper": "#F8F5ED",
    "muted": "#59716C",
}
CAUTION = (
    "**ExperimentSignal estimates contrasts; it does not manufacture randomization.** A causal reading also requires "
    "a valid assignment process, one observation per randomized unit, treatment before outcome, acceptable missingness, "
    "limited interference, and faithful implementation. P-values are never the decision rule."
)
mark_path = ROOT / "assets" / "experimentsignal-mark.svg"
MARK_URI = (
    "data:image/svg+xml;base64," + base64.b64encode(mark_path.read_bytes()).decode("ascii")
    if mark_path.exists()
    else ""
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


st.set_page_config(page_title="ExperimentSignal | Causal experiment decisions", page_icon="✦", layout="wide")
st.markdown(
    """
    <style>
    :root {
        --xs-ink:#17322e; --xs-deep:#102c2a; --xs-teal:#173c3a;
        --xs-coral:#d95b40; --xs-mint:#83d2b4; --xs-gold:#f2c66d;
        --xs-paper:#f8f5ed; --xs-line:rgba(23,50,46,.14);
    }
    [data-testid="stAppViewContainer"] {
        background:radial-gradient(circle at 94% 2%,rgba(131,210,180,.17),transparent 28rem),
                   radial-gradient(circle at 3% 93%,rgba(242,198,109,.14),transparent 25rem),
                   linear-gradient(180deg,#fbf9f3 0%,var(--xs-paper) 100%);
    }
    [data-testid="stHeader"] { background:rgba(248,245,237,.78); }
    [data-testid="stSidebar"] { background:linear-gradient(165deg,#173c3a 0%,#102c2a 65%,#0c2422 100%); }
    [data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stSidebar"] span { color:#f8f5ed; }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p { color:#b9cbc5; }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
        background:rgba(255,255,255,.06); border-color:rgba(242,198,109,.32);
    }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] small,
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] small span { color:#b9cbc5 !important; }
    [data-testid="stSidebar"] button {
        background:rgba(255,255,255,.08); color:#f8f5ed !important; border-color:rgba(255,255,255,.23);
    }
    [data-testid="stSidebar"] button:hover { background:rgba(242,198,109,.14); border-color:rgba(242,198,109,.48); }
    [data-testid="stSidebar"] button * { color:#f8f5ed !important; }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button {
        background:#f8f5ed; color:#17322e !important;
    }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button * { color:#17322e !important; }
    .block-container { max-width:1240px; padding-top:4.4rem; padding-bottom:4rem; }
    h1,h2,h3 { color:var(--xs-ink); letter-spacing:-.025em; }
    a { color:#9b3e2b; }
    [data-testid="stMetric"] {
        background:rgba(255,255,255,.75); border:1px solid var(--xs-line); border-radius:16px;
        padding:1rem 1.05rem; box-shadow:0 8px 28px rgba(23,50,46,.045);
    }
    [data-testid="stMetricValue"] { color:var(--xs-ink); font-size:clamp(1.35rem,2.3vw,1.9rem); }
    .stButton > button[kind="primary"] {
        background:linear-gradient(135deg,#e26748,#c94c34); color:white; border:0;
        box-shadow:0 8px 20px rgba(217,91,64,.22); font-weight:750;
    }
    .stButton > button[kind="primary"]:hover { background:linear-gradient(135deg,#c94c34,#b63f2b); color:white; }
    button:focus-visible,a:focus-visible,input:focus-visible { outline:3px solid #f2c66d !important; outline-offset:2px; }
    [data-testid="stExpander"],[data-testid="stAlert"],[data-testid="stVerticalBlockBorderWrapper"] { border-radius:14px; }
    .xs-lockup { display:flex; align-items:center; gap:.65rem; }
    .xs-mark { width:38px; height:38px; }
    .xs-name { color:white; font-size:1.28rem; line-height:1; font-weight:850; letter-spacing:-.04em; }
    .xs-name span { color:#f2c66d !important; }
    .xs-tag { margin:.55rem 0 0 !important; color:#b9cbc5 !important; font-size:.77rem; line-height:1.4; }
    .xs-masthead {
        display:flex; justify-content:space-between; align-items:center; gap:1rem; padding:.72rem 1rem .72rem .78rem;
        margin-bottom:1.35rem; background:rgba(255,255,255,.65); border:1px solid var(--xs-line);
        border-radius:18px; box-shadow:0 10px 36px rgba(23,50,46,.05);
    }
    .xs-masthead .xs-mark { width:48px; height:48px; }
    .xs-wordmark { color:var(--xs-ink); font-weight:850; letter-spacing:-.045em; font-size:1.55rem; line-height:1; }
    .xs-wordmark span { color:var(--xs-coral); }
    .xs-kicker { margin-top:.32rem; color:#59716c; font-size:.67rem; font-weight:800; letter-spacing:.13em; }
    .xs-promise { color:#47645e; font-size:.78rem; font-weight:700; white-space:nowrap; }
    .xs-promise span { color:var(--xs-coral); padding:0 .3rem; }
    .xs-hero {
        position:relative; overflow:hidden; padding:clamp(1.7rem,4vw,3.4rem); margin-bottom:1.3rem;
        background:linear-gradient(135deg,#173c3a 0%,#102c2a 75%); border-radius:26px;
        box-shadow:0 18px 50px rgba(23,50,46,.17);
    }
    .xs-hero:after {
        content:""; position:absolute; width:330px; height:330px; right:-105px; top:-148px;
        border-radius:50%; border:56px solid rgba(131,210,180,.12);
    }
    .xs-eyebrow { color:#83d2b4; font-size:.72rem; font-weight:850; letter-spacing:.16em; }
    .xs-hero h1 { color:white; font-size:clamp(2.25rem,5vw,4.7rem); line-height:.97; margin:.75rem 0 1rem; max-width:960px; }
    .xs-hero h1 em { color:#f2c66d; font-style:normal; }
    .xs-hero p { color:#d7e3df; font-size:1.06rem; line-height:1.6; max-width:820px; }
    .xs-pills { display:flex; flex-wrap:wrap; gap:.55rem; margin-top:1.15rem; }
    .xs-pill {
        padding:.4rem .72rem; border:1px solid rgba(255,255,255,.16); border-radius:999px;
        color:#f8f5ed; font-size:.78rem; font-weight:700; background:rgba(255,255,255,.055);
    }
    .xs-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:1rem; }
    .xs-card {
        height:100%; padding:1.2rem 1.2rem 1rem; background:rgba(255,255,255,.68);
        border:1px solid var(--xs-line); border-radius:18px;
    }
    .xs-card b { color:var(--xs-coral); font-size:.72rem; letter-spacing:.12em; }
    .xs-card h3 { margin:.4rem 0 .5rem; }
    .xs-card p { color:#59716c; font-size:.9rem; line-height:1.55; }
    .xs-note {
        padding:1rem 1.1rem; margin:.75rem 0 1rem; border-left:4px solid var(--xs-mint);
        background:rgba(255,255,255,.62); border-radius:0 14px 14px 0; color:#47645e;
    }
    .xs-decision {
        padding:1.3rem 1.4rem; margin:1rem 0; color:white; border-radius:18px;
        background:linear-gradient(135deg,#173c3a,#102c2a); box-shadow:0 12px 34px rgba(23,50,46,.14);
    }
    .xs-decision b { color:#f2c66d; font-size:.78rem; letter-spacing:.14em; }
    .xs-decision h2 { color:white; margin:.35rem 0 .4rem; }
    .xs-decision p { color:#d7e3df; margin:.35rem 0 0; }
    .xs-footer { margin-top:3.2rem; padding-top:1rem; border-top:1px solid var(--xs-line); color:#617670; font-size:.76rem; text-align:center; }
    .xs-footer span { color:var(--xs-coral); padding:0 .38rem; }
    @media (max-width:1050px) { .xs-grid{grid-template-columns:1fr} }
    @media (max-width:760px) { .xs-promise{display:none}.xs-hero{border-radius:20px}.block-container{padding-top:3.5rem} }
    @media (prefers-reduced-motion:reduce) { * { scroll-behavior:auto !important; transition:none !important; } }
    </style>
    """,
    unsafe_allow_html=True,
)


def show_error(exc: Exception) -> None:
    st.error(friendly_message(exc))
    if not isinstance(exc, (DataProblem, ValueError)) and os.getenv("EXPERIMENTSIGNAL_DEBUG") == "1":
        with st.expander("Technical details"):
            st.code("".join(traceback.format_exception(exc)))


def reset_results() -> None:
    for key in ("audit", "analysis", "decision"):
        st.session_state.pop(key, None)


def load_demo() -> None:
    demo = demo_dataframe()
    st.session_state["data"] = demo
    st.session_state["source"] = {
        "source_filename": "experimentsignal-fictional-factorial-demo.csv",
        "source_sheet": "",
        "source_sha256": hashlib.sha256(demo.to_csv(index=False).encode("utf-8")).hexdigest(),
        "source_type": "deterministic synthetic demonstration",
    }
    st.session_state["contract"] = demo_defaults()
    reset_results()


def load_binary_demo() -> None:
    demo = binary_demo_dataframe()
    st.session_state["data"] = demo
    st.session_state["source"] = {
        "source_filename": "experimentsignal-fictional-binary-message-demo.csv",
        "source_sheet": "",
        "source_sha256": hashlib.sha256(demo.to_csv(index=False).encode("utf-8")).hexdigest(),
        "source_type": "deterministic synthetic demonstration",
    }
    st.session_state["contract"] = binary_demo_defaults()
    reset_results()


def masthead() -> None:
    mark = f'<img class="xs-mark" src="{MARK_URI}" alt="">' if MARK_URI else ""
    st.markdown(
        f"""
        <div class="xs-masthead">
          <div class="xs-lockup">{mark}<div><div class="xs-wordmark">Experiment<span>Signal</span></div>
          <div class="xs-kicker">DESIGN → ESTIMATE → DECIDE</div></div></div>
          <div class="xs-promise">Practical effects <span>◆</span> Robust uncertainty <span>◆</span> Local evidence</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def footer() -> None:
    st.markdown(
        f'<div class="xs-footer">ExperimentSignal v{__version__} <span>◆</span> randomized contrasts do not '
        "manufacture randomization <span>◆</span> Part of the Signal suite <span>◆</span> AGPL-3.0-or-later</div>",
        unsafe_allow_html=True,
    )


def select_index(options: list[str], value: object, fallback: int = 0) -> int:
    return options.index(value) if value in options else min(fallback, len(options) - 1)


def render_welcome() -> None:
    st.markdown(
        """
        <section class="xs-hero">
          <div class="xs-eyebrow">EXPERIMENT DECISION SUPPORT</div>
          <h1>Did the treatment cause a change <em>worth acting on?</em></h1>
          <p>Turn a randomized between-subject experiment into an auditable decision record: declare the contrast,
          inspect assignment and observation, estimate effects with robust uncertainty, and compare the interval with
          a business threshold written before the result.</p>
          <div class="xs-pills"><span class="xs-pill">continuous & binary outcomes</span>
          <span class="xs-pill">1–3 treatment factors</span><span class="xs-pill">HC3 intervals</span>
          <span class="xs-pill">Holm multiplicity</span><span class="xs-pill">factorial decomposition</span>
          <span class="xs-pill">a priori power</span><span class="xs-pill">privacy-minimized exports</span></div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.warning(CAUTION)
    st.markdown(
        """
        <div class="xs-grid">
          <div class="xs-card"><b>01 · CONTRACT</b><h3>Write the claim first</h3><p>Name the unit, population,
          outcome, treatment cells, primary contrast, minimum worthwhile effect, exclusions, and stopping rule.</p></div>
          <div class="xs-card"><b>02 · AUDIT</b><h3>Interrogate the design</h3><p>Check unique units, assigned-cell
          counts, outcome observation rates, baseline standardized differences, and complete-case retention.</p></div>
          <div class="xs-card"><b>03 · DECIDE</b><h3>Read magnitude with uncertainty</h3><p>Use the declared contrast and
          confidence interval for the decision. Treat omnibus tests and pairwise p-values as supporting diagnostics.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("### A deliberately bounded release")
    st.write(
        "ExperimentSignal analyzes continuous and binary outcomes from individually randomized, between-subject designs. "
        "It supports one-way and factorial cells, optional numeric pre-treatment adjustment, robust cell contrasts, "
        "and two-arm power planning. It does not currently claim support for clustered assignment, crossover "
        "or repeated-measures designs, count/survival outcomes, adaptive stopping, noncompliance estimands, "
        "or observational causal identification."
    )
    if "data" not in st.session_state:
        st.info("Load the fictional demonstration from the sidebar, or upload a CSV/XLSX/JSON table.")


def render_contract() -> None:
    st.title("1 · Design contract")
    st.caption("Declare the analysis roles and decision boundary. The app will not infer them from whichever result looks best.")
    if "data" not in st.session_state:
        st.info("Load or upload experiment data first.")
        return
    data: pd.DataFrame = st.session_state["data"]

    templates = contract_templates()
    with st.expander("Start from a template · optional"):
        template_name = st.selectbox(
            "Template",
            list(templates),
            key="contract_template",
            help="Prefills the claim wording and outcome type. It never invents data, columns, or thresholds.",
        )
        selected_template = dict(templates[template_name])
        st.caption(str(selected_template.pop("note", "")))
        if st.button("Apply template", key="apply_template"):
            merged = dict(st.session_state.get("contract", {}))
            merged.update(selected_template)
            st.session_state["contract"] = merged
            reset_results()
            st.success(f"Applied the “{template_name}” template. Review every field before saving.")

    current = dict(st.session_state.get("contract", {}))
    st.markdown("#### Data roles")
    outcome_type = st.selectbox(
        "Primary outcome type",
        ["continuous", "binary"],
        index=0 if current.get("outcome_type", "continuous") == "continuous" else 1,
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
            help="Used to detect repeated rows for the same randomized unit.",
        )
        if not outcome_candidates:
            st.error(f"No {outcome_type} outcome candidate was detected.")
            return
        outcome = st.selectbox(
            "Primary outcome",
            outcome_candidates,
            index=select_index(outcome_candidates, current.get("outcome")),
        )
        success_value = None
        if outcome_type == "binary":
            success_levels = ordered_levels(data[outcome].dropna().astype(str))
            success_value = st.selectbox(
                "Value that means success",
                success_levels,
                index=select_index(success_levels, current.get("success_value"), fallback=len(success_levels) - 1),
                help="The other observed value is encoded as 0; this value is encoded as 1.",
            )
    with col2:
        factors_default = [item for item in current.get("factors", []) if item in factor_candidates]
        factors = st.multiselect(
            "Treatment factor(s) · choose 1–3",
            factor_candidates,
            default=factors_default,
            max_selections=3,
            help="Columns that encode randomized treatment levels—not segments discovered after the result.",
        )
        covariate_options = [column for column in numeric_columns if column != outcome and column not in factors]
        covariates = st.multiselect(
            "Pre-treatment numeric covariates · optional",
            covariate_options,
            default=[item for item in current.get("covariates", []) if item in covariate_options],
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
    col1, col2, col3 = st.columns([1, 1, 0.7])
    with col1:
        control = st.selectbox(
            "Primary control cell",
            labels,
            index=select_index(labels, current.get("control_arm")),
        )
    treatment_options = [label for label in labels if label != control]
    with col2:
        treatment = st.selectbox(
            "Primary treatment cell",
            treatment_options,
            index=select_index(treatment_options, current.get("treatment_arm")),
        )
    with col3:
        if outcome_type == "binary":
            minimum_effect_pp = st.number_input(
                "Minimum worthwhile lift · percentage points",
                min_value=0.0,
                max_value=100.0,
                value=min(100 * float(current.get("minimum_effect", 0.0)), 100.0),
                step=0.5,
                help="Enter 3 for a 3-percentage-point lift. Set it before reading the estimate.",
            )
            minimum_effect = minimum_effect_pp / 100
        else:
            minimum_effect = st.number_input(
                "Minimum worthwhile effect",
                min_value=0.0,
                value=float(current.get("minimum_effect", 0.0)),
                step=0.10,
                help="In outcome units. Set from economics, customer value, or policy—not from the observed estimate.",
            )

    st.markdown("#### Claim and protocol")
    question = st.text_input("Decision question", value=str(current.get("question", "")))
    population = st.text_input("Target population", value=str(current.get("population", "")))
    col1, col2 = st.columns(2)
    with col1:
        assignment_method = st.text_area("Assignment mechanism", value=str(current.get("assignment_method", "")), height=92)
        analysis_population = st.text_area("Analysis population and exclusions", value=str(current.get("analysis_population", "")), height=92)
    with col2:
        stopping_rule = st.text_area("Sample-size / stopping rule", value=str(current.get("stopping_rule", "")), height=92)
        guardrail = st.text_area("Guardrail outcome or harm check", value=str(current.get("guardrail", "")), height=92)

    st.markdown("#### Design confirmations")
    col1, col2 = st.columns(2)
    with col1:
        randomized_confirmed = st.checkbox(
            "Treatment was assigned by a known random mechanism",
            value=bool(current.get("randomized_confirmed", False)),
        )
        outcome_prespecified = st.checkbox(
            "Primary outcome and contrast were set before reading results",
            value=bool(current.get("outcome_prespecified", False)),
        )
    with col2:
        treatment_precedes_outcome = st.checkbox(
            "Treatment assignment preceded outcome measurement",
            value=bool(current.get("treatment_precedes_outcome", False)),
        )
        stopping_prespecified = st.checkbox(
            "The stopping rule did not depend on interim outcome significance",
            value=bool(current.get("stopping_prespecified", False)),
        )
    if st.button("Save design contract", type="primary", key="save_contract"):
        if float(minimum_effect) <= 0:
            st.error(
                "Set the minimum worthwhile effect above zero. With a zero threshold the reading collapses "
                "into a bare significance statement, which ExperimentSignal refuses to present as a decision."
            )
            return
        st.session_state["contract"] = {
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
    st.title("2 · Data & randomization audit")
    st.caption("Diagnostics can reveal trouble. They cannot prove that assignment was random or that interference is absent.")
    if "data" not in st.session_state or "contract" not in st.session_state:
        st.info("Load data and save the design contract first.")
        return
    data: pd.DataFrame = st.session_state["data"]
    contract: dict[str, object] = st.session_state["contract"]
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
        confidence = st.select_slider("Confidence level", options=[0.90, 0.95, 0.99], value=0.95)
    with col2:
        permutations = st.select_slider(
            "Randomization permutations",
            options=[0, 999, 4999, 9999],
            value=4999,
            help="Available only for unadjusted two-arm, one-factor data in this release.",
        )
    st.caption("HC3 intervals are primary. A sharp-null permutation p-value is a design-based sensitivity check where supported.")
    if st.button("Run declared analysis", type="primary", key="run_analysis"):
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
            st.session_state["audit"] = audit
            st.session_state["analysis"] = analysis
            st.session_state["decision"] = decision
            st.success("Analysis complete. Continue to effects and uncertainty.")
        except Exception as exc:
            show_error(exc)


def contrast_figure(frame: pd.DataFrame, minimum_effect: float) -> go.Figure:
    ordered = frame.sort_values("estimate").copy()
    figure = go.Figure()
    figure.add_vrect(x0=-minimum_effect, x1=minimum_effect, fillcolor=COLORS["gold"], opacity=0.17, line_width=0)
    figure.add_vline(x=0, line_color=COLORS["muted"], line_dash="dot")
    figure.add_trace(
        go.Scatter(
            x=ordered["estimate"],
            y=ordered["contrast"],
            mode="markers",
            marker={"color": COLORS["coral"], "size": 10},
            error_x={
                "type": "data",
                "symmetric": False,
                "array": ordered["ci_high"] - ordered["estimate"],
                "arrayminus": ordered["estimate"] - ordered["ci_low"],
                "color": COLORS["teal"],
                "thickness": 2,
            },
            hovertemplate="%{y}<br>Effect %{x:.3f}<extra></extra>",
        )
    )
    figure.update_layout(
        height=max(360, 58 * len(ordered)),
        margin={"l": 20, "r": 25, "t": 25, "b": 55},
        xaxis_title="Adjusted outcome difference with confidence interval",
        yaxis_title="",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,.54)",
        font={"color": COLORS["ink"]},
        showlegend=False,
    )
    return figure


def render_effects() -> None:
    st.title("3 · Effects & uncertainty")
    st.caption("The declared treatment-minus-control contrast is primary. Every other comparison is a labeled family.")
    if "analysis" not in st.session_state:
        st.info("Run the declared analysis on the audit page first.")
        return
    analysis = st.session_state["analysis"]
    contract = st.session_state["contract"]
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
    st.markdown(
        f"""
        <div class="xs-note"><strong>Primary estimand:</strong> {estimand} under
        <code>{html.escape(str(primary['treatment_arm']))}</code> minus {estimand} under <code>{html.escape(str(primary['control_arm']))}</code>,
        {adjustment_text}. The estimate is <strong>{estimate_text}</strong> with a
        {html.escape(interval_method)} interval.</div>
        """,
        unsafe_allow_html=True,
    )
    for warning in analysis.warnings:
        st.warning(warning)
    st.markdown("#### Adjusted cell means")
    display_groups = analysis.group_summary.copy()
    full_width(st.dataframe, display_groups.round(3), hide_index=True)
    st.markdown("#### Pairwise contrast family")
    full_width(st.plotly_chart, contrast_figure(analysis.contrasts, float(contract.get("minimum_effect", 0))))
    st.caption(
        f"Gold band: ± the declared minimum worthwhile effect. Intervals are {interval_method}; "
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
    st.title("4 · Decision & export")
    st.caption("A compact handoff that preserves the design claim, uncertainty, audit, and exact analysis settings.")
    if "analysis" not in st.session_state or "decision" not in st.session_state:
        st.info("Run the declared analysis first.")
        return
    decision = st.session_state["decision"]
    analysis = st.session_state["analysis"]
    audit = st.session_state["audit"]
    contract = st.session_state["contract"]
    st.markdown(
        f"""
        <div class="xs-decision"><b>DECLARED-CONTRAST READING</b><h2>{decision['status']}</h2>
        <p>{decision['meaning']}</p><p><strong>Next move:</strong> {decision['action']}</p></div>
        """,
        unsafe_allow_html=True,
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
        source=dict(st.session_state.get("source", {})),
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
    )
    col2.download_button(
        "Download CSV ZIP",
        evidence_to_csv_zip(pack),
        file_name="experimentsignal-evidence-pack.zip",
        mime="application/zip",
    )
    col3.download_button(
        "Download JSON record",
        evidence_to_json(pack),
        file_name="experimentsignal-evidence-pack.json",
        mime="application/json",
    )


def render_power() -> None:
    st.title("Power planner")
    st.caption("Prospective planning only: choose the smallest effect worth detecting before collecting or inspecting outcomes.")
    outcome_type = st.selectbox("Planning outcome", ["continuous", "binary"], key="power_outcome_type")
    st.warning(
        "This approximation is for a fixed, two-sided, two-arm individually randomized design. "
        "It does not account for clustering, repeated measures, covariate gain, noncompliance, sequential looks, or multiple outcomes."
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        if outcome_type == "continuous":
            minimum = st.number_input("Minimum worthwhile raw effect", min_value=0.001, value=0.40, step=0.05)
            sd = st.number_input("Expected outcome SD", min_value=0.001, value=1.50, step=0.10)
        else:
            control_rate = st.number_input(
                "Expected control success rate · %", min_value=0.1, max_value=99.9, value=12.0, step=0.5
            ) / 100
            minimum_lift = st.number_input(
                "Minimum worthwhile lift · percentage points", min_value=0.1, max_value=99.0, value=2.5, step=0.5,
                help="Enter 2.5 for a 2.5-percentage-point lift.",
            ) / 100
    with col2:
        alpha = st.select_slider("Two-sided alpha", options=[0.01, 0.025, 0.05, 0.10], value=0.05)
        power = st.select_slider("Target power", options=[0.70, 0.80, 0.85, 0.90, 0.95], value=0.80)
    with col3:
        ratio = st.number_input("Treatment ÷ control allocation", min_value=0.10, max_value=10.0, value=1.0, step=0.10)
        attrition = st.slider("Expected outcome loss", min_value=0, max_value=60, value=10, step=1)
    if st.button("Plan sample", type="primary", key="plan_sample"):
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
    st.title("Methods & limits")
    st.warning(CAUTION)
    st.markdown(
        """
        ### Estimand before test statistic

        The primary output is the declared treatment-cell mean minus the declared control-cell mean for the primary
        continuous mean or binary risk outcome. With baseline covariates, ExperimentSignal centers those pre-treatment measures and fits
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

        ### Explicit non-support in version 1.1

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
        "ExperimentSignal is an independent implementation built from public statistical literature and original "
        "synthetic examples. It does not reproduce course slides, proprietary cases, exam questions, teaching diagrams, "
        "or institution-specific wording."
    )


# Initialize and render sidebar.
with st.sidebar:
    mark = f'<img class="xs-mark" src="{MARK_URI}" alt="">' if MARK_URI else ""
    st.markdown(
        f'<div class="xs-lockup">{mark}<div class="xs-name">Experiment<span>Signal</span></div></div>'
        '<p class="xs-tag">Causal experiment evidence without the significance theatre.</p>',
        unsafe_allow_html=True,
    )
    if st.button("Load fictional 2×2 demo", key="load_demo"):
        load_demo()
    if st.button("Load fictional binary message demo", key="load_binary_demo"):
        load_binary_demo()
    upload = st.file_uploader("Upload experiment data", type=["csv", "xlsx", "json"])
    if upload is not None:
        raw = upload.getvalue()
        fingerprint = hashlib.sha256(raw).hexdigest()
        if fingerprint != st.session_state.get("upload_fingerprint"):
            try:
                frame, source = read_table(raw, upload.name)
                st.session_state["data"] = frame
                st.session_state["source"] = source
                st.session_state["upload_fingerprint"] = fingerprint
                st.session_state.pop("contract", None)
                reset_results()
                st.success(f"Loaded {len(frame):,} rows × {len(frame.columns):,} columns.")
            except Exception as exc:
                show_error(exc)
    st.download_button(
        "Download starter template",
        dataframe_to_xlsx(starter_template()),
        file_name="experimentsignal-starter-template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    if "data" in st.session_state:
        data = st.session_state["data"]
        st.caption(f"Active data · {len(data):,} rows × {len(data.columns):,} columns")
    page = st.radio("Navigate", PAGES, label_visibility="collapsed")
    st.caption("Local mode · no telemetry · no external AI calls · uploads stay in this Python process")

masthead()
try:
    if page == "Welcome":
        render_welcome()
    elif page == "1 · Design contract":
        render_contract()
    elif page == "2 · Data & randomization audit":
        render_audit()
    elif page == "3 · Effects & uncertainty":
        render_effects()
    elif page == "4 · Decision & export":
        render_decision()
    elif page == "Power planner":
        render_power()
    else:
        render_methods()
except Exception as exc:
    show_error(exc)
footer()
