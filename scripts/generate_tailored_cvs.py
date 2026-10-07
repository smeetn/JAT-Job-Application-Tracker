from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.candidate.cv_tailoring import generate_all_tailored_cvs


def main() -> None:
    resume_dir = ROOT / "data" / "resume"
    output_dir = ROOT / "data" / "candidate" / "cvs"
    generated = generate_all_tailored_cvs(resume_dir, output_dir)
    for path in generated:
        print(f"Created: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
