import pytest

from vignette_gen.validate import ValidationError, validate_code

GOOD_CODE = """def compute_average(numbers):
    total = 0
    count = 0
    for number in numbers:
        total += number
        count += 1
    if count == 0:
        return 0
    return total / count
"""

GOOD_CODE_WITH_IMPORT = """import json


def parse_config(raw):
    data = json.loads(raw)
    retries = data.get("retries")
    if retries is None:
        data["retries"] = 3
    timeout = data.get("timeout")
    if timeout is None:
        data["timeout"] = 30
    max_attempts = data.get("max_attempts")
    if max_attempts is None:
        data["max_attempts"] = 5
    return data
"""

GOOD_CODE_WITH_MIDFUNCTION_TRIPLE_QUOTE = '''def build_query(user_id):
    base_query = """
    SELECT * FROM users
    WHERE id = %s
    """
    result = base_query % user_id
    filters = []
    if result:
        filters.append(result)
    final_query = " AND ".join(filters)
    value = final_query if final_query else base_query
    return value
'''


def test_valid_code_passes():
    validate_code(GOOD_CODE)


def test_valid_code_with_leading_import_passes():
    validate_code(GOOD_CODE_WITH_IMPORT)


def test_midfunction_triple_quoted_string_is_not_a_docstring():
    validate_code(GOOD_CODE_WITH_MIDFUNCTION_TRIPLE_QUOTE)


def test_syntax_error_is_rejected():
    with pytest.raises(ValidationError, match="syntax"):
        validate_code("def broken(:\n    pass\n")


def test_docstring_as_first_statement_is_rejected():
    code = '''def f(x):
    """docstring"""
    return x
'''
    with pytest.raises(ValidationError, match="docstring"):
        validate_code(code)


def test_comment_is_rejected():
    code = """def f(x):
    y = x + 1  # add one
    return y
"""
    with pytest.raises(ValidationError, match="comment"):
        validate_code(code)


def test_nested_function_is_rejected():
    code = """def outer(x):
    def inner(y):
        return y
    return inner(x)
"""
    with pytest.raises(ValidationError, match="nested"):
        validate_code(code)


def test_top_level_class_is_rejected():
    code = """class Foo:
    def f(self, x):
        return x
"""
    with pytest.raises(ValidationError, match="class"):
        validate_code(code)


def test_too_few_lines_is_rejected():
    code = """def f(x):
    return x
"""
    with pytest.raises(ValidationError, match="5-25"):
        validate_code(code)


def test_too_many_lines_is_rejected():
    body_lines = "\n".join(f"    x += {i}" for i in range(30))
    code = f"def f(x):\n{body_lines}\n    return x\n"
    with pytest.raises(ValidationError, match="5-25"):
        validate_code(code)


def test_import_after_function_is_rejected():
    code = """def f(x):
    total = 0
    for i in range(x):
        total += i
        total += 1
        total += 2
        total += 3
        total += 4
    return total


import json
"""
    with pytest.raises(ValidationError, match="before the function"):
        validate_code(code)


def test_fstring_as_first_statement_is_rejected():
    code = '''def f(x):
    f"""Computes something useful from x."""
    total = 0
    total += 1
    total += 2
    total += 3
    total += 4
    total += 5
    return total
'''
    with pytest.raises(ValidationError, match="docstring"):
        validate_code(code)
