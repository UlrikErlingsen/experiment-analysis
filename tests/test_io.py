from __future__ import annotations

from io import BytesIO
import json
import zipfile

import pandas as pd
import pytest

from experimentsignal.analysis import AnalysisConfig, analyze_experiment
from experimentsignal.design import audit_experiment, classify_decision
from experimentsignal import limits
from experimentsignal.errors import DataProblem, friendly_message
from experimentsignal.examples import demo_dataframe, demo_defaults
import experimentsignal.io as eio
from experimentsignal.io import (
    build_evidence_pack,
    dataframe_to_xlsx,
    evidence_to_csv_zip,
    evidence_to_excel,
    evidence_to_json,
    read_table,
    safe_frame,
)


def completed_pack() -> dict[str, object]:
    frame = demo_dataframe()
    defaults = demo_defaults()
    audit = audit_experiment(
        frame,
        unit=defaults["unit"],
        outcome=defaults["outcome"],
        factors=defaults["factors"],
        covariates=defaults["covariates"],
    )
    analysis = analyze_experiment(
        frame,
        AnalysisConfig(
            outcome=defaults["outcome"],
            factors=tuple(defaults["factors"]),
            covariates=tuple(defaults["covariates"]),
            control_arm=defaults["control_arm"],
            treatment_arm=defaults["treatment_arm"],
            minimum_effect=defaults["minimum_effect"],
        ),
    )
    decision = classify_decision(
        estimate=analysis.primary["estimate"],
        ci_low=analysis.primary["ci_low"],
        ci_high=analysis.primary["ci_high"],
        minimum_effect=defaults["minimum_effect"],
        randomized_confirmed=True,
        audit=audit,
    )
    return build_evidence_pack(
        source={"source_filename": "demo.csv", "source_sha256": "abc"},
        contract=defaults,
        audit=audit,
        analysis=analysis,
        decision=decision,
    )


def test_read_csv_json_and_xlsx() -> None:
    frame = pd.DataFrame({"unit": [1, 2], "arm": ["A", "B"], "outcome": [3.0, 4.0]})
    csv_frame, csv_meta = read_table(frame.to_csv(index=False).encode(), "study.csv")
    json_frame, _ = read_table(frame.to_json(orient="records").encode(), "study.json")
    xlsx_frame, xlsx_meta = read_table(dataframe_to_xlsx(frame), "study.xlsx")
    pd.testing.assert_frame_equal(csv_frame, json_frame, check_dtype=False)
    pd.testing.assert_frame_equal(csv_frame, xlsx_frame, check_dtype=False)
    assert csv_meta["source_sha256"]
    assert xlsx_meta["source_sheet"] == "Experiment data"


def test_spreadsheet_formula_text_is_neutralized() -> None:
    safe = safe_frame(pd.DataFrame({"label": ["=1+1", "+cmd", "ordinary"], "value": [-2, 3, 4]}))
    assert safe["label"].tolist() == ["'=1+1", "'+cmd", "ordinary"]
    assert safe["value"].tolist() == [-2, 3, 4]


def test_evidence_exports_are_readable_and_exclude_raw_rows() -> None:
    pack = completed_pack()
    json_bytes = evidence_to_json(pack)
    payload = json.loads(json_bytes)
    assert payload["schema"] == "experimentsignal.evidence.v1"
    assert "tables" in payload
    assert "PX-0001" not in json_bytes.decode()
    workbook = pd.ExcelFile(BytesIO(evidence_to_excel(pack)), engine="openpyxl")
    assert "Primary contrast" in workbook.sheet_names
    with zipfile.ZipFile(BytesIO(evidence_to_csv_zip(pack))) as archive:
        assert "manifest.json" in archive.namelist()
        assert "pairwise_contrasts.csv" in archive.namelist()


def test_local_mode_accepts_input_beyond_every_demo_cap(monkeypatch) -> None:
    monkeypatch.delenv("SIGNAL_PUBLIC", raising=False)
    rows = limits.DEMO_MAX_ROWS + 1
    raw = ("arm,outcome\n" + "A,1\nB,2\n" * (rows // 2) + "A,1\n").encode()
    frame, _ = read_table(raw, "large.csv")
    assert len(frame) == rows
    width = limits.DEMO_MAX_COLUMNS + 1
    wide = pd.DataFrame([range(width)], columns=[f"c{i}" for i in range(width)])
    assert read_table(wide.to_csv(index=False).encode(), "wide.csv")[0].shape[1] == width
    assert limits.max_upload_bytes() is None and limits.max_rows() is None and limits.max_permutations() is None


def test_public_demo_enforces_its_caps_with_a_demo_message(monkeypatch) -> None:
    monkeypatch.setenv("SIGNAL_PUBLIC", "1")
    raw = pd.DataFrame({"arm": ["A", "B"] * 6, "outcome": range(12)}).to_csv(index=False).encode()
    monkeypatch.setattr(limits, "DEMO_MAX_ROWS", 10)
    with pytest.raises(DataProblem, match="at most 10 rows.*downloadable Experiment Signal app has no built-in limit"):
        read_table(raw, "study.csv")
    monkeypatch.setattr(limits, "DEMO_MAX_UPLOAD_MB", 0)
    with pytest.raises(DataProblem, match="files up to 0 MB.*public demo only"):
        read_table(raw, "study.csv")
    assert limits.max_permutations() == limits.DEMO_MAX_PERMUTATIONS


def test_running_out_of_memory_is_reported_plainly(monkeypatch) -> None:
    def no_memory(*args, **kwargs):
        raise MemoryError

    monkeypatch.setattr(eio.pd, "read_csv", no_memory)
    with pytest.raises(DataProblem, match="not enough memory on this computer"):
        read_table(b"arm,outcome\nA,1\n", "study.csv")
    assert friendly_message(MemoryError()) == limits.MEMORY_MESSAGE
