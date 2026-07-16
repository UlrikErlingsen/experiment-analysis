"""Safe local import and evidence-pack export helpers."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import platform
import re
import zipfile

import numpy as np
import pandas as pd

from . import __version__
from .errors import DataProblem


MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_ROWS = 250_000
MAX_COLUMNS = 500
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".json"}


def _validate_shape(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        raise DataProblem("The uploaded table has no data rows.")
    if len(frame) > MAX_ROWS:
        raise DataProblem(f"This release accepts at most {MAX_ROWS:,} rows per analysis.")
    if len(frame.columns) > MAX_COLUMNS:
        raise DataProblem(f"This release accepts at most {MAX_COLUMNS:,} columns.")
    names = [str(column).strip() for column in frame.columns]
    if any(not name for name in names):
        raise DataProblem("Every column needs a non-empty name.")
    if len(names) != len(set(names)):
        raise DataProblem("Column names must be unique.")
    frame = frame.copy()
    frame.columns = names
    return frame


def read_table(raw: bytes, filename: str) -> tuple[pd.DataFrame, dict[str, str]]:
    """Read one CSV, XLSX, or JSON table and return source metadata."""
    if not raw:
        raise DataProblem("The uploaded file is empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise DataProblem("The uploaded file exceeds ExperimentSignal's 50 MB local safety limit.")
    extension = Path(filename).suffix.casefold()
    if extension not in ALLOWED_EXTENSIONS:
        raise DataProblem("Use CSV, XLSX, or JSON for experiment data.")
    sheet = ""
    try:
        if extension == ".csv":
            frame = pd.read_csv(BytesIO(raw))
        elif extension == ".xlsx":
            book = pd.ExcelFile(BytesIO(raw), engine="openpyxl")
            if not book.sheet_names:
                raise DataProblem("The workbook has no worksheets.")
            sheet = book.sheet_names[0]
            frame = pd.read_excel(book, sheet_name=sheet)
        else:
            payload = json.loads(raw.decode("utf-8-sig"))
            if isinstance(payload, dict) and isinstance(payload.get("data"), list):
                payload = payload["data"]
            if not isinstance(payload, list):
                raise DataProblem("JSON input must be an array of row objects or an object with a data array.")
            frame = pd.DataFrame(payload)
    except DataProblem:
        raise
    except Exception as exc:
        raise DataProblem(f"The {extension[1:].upper()} file could not be read as a rectangular table.") from exc
    return _validate_shape(frame), {
        "source_filename": Path(filename).name,
        "source_sheet": sheet,
        "source_sha256": sha256(raw).hexdigest(),
    }


_ILLEGAL_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _scrub_control(value: str) -> str:
    return _ILLEGAL_XML.sub("", value)


def _safe_cell(value: object) -> object:
    if isinstance(value, str):
        cleaned = _scrub_control(value)
        if cleaned.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + cleaned
        return cleaned
    return value


def safe_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Neutralize spreadsheet formulas in object cells and column headers."""
    result = frame.copy()
    for column in result.select_dtypes(include=["object", "string"]).columns:
        result[column] = result[column].map(_safe_cell)
    result.columns = [_safe_cell(_scrub_control(str(column))) for column in result.columns]
    return result


def _json_value(value: object) -> object:
    if isinstance(value, pd.DataFrame):
        return [{str(key): _json_value(item) for key, item in row.items()} for row in value.to_dict(orient="records")]
    if is_dataclass(value):
        return _json_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, np.ndarray):
        return [_json_value(item) for item in value.tolist()]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def build_evidence_pack(
    *,
    source: dict[str, object],
    contract: dict[str, object],
    audit,
    analysis,
    decision: dict[str, str],
) -> dict[str, object]:
    """Build a privacy-minimized, reproducible analysis record without row-level outcomes."""
    return {
        "schema": "experimentsignal.evidence.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generated_by": {
            "product": "ExperimentSignal",
            "version": __version__,
            "python": platform.python_version(),
        },
        "causal_status": (
            "Randomized interpretation requested; still conditional on correct assignment, measurement, no interference, "
            "and acceptable missingness."
            if contract.get("randomized_confirmed")
            else "Association only: random assignment was not confirmed."
        ),
        "source": source,
        "design_contract": contract,
        "analysis_config": asdict(analysis.config),
        "model_formula_internal": analysis.model_formula,
        "audit_summary": audit.summary,
        "audit_warnings": list(audit.warnings),
        "analysis_diagnostics": analysis.diagnostics,
        "analysis_warnings": list(analysis.warnings),
        "decision": decision,
        "primary_contrast": analysis.primary,
        "randomization_inference": analysis.permutation,
        "tables": {
            "arm_counts": audit.arm_counts,
            "outcome_observation": audit.outcome_observation,
            "covariate_balance": audit.covariate_balance,
            "group_summary": analysis.group_summary,
            "pairwise_contrasts": analysis.contrasts,
            "factorial_term_tests": analysis.term_tests,
        },
        "privacy_note": "No unit-level outcomes, covariates, identifiers, fitted values, or residuals are included.",
    }


