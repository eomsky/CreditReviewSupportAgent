"""Bound internal schema explanations while preserving all review decisions."""
import copy


def bound_schema(schema):
    result = copy.deepcopy(schema)
    def visit(node):
        if isinstance(node, dict):
            for key, prop in node.get('properties', {}).items():
                if key in ('reason', 'layout_reason', 'calculation') and prop.get('type') == 'string':
                    prop['maxLength'] = min(prop.get('maxLength', 320), 320)
                    prop['description'] = prop.get('description', '') + ' 핵심 근거 또는 계산식만 간결하게 쓰고 같은 판단을 반복하지 않는다.'
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)
    visit(result)
    return result
