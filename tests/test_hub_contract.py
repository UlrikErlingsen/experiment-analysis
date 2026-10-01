"""Signal Hub contract: importable UI entry point, Streamlit only under ui/, slug-namespaced state, packaged installs."""

import ast
from pathlib import Path
import re
import shutil
import subprocess
import sys
import textwrap

import pytest
from streamlit.testing.v1 import AppTest

from experimentsignal import __version__


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "src" / "experimentsignal"
UI = PACKAGE / "ui"
UI_ONLY_LIBRARIES = {"streamlit", "plotly"}
PAGES = [
    "Welcome",
    "1 · Design contract",
    "2 · Data & randomization audit",
    "3 · Effects & uncertainty",
    "4 · Decision & export",
    "Power planner",
    "Methods & limits",
]
RENDER_SCRIPT = """
from experimentsignal.ui import render

render()
"""


def _imported_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def _rendered_with_analysis() -> AppTest:
    app = AppTest.from_string(RENDER_SCRIPT, default_timeout=120)
    app.run()
    app.button(key="experiment:load_demo").click().run()
    app.sidebar.radio[0].set_value("2 · Data & randomization audit").run()
    app.button(key="experiment:run_analysis").click().run()
    return app


def test_ui_entry_point_matches_the_hub_contract() -> None:
    from experimentsignal.ui import APP_INFO, render

    assert callable(render)
    assert APP_INFO == {
        "product": "Experiment Signal",
        "version": __version__,
        "repo": "experiment-analysis",
        "slug": "experiment",
    }


def test_only_the_ui_package_imports_streamlit_or_plotly() -> None:
    offenders = {
        str(path.relative_to(PACKAGE)): sorted(_imported_roots(path) & UI_ONLY_LIBRARIES)
        for path in PACKAGE.rglob("*.py")
        if UI not in path.parents and _imported_roots(path) & UI_ONLY_LIBRARIES
    }
    assert not offenders, offenders


