"""Friendly domain errors for Experiment Signal."""


class DataProblem(ValueError):
    """Raised when an input cannot support the requested analysis."""


def friendly_message(exc: Exception) -> str:
    """Return a concise user-facing error without exposing internals."""
    if isinstance(exc, DataProblem):
        return str(exc)
    if isinstance(exc, MemoryError):
        from .limits import MEMORY_MESSAGE

        return MEMORY_MESSAGE
    if isinstance(exc, (KeyError, ValueError, TypeError)):
        return f"Experiment Signal could not complete that request: {exc}"
    return "Experiment Signal hit an unexpected problem. Check the data roles and try again."

