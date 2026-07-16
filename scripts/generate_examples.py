"""Generate the deterministic fictional demonstration and starter template."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

def main() -> None:
    from experimentsignal.examples import demo_dataframe, starter_template
    from experimentsignal.io import dataframe_to_xlsx

    examples = ROOT / "examples"
    examples.mkdir(parents=True, exist_ok=True)
    demo = demo_dataframe()
    template = starter_template()
    demo.to_csv(examples / "experimentsignal-fictional-factorial-demo.csv", index=False)
    (examples / "experimentsignal-fictional-factorial-demo.xlsx").write_bytes(
        dataframe_to_xlsx(demo, "Fictional experiment")
    )
    (examples / "experimentsignal-starter-template.xlsx").write_bytes(dataframe_to_xlsx(template, "Experiment data"))
    assert len(demo) == 480
    assert demo["message_frame"].nunique() == 2
    assert demo["proof_badge"].nunique() == 2


if __name__ == "__main__":
    main()
