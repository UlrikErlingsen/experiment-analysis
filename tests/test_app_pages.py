from __future__ import annotations

from streamlit.testing.v1 import AppTest


def app() -> AppTest:
    return AppTest.from_file("app.py", default_timeout=30).run()


def test_welcome_page_and_brand_are_rendered() -> None:
    at = app()
    assert not at.exception
    assert any("ExperimentSignal" in markdown.value for markdown in at.markdown)
    assert any("does not manufacture randomization" in warning.value for warning in at.warning)


def test_every_page_renders_with_fictional_demo() -> None:
    at = app()
    at.button(key="load_demo").click().run()
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


def test_demo_analysis_flow_produces_conservative_evidence_pack() -> None:
    at = app()
    at.button(key="load_demo").click().run()
    at.radio[0].set_value("2 · Data & randomization audit").run()
    at.button(key="run_analysis").click().run()
    assert "analysis" in at.session_state
    assert at.session_state["decision"]["status"] == "MEANINGFUL LIFT"

    at.radio[0].set_value("3 · Effects & uncertainty").run()
    assert not at.exception
    assert len(at.metric) >= 4

    at.radio[0].set_value("4 · Decision & export").run()
    assert not at.exception
    assert len(at.download_button) >= 4
