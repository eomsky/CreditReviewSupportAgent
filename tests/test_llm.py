import pytest
from credit_review.llm import structured_content


def test_structured_json_accepts_model_fence():
    assert structured_content('```json\n{"action":"search"}\n```') == '{"action":"search"}'
    assert structured_content(' {"action":"search"} ') == '{"action":"search"}'


@pytest.mark.parametrize("content", [None, "", "[]", 'explanation {"action":"search"}', '```json\n{"broken":\n```'])
def test_structured_json_rejects_invalid_or_ambiguous_content(content):
    with pytest.raises(ValueError):
        structured_content(content)
