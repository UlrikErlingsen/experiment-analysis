from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from experimentsignal import __version__

APP = str(Path(__file__).parents[1] / "app.py")


def k(name: str) -> str:
    return f"experiment:{name}"


def app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=30).run()


def test_welcome_page_and_brand_are_rendered() -> None:
    at = app()
    assert not at.exception
    assert any(f"Experiment Signal v{__version__}" in markdown.value for markdown in at.markdown)
    assert any("does not manufacture randomization" in warning.value for warning in at.warning)


def test_every_page_renders_with_fictional_demo() -> None:
    at = app()
    at.button(key=k("load_demo")).click().run()
    for page in [
        "1 · Design contract",
        "2 · Data & randomization audit",
        "3 · Effects & uncertainty",
        "4 · Decision & export",
        "Power planner",
        "Methods & limits",
    ]:
        at.radio[0].set_value(page).run()
        assert not at.exception, page


def test_binary_demo_flow_uses_newcombe_and_reads_an_honest_uncertain_decision() -> None:
    at = app()
    at.button(key=k("load_binary_demo")).click().run()
    at.radio[0].set_value("2 · Data & randomization audit").run()
    at.button(key=k("run_analysis")).click().run()
    assert not at.exception
    analysis = at.session_state[k("analysis")]
    assert analysis.primary["interval_method"] == "Newcombe hybrid Wilson score"
    # The seeded demo is deliberately instructive: evidence of a lift, but the 2 pp practical bound is not cleared.
    assert at.session_state[k("decision")]["status"] == "UNCERTAIN"
    at.radio[0].set_value("3 · Effects & uncertainty").run()
    assert not at.exception
    at.radio[0].set_value("4 · Decision & export").run()
    assert not at.exception


def test_contract_template_selector_prefills_binary_communication_test() -> None:
    at = app()
    at.button(key=k("load_binary_demo")).click().run()
    at.radio[0].set_value("1 · Design contract").run()
    at.selectbox(key=k("contract_template")).set_value("Communication test").run()
    at.button(key=k("apply_template")).click().run()
    assert not at.exception
    contract = at.session_state[k("contract")]
    assert contract["outcome_type"] == "binary"
    assert "recall" in str(contract["question"])
    # The form fields are re-seeded from the applied template instead of keeping stale widget values.
    question = [field for field in at.text_input if field.label == "Decision question"][0]
    assert question.value == contract["question"]


def test_loading_another_demo_reseeds_the_contract_form() -> None:
    at = app()
    at.button(key=k("load_demo")).click().run()
    at.radio[0].set_value("1 · Design contract").run()
    assert [box.value for box in at.selectbox if box.label == "Primary outcome type"] == ["continuous"]
    at.button(key=k("load_binary_demo")).click().run()
    assert not at.exception
    assert [box.value for box in at.selectbox if box.label == "Primary outcome type"] == ["binary"]
    assert [box.value for box in at.selectbox if box.label == "Primary outcome"] == ["recalled_key_claim"]


def test_demo_analysis_flow_produces_conservative_evidence_pack() -> None:
    at = app()
    at.button(key=k("load_demo")).click().run()
    at.radio[0].set_value("2 · Data & randomization audit").run()
    at.button(key=k("run_analysis")).click().run()
    assert k("analysis") in at.session_state
    assert at.session_state[k("decision")]["status"] == "MEANINGFUL LIFT"

    at.radio[0].set_value("3 · Effects & uncertainty").run()
    assert not at.exception
    assert len(at.metric) >= 4

    at.radio[0].set_value("4 · Decision & export").run()
    assert not at.exception
    assert len(at.download_button) >= 4


def test_fresh_run_preloads_the_fictional_factorial_demo() -> None:
    at = app()
    assert not at.exception
    assert k("data") in at.session_state
    assert at.session_state[k("source")]["source_filename"] == "experimentsignal-fictional-factorial-demo.csv"
    assert at.session_state[k("contract")]["outcome"] == "activation_score_0_10"
    assert any("fictional demo is loaded" in info.value for info in at.info)
    # No button click is needed: the audit page shows demo-backed diagnostics and the analysis runs.
    at.radio[0].set_value("2 · Data & randomization audit").run()
    assert not at.exception
    assert [metric.label for metric in at.metric][:2] == ["Assigned rows", "Treatment cells"]
    at.button(key=k("run_analysis")).click().run()
    assert not at.exception
    assert at.session_state[k("decision")]["status"] == "MEANINGFUL LIFT"


UPLOAD_SCRIPT = r"""
import streamlit as st

from experimentsignal.ui import render


class _Upload:
    name = "my-experiment.csv"

    def getvalue(self):
        rows = [f"U{i:03d},{'Treatment' if i % 2 else 'Control'},{4 + (i % 7) / 3:.2f}" for i in range(1, 41)]
        return ("unit_id,treatment,primary_outcome\n" + "\n".join(rows) + "\n").encode("utf-8")


original = st.file_uploader
if st.session_state.get("test:upload"):
    st.file_uploader = lambda *args, **kwargs: _Upload()
try:
    render()
finally:
    st.file_uploader = original
"""


def test_upload_replaces_the_preloaded_demo() -> None:
    at = AppTest.from_string(UPLOAD_SCRIPT, default_timeout=30).run()
    assert at.session_state[k("source")]["source_type"] == "deterministic synthetic demonstration"
    at.session_state["test:upload"] = True
    at.run()
    assert not at.exception
    assert at.session_state[k("source")]["source_filename"] == "my-experiment.csv"
    assert list(at.session_state[k("data")].columns) == ["unit_id", "treatment", "primary_outcome"]
    assert k("contract") not in at.session_state
    assert not any("fictional demo is loaded" in info.value for info in at.info)
    # The demo buttons still restore the fictional demo after an upload.
    at.session_state["test:upload"] = False
    at.button(key=k("load_demo")).click().run()
    assert at.session_state[k("source")]["source_filename"] == "experimentsignal-fictional-factorial-demo.csv"