def evidence_to_json(pack: dict[str, object]) -> bytes:
    return json.dumps(_json_value(pack), indent=2, ensure_ascii=False).encode("utf-8")


def _sheet_name(name: str, used: set[str]) -> str:
    cleaned = re.sub(r"[\\/*?:\[\]]", "_", name)[:31] or "Sheet"
    candidate = cleaned
    suffix = 2
    while candidate.casefold() in used:
        marker = f"_{suffix}"
        candidate = cleaned[: 31 - len(marker)] + marker
        suffix += 1
    used.add(candidate.casefold())
    return candidate


def evidence_to_excel(pack: dict[str, object]) -> bytes:
    """Serialize summary metadata and aggregate tables to an XLSX workbook."""
    buffer = BytesIO()
    used: set[str] = set()
    tables = pack.get("tables", {})
    flat_sections = {
        "Read me": {
            "product": "ExperimentSignal",
            "schema": pack.get("schema"),
            "causal_status": pack.get("causal_status"),
            "privacy_note": pack.get("privacy_note"),
        },
        "Source": pack.get("source", {}),
        "Design contract": pack.get("design_contract", {}),
        "Audit summary": pack.get("audit_summary", {}),
        "Diagnostics": pack.get("analysis_diagnostics", {}),
        "Decision": pack.get("decision", {}),
        "Primary contrast": pack.get("primary_contrast", {}),
        "Randomization test": pack.get("randomization_inference") or {"available": False},
    }
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, values in flat_sections.items():
            rows = [{"field": key, "value": _json_value(value)} for key, value in dict(values).items()]
            safe_frame(pd.DataFrame(rows)).to_excel(writer, sheet_name=_sheet_name(name, used), index=False)
        if isinstance(tables, dict):
            for name, frame in tables.items():
                if isinstance(frame, pd.DataFrame):
                    safe_frame(frame).to_excel(writer, sheet_name=_sheet_name(str(name), used), index=False)
        for worksheet in writer.book.worksheets:
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            for column_cells in worksheet.columns:
                width = min(48, max(10, max(len(str(cell.value or "")) for cell in column_cells) + 2))
                worksheet.column_dimensions[column_cells[0].column_letter].width = width
    return buffer.getvalue()


def evidence_to_csv_zip(pack: dict[str, object]) -> bytes:
    """Serialize aggregate tables and a JSON manifest to a portable ZIP."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", evidence_to_json({key: value for key, value in pack.items() if key != "tables"}))
        tables = pack.get("tables", {})
        if isinstance(tables, dict):
            for name, frame in tables.items():
                if isinstance(frame, pd.DataFrame):
                    archive.writestr(f"{name}.csv", safe_frame(frame).to_csv(index=False, lineterminator="\n"))
    return buffer.getvalue()


def dataframe_to_xlsx(frame: pd.DataFrame, sheet_name: str = "Experiment data") -> bytes:
    """Create a safe example/template workbook."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        safe_frame(frame).to_excel(writer, sheet_name=sheet_name, index=False)
        worksheet = writer.book[sheet_name]
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions
        for column_cells in worksheet.columns:
            worksheet.column_dimensions[column_cells[0].column_letter].width = min(
                42, max(11, max(len(str(cell.value or "")) for cell in column_cells) + 2)
            )
    return buffer.getvalue()
