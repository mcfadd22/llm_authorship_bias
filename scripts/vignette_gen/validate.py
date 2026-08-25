import ast
import io
import tokenize

MIN_BODY_LINES = 3
MAX_BODY_LINES = 25


class ValidationError(Exception):
    pass


def _has_comment(code: str) -> bool:
    tokens = tokenize.generate_tokens(io.StringIO(code).readline)
    return any(tok.type == tokenize.COMMENT for tok in tokens)


def _is_docstring_expr(node: ast.stmt) -> bool:
    if not isinstance(node, ast.Expr):
        return False
    # Check for plain string constant (traditional docstring)
    if (
        isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ):
        return True
    # Check for f-string (which LLM could use to sneak in explanatory text)
    if isinstance(node.value, ast.JoinedStr):
        return True
    return False


def validate_code(code: str) -> None:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ValidationError(f"syntax error: {exc}") from exc

    top_level_funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    top_level_classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    top_level_other = [
        n
        for n in tree.body
        if not isinstance(n, (ast.FunctionDef, ast.Import, ast.ImportFrom))
    ]

    if top_level_classes:
        raise ValidationError("top-level class definition not allowed")
    if len(top_level_funcs) != 1:
        raise ValidationError(
            f"expected exactly one top-level function, found {len(top_level_funcs)}"
        )
    if top_level_other:
        raise ValidationError(
            "only leading import statements and one function definition allowed at top level"
        )

    func = top_level_funcs[0]
    func_index = tree.body.index(func)

    # Verify all imports appear before the function
    for i, node in enumerate(tree.body):
        if isinstance(node, (ast.Import, ast.ImportFrom)) and i >= func_index:
            raise ValidationError("import statements must appear before the function definition")

    for node in ast.walk(func):
        if node is not func and isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            raise ValidationError("nested function or class not allowed")

    if func.body and _is_docstring_expr(func.body[0]):
        raise ValidationError("docstring not allowed")

    if _has_comment(code):
        raise ValidationError("comment not allowed")

    body_line_count = func.body[-1].end_lineno - func.lineno + 1
    if not (MIN_BODY_LINES <= body_line_count <= MAX_BODY_LINES):
        raise ValidationError(
            f"function body has {body_line_count} lines, expected {MIN_BODY_LINES}-{MAX_BODY_LINES}"
        )
