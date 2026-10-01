"""Experiment Signal user interface: the Signal Hub entry point.

The only package under ``experimentsignal`` that imports Streamlit or Plotly. ``render()`` draws the whole app on
the current page and never calls ``st.set_page_config``; the standalone ``app.py`` or Signal Hub owns the page config.
"""

from experimentsignal import __version__
from experimentsignal.ui import signal_theme
from experimentsignal.ui.app import render

APP_INFO = {"product": "Experiment Signal", "version": __version__, "repo": "experiment-analysis", "slug": "experiment"}

__all__ = ["APP_INFO", "render", "signal_theme"]
