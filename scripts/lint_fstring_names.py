#!/usr/bin/env python3
"""Fail on f-string expressions that reference names which are not bound.

Why: HTML/JS templates written as Python f-strings turn a stray literal brace
into an expression. A typo like f"... replace('{sec}', sec) ..." raises
`NameError: name 'sec' is not defined` at request time only — the service keeps
reporting healthy while one page 500s (that is exactly how the QR confirm page
broke). Python catches this statically; this script does the same without
adding a dependency.

Scope-aware: parameters, assignments, imports, comprehension targets, except
handlers, walrus, with-as and enclosing scopes all count as bound, plus
builtins. Anything else inside an f-string replacement field is reported.

Usage: python3 scripts/lint_fstring_names.py [paths...]   (default: app)
Exit: 0 clean, 1 findings, 2 usage error.
"""
from __future__ import annotations

import ast
import builtins
import sys
from pathlib import Path

BUILTINS = set(dir(builtins)) | {"__name__", "__file__", "__doc__", "__package__", "self", "cls"}


class ScopeChecker(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.findings: list[str] = []
        self.module_bound: set[str] = set()

    # ── name collection ───────────────────────────────────
    @staticmethod
    def _collect_targets(node: ast.AST, into: set[str]) -> None:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
                into.add(sub.id)
            elif isinstance(sub, ast.arg):
                into.add(sub.arg)
            elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                into.add(sub.name)
            elif isinstance(sub, (ast.Import, ast.ImportFrom)):
                for alias in sub.names:
                    into.add((alias.asname or alias.name).split(".")[0])

    def _scope_names(self, node: ast.AST) -> set[str]:
        names: set[str] = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
                names.add(sub.id)
            elif isinstance(sub, ast.arg):
                names.add(sub.arg)
            elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(sub.name)
            elif isinstance(sub, (ast.Import, ast.ImportFrom)):
                for alias in sub.names:
                    names.add((alias.asname or alias.name).split(".")[0])
            elif isinstance(sub, ast.ExceptHandler) and sub.name:
                names.add(sub.name)
            elif isinstance(sub, ast.NamedExpr):
                self._collect_targets(sub.target, names)
        return names

    # ── checks ────────────────────────────────────────────
    def _check_fstring(self, node: ast.JoinedStr, bound: set[str]) -> None:
        for value in node.values:
            if not isinstance(value, ast.FormattedValue):
                continue
            for sub in ast.walk(value.value):
                if isinstance(sub, ast.Name):
                    if sub.id not in bound:
                        self.findings.append(
                            f"{self.path}:{sub.lineno}: f-string references unbound name "
                            f"'{sub.id}' -> NameError at request time"
                        )

    def visit_Module(self, node: ast.Module) -> None:
        self.module_bound = BUILTINS | self._scope_names(node)
        for child in node.body:
            self.visit(child)

    def _visit_scope(self, node: ast.AST, extra: set[str]) -> None:
        bound = set(extra) | self.module_bound | self._scope_names(node)
        for sub in ast.walk(node):
            if isinstance(sub, ast.JoinedStr):
                self._check_fstring(sub, bound)
            elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # nested scopes see this scope's names
                if sub is not node:
                    inner_extra = bound | {a.arg for a in sub.args.args + sub.args.kwonlyargs}
                    if sub.args.vararg:
                        inner_extra.add(sub.args.vararg.arg)
                    if sub.args.kwarg:
                        inner_extra.add(sub.args.kwarg.arg)
                    self._visit_scope(sub, inner_extra)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_scope(node, set())

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_scope(node, set())

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_scope(node, set())


def check_file(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:  # pragma: no cover - reported separately
        return [f"{path}:{exc.lineno}: syntax error: {exc.msg}"]
    checker = ScopeChecker(path)
    checker.visit(tree)
    # module-level f-strings are checked via visit_Module children
    for child in ast.walk(tree):
        if isinstance(child, ast.JoinedStr):
            checker._check_fstring(child, checker.module_bound)
    return sorted(set(checker.findings))


def main(argv: list[str]) -> int:
    targets = [Path(a) for a in argv[1:]] or [Path("app")]
    files: list[Path] = []
    for target in targets:
        if target.is_dir():
            files.extend(sorted(target.rglob("*.py")))
        elif target.suffix == ".py":
            files.append(target)
        else:
            print(f"skip (not python): {target}", file=sys.stderr)
    if not files:
        print("no python files found", file=sys.stderr)
        return 2

    findings: list[str] = []
    for path in files:
        findings.extend(check_file(path))

    if findings:
        print("f-string name check FAILED:")
        for item in findings:
            print("  " + item)
        return 1
    print(f"f-string name check ok ({len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
