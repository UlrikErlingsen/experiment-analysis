"""Friendly domain errors for ExperimentSignal."""


class DataProblem(ValueError):
    """Raised when an input cannot support the requested analysis."""


def friendly_message(exc: Exception) -> str:
    """Return a concise user-facing error without exposing internals."""
    if isinstance(exc, DataProblem):
        return str(exc)
    if isinstance(exc, (KeyError, ValueError, TypeError)):
        return f"ExperimentSignal could not complete that request: {exc}"
    return "ExperimentSignal hit an unexpected problem. Check the data roles and try again."

