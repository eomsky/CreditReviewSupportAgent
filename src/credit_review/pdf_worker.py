"""Fresh-process PDF extraction; no inherited Streamlit dependency cache."""
import sys
from datetime import date
from pathlib import Path

from .documents import from_pdf
from .store import atomic_json


def main():
    pdf, published, artifacts, result = sys.argv[1:]
    sources = from_pdf(Path(pdf), date.fromisoformat(published), Path(artifacts))
    atomic_json(Path(result), {'sources': [s.model_dump(mode='json') for s in sources]})


if __name__ == '__main__':
    main()
