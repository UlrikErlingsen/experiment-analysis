from pathlib import Path

from streamlit.testing.v1 import AppTest

from experimentsignal import __version__


ROOT = Path(__file__).parents[1]
APP = str(ROOT / "app.py")
UI = ROOT / "src" / "experimentsignal" / "ui"


def test_shared_signal_shell_renders() -> None:
    app = AppTest.from_file(APP, default_timeout=120)
    app.run()

    assert not app.exception, [error.value for error in app.exception]
    body = "\n".join(str(item.value) for item in app.markdown)
    sidebar = "\n".join(str(item.value) for item in app.sidebar.markdown)
    sidebar_captions = "\n".join(str(item.value) for item in app.sidebar.caption)
    assert "DESIGN → ESTIMATE → DECIDE" in body
    assert "EXPERIMENT DECISION SUPPORT" in body
    assert f"Experiment Signal v{__version__}" in body
    assert "randomized contrasts do not manufacture randomization" in body
    assert "Part of the Signal suite" in body
    assert "AGPL-3.0-or-later" in body
    assert "sg-mast" in body  # the shared Signal masthead
    assert "sg-hero" in body  # the shared Signal hero
    assert "sg-foot" in body  # the shared Signal footer
    assert "Causal experiment evidence without the significance theatre" in sidebar
    assert "sg-side" in sidebar  # the shared Signal sidebar lockup
    assert "no telemetry" in sidebar_captions


def test_app_uses_shared_signal_theme_instead_of_pasted_styles() -> None:
    standalone = (ROOT / "app.py").read_text(encoding="utf-8")
    ui_source = (UI / "app.py").read_text(encoding="utf-8")
    theme = (UI / "signal_theme.py").read_text(encoding="utf-8")
    assert 'st.set_page_config(**sig.page_config("experiment"))' in standalone
    assert "sig.apply(NS)" in ui_source
    assert "st.plotly_chart(" not in ui_source  # charts go through sig.chart (template + theme=None)
    assert "sig.chart(NS," in ui_source
    assert "template=sig.template(NS)" in ui_source
    assert "unsafe_allow_html" not in standalone + ui_source
    assert "<style>" not in standalone + ui_source
    for old_colour in ("#173c3a", "#d95b40", "#83d2b4", "#f2c66d", "#17322e", "#102c2a", "#f8f5ed", "#59716c"):
        assert old_colour not in (standalone + ui_source).lower()
    assert (UI / "assets" / "marks" / "experimentsignal-mark-64.png").exists()
    assert ":focus-visible" in theme
    assert "@media (max-width:760px)" in theme
    assert "@media (prefers-reduced-motion:reduce)" in theme
    assert "friendly_message" in ui_source


def test_runtime_scaffolding_is_private_and_uses_the_decide_family() -> None:
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    launcher = (ROOT / "run_app.command").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")

    assert "gatherUsageStats = false" in config
    assert 'base = "light"' in config
    assert 'primaryColor = "#4f80a2"' in config  # Signal Decide family, 600 step
    assert "USER experimentsignal" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "8592" in dockerfile
    assert "--browser.gatherUsageStats=false" in launcher
    assert "EXPERIMENTSIGNAL_PORT" in launcher
    assert 'python-version: ["3.10", "3.11", "3.12", "3.13"]' in workflow