def test_core_package_imports_without_streamlit_or_plotly() -> None:
    # A fresh interpreter, so modules already imported by other tests cannot hide a stray import.
    code = (
        f"import sys\nsys.path.insert(0, {str(ROOT / 'src')!r})\n"
        "import experimentsignal, experimentsignal.analysis, experimentsignal.design, experimentsignal.errors, "
        "experimentsignal.examples, experimentsignal.io\n"
        "loaded = sorted(name for name in ('streamlit', 'plotly') if name in sys.modules)\n"
        "assert not loaded, loaded\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr


def test_render_never_sets_page_config_or_navigation() -> None:
    for path in UI.glob("*.py"):
        if path.name == "signal_theme.py":
            continue
        source = path.read_text(encoding="utf-8")
        for call in ("st.set_page_config(", "st.navigation(", "st.Page("):
            assert call not in source, (path.name, call)


def test_render_runs_from_a_script_without_set_page_config() -> None:
    app = AppTest.from_string(RENDER_SCRIPT, default_timeout=120)
    app.run()

    assert not app.exception, [error.value for error in app.exception]
    assert app.sidebar.radio[0].key == "experiment:page"
    body = "\n".join(str(item.value) for item in app.markdown)
    assert "EXPERIMENT DECISION SUPPORT" in body
    assert "DESIGN → ESTIMATE → DECIDE" in body
    assert f"Experiment Signal v{__version__}" in body

    app.button(key="experiment:load_demo").click().run()
    assert not app.exception, [error.value for error in app.exception]
    assert "experiment:data" in app.session_state
    assert "data" not in app.session_state
    assert "contract" not in app.session_state


def test_render_runs_the_demo_analysis_with_namespaced_results() -> None:
    app = _rendered_with_analysis()

    assert not app.exception, [error.value for error in app.exception]
    assert app.session_state["experiment:decision"]["status"] == "MEANINGFUL LIFT"
    for bare in ("analysis", "decision", "audit"):
        assert bare not in app.session_state


@pytest.mark.parametrize("page", PAGES)
def test_every_widget_key_is_namespaced(page: str) -> None:
    app = _rendered_with_analysis()
    app.sidebar.radio[0].set_value(page).run()

    assert not app.exception, [error.value for error in app.exception]
    widgets = [
        *app.radio, *app.selectbox, *app.multiselect, *app.checkbox, *app.button, *app.number_input,
        *app.text_input, *app.text_area, *app.select_slider, *app.slider,
    ]
    assert widgets
    unkeyed = [(type(widget).__name__, widget.label) for widget in widgets if widget.key is None]
    assert not unkeyed, unkeyed
    assert all(widget.key.startswith("experiment:") for widget in widgets)


def test_session_state_and_widget_keys_go_through_the_namespace_helper() -> None:
    source = (UI / "app.py").read_text(encoding="utf-8")
    state_keys = re.findall(r"session_state(?:\[|\.get\(|\.pop\(|\.setdefault\()\s*([^,\])]+)", source)
    membership_keys = re.findall(r"(k\([^)]*\)|\S+)\s+(?:not\s+)?in\s+st\.session_state", source)
    widget_keys = re.findall(r"\bkey=([^,)\n]+)", source)
    assert state_keys and membership_keys and widget_keys
    assert all(key.startswith("k(") for key in state_keys), state_keys
    assert all(key.startswith("k(") for key in membership_keys), membership_keys
    assert all(key.startswith("k(") for key in widget_keys), widget_keys
    assert 'NS = "experiment"' in source


def test_ui_reads_no_repo_root_files() -> None:
    # Signal Hub installs the release as a normal package: only src/experimentsignal/ (plus package data) exists.
    # The demo data are generated in code; the only files the UI reads are the theme's packaged marks.
    from experimentsignal.ui import signal_theme as sig

    for path in UI.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for pattern in (".parents[", "parent.parent", '"examples"', '"docs"', "examples/", "docs/", "README"):
            assert pattern not in source, (path.name, pattern)
    assets = Path(sig.ASSETS).resolve()
    assert UI.resolve() in assets.parents
    slug = sig.app("experiment")["slug"]
    for name in (f"{slug}-mark.svg", f"{slug}-mark-32.png", f"{slug}-mark-64.png"):
        assert (assets / "marks" / name).is_file(), name
    assert Path(sig.page_config("experiment")["page_icon"]).resolve().is_relative_to(UI.resolve())


def test_render_works_from_a_copy_holding_only_the_packaged_files(tmp_path: Path) -> None:
    # Mimic the installed wheel: every module under src/experimentsignal plus the declared package data
    # ("experimentsignal.ui" = ["assets/marks/*"]), and nothing from the repository root.
    target = tmp_path / "site" / "experimentsignal"
    for source in PACKAGE.rglob("*.py"):
        if "__pycache__" in source.parts:
            continue
        destination = target / source.relative_to(PACKAGE)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    shutil.copytree(UI / "assets" / "marks", target / "ui" / "assets" / "marks")
    work = tmp_path / "elsewhere"
    work.mkdir()
    code = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(tmp_path / "site")!r})
        from pathlib import Path
        from streamlit.testing.v1 import AppTest
        import experimentsignal

        assert Path(experimentsignal.__file__).resolve().is_relative_to(Path({str(tmp_path)!r}).resolve())
        app = AppTest.from_string({RENDER_SCRIPT!r}, default_timeout=120)
        app.run()
        app.button(key="experiment:load_binary_demo").click().run()
        for page in {PAGES!r}:
            app.sidebar.radio[0].set_value(page).run()
            assert not app.exception, (page, [error.value for error in app.exception])
        app.sidebar.radio[0].set_value("2 · Data & randomization audit").run()
        app.button(key="experiment:run_analysis").click().run()
        app.sidebar.radio[0].set_value("3 · Effects & uncertainty").run()
        assert not app.exception, [error.value for error in app.exception]
        assert app.session_state["experiment:decision"]["status"] == "UNCERTAIN"
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=300, cwd=work
    )
    assert result.returncode == 0, result.stderr[-4000:]
