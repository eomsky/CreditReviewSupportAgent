"""One shared reasoning standard for every review-related model entry point."""
from pathlib import Path
import evidence_quality

PATH = Path(__file__).resolve().parents[1] / 'prompts' / 'review_reasoning_rules.txt'


def with_reasoning(prompt):
    rules = PATH.read_text(encoding='utf-8').strip()+'\n'+evidence_quality.RULES
    return prompt if rules in prompt else prompt + '\n\n' + rules
