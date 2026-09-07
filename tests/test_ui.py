from streamlit.testing.v1 import AppTest
from pathlib import Path

def test_workbench_initial_render():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app' / 'workbench.py')).run(timeout=30)
    assert not app.exception
    assert '기업여신' in app.title[0].value
