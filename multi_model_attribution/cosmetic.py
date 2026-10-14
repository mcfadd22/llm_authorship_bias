"""Cosmetic variant: rename local variables consistently across the callee and caller.

Leaves function names, parameters, attribute names, keyword-argument names, globals and
imports untouched. Behaviour preservation is checked by re-running the harness in
build_scenarios, not here.
"""
import ast
import io
import tokenize
from typing import Dict, List, Set, Tuple

SYNONYMS = {
    "total": "acc", "result": "out", "results": "outs", "count": "n_items", "value": "val", "values": "vals",
    "item": "entry", "items": "entries", "x": "v", "y": "w", "i": "idx", "j": "jdx", "n": "num",
    "s": "text", "line": "row", "lines": "rows", "data": "payload", "out": "ret", "res": "resp",
    "tmp": "scratch", "name": "label", "key": "k_", "val": "value_", "avg": "mean_v", "seen": "visited",
    "parts": "pieces", "words": "tokens", "cfg": "settings", "config": "settings", "record": "rec",
    "order": "ord_", "orders": "ords", "token": "tok", "user": "account", "path": "fpath",
}


class SkipCosmetic(Exception):
    pass


def _function_names_and_params(code: str) -> Tuple[Set[str], Set[str]]:
    tree = ast.parse(code)
    fnames, params = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fnames.add(node.name)
            a = node.args
            for p in a.args + a.posonlyargs + a.kwonlyargs:
                params.add(p.arg)
            if a.vararg: params.add(a.vararg.arg)
            if a.kwarg: params.add(a.kwarg.arg)
    return fnames, params


def _local_store_names(code: str) -> Set[str]:
    names = set()
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
    for node in ast.walk(tree):  # names bound by import or as attribute targets are not locals
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                names.discard((a.asname or a.name).split(".")[0])
    return names


def renameable_names(code: str, protected: Set[str]) -> List[str]:
    fnames, params = _function_names_and_params(code)
    return sorted(n for n in _local_store_names(code) if n not in fnames and n not in params and n not in protected)


def make_rename_map(names: List[str], taken: Set[str]) -> Dict[str, str]:
    out = {}
    for n in names:
        new = SYNONYMS.get(n, n + "_val")
        while new in taken or new in names or new in out.values():
            new += "_"
        out[n] = new
    return out


def apply_renames(code: str, mapping: Dict[str, str]) -> str:
    toks = list(tokenize.generate_tokens(io.StringIO(code).readline))
    out = []
    depth = 0
    for k, tok in enumerate(toks):
        t = tok
        if tok.type == tokenize.OP:
            if tok.string in "([{": depth += 1
            elif tok.string in ")]}": depth -= 1
        if tok.type == tokenize.NAME and tok.string in mapping:
            prev = toks[k - 1] if k else None
            nxt = toks[k + 1] if k + 1 < len(toks) else None
            is_attr = prev is not None and prev.type == tokenize.OP and prev.string == "."
            is_kwarg = depth > 0 and nxt is not None and nxt.type == tokenize.OP and nxt.string == "="
            if not is_attr and not is_kwarg:
                t = tok._replace(string=mapping[tok.string])
        out.append(t)
    return tokenize.untokenize(out)


def rename_pair(callee_code: str, caller_code: str, min_names: int = 2) -> Tuple[str, str, Dict[str, str]]:
    """Rename locals in both components with one consistent map. Raises SkipCosmetic if either
    component has fewer than `min_names` renameable locals."""
    f1, p1 = _function_names_and_params(callee_code)
    f2, p2 = _function_names_and_params(caller_code)
    protected = f1 | f2 | p1 | p2
    n1 = renameable_names(callee_code, protected)
    n2 = renameable_names(caller_code, protected)
    if len(n1) < min_names or len(n2) < min_names:
        raise SkipCosmetic(f"too few renameable locals (callee {len(n1)}, caller {len(n2)})")
    all_names = sorted(set(n1) | set(n2))
    mapping = make_rename_map(all_names, protected)
    return apply_renames(callee_code, mapping), apply_renames(caller_code, mapping), mapping
