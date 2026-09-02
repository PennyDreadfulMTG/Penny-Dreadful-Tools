#!/usr/bin/env python3
"""
Check that auth.admin_required and auth.demimod_required are always the last
(innermost) decorator on a function. If they are not last, decorators applied
outside them will not propagate the permission_required attribute correctly,
which breaks the admin menu and the test_all_admin_routes_require_permission test.
"""
import ast
import subprocess
import sys
from pathlib import Path

AUTH_DECORATORS = {'admin_required', 'demimod_required'}


def is_auth_decorator(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr in AUTH_DECORATORS
        and isinstance(node.value, ast.Name)
        and node.value.id == 'auth'
    )


def check_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    except SyntaxError:
        return errors

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        decorators = node.decorator_list
        for i, dec in enumerate(decorators):
            if is_auth_decorator(dec) and i != len(decorators) - 1:
                attr = dec.attr  # type: ignore[union-attr]
                errors.append(
                    f'{path}:{dec.lineno}: auth.{attr} must be the last (innermost) '
                    f'decorator on {node.name!r}, but it is at position '
                    f'{i + 1} of {len(decorators)}'
                )
    return errors


def main() -> None:
    if len(sys.argv) > 1:
        paths = [Path(p) for p in sys.argv[1:] if p.endswith('.py')]
    else:
        result = subprocess.run(
            ['git', 'ls-files', '*.py', '**/*.py'],
            capture_output=True, text=True,
        )
        paths = [Path(p) for p in result.stdout.splitlines() if p.endswith('.py')]

    all_errors: list[str] = []
    for path in paths:
        all_errors.extend(check_file(path))

    if all_errors:
        for error in all_errors:
            print(error, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
