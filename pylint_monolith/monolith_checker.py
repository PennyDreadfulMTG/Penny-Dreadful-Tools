from typing import Dict, List, Optional

import astroid
import isort
from pylint.checkers import BaseChecker
from pylint.checkers.utils import check_messages
from pylint.interfaces import IAstroidChecker
from pylint.lint import PyLinter

ACCEPTABLE_IMPORTS: Dict[str, List[str]] = {
    'decksite': ['decksite', 'magic', 'shared', 'shared_web'],
    'discordbot': ['discordbot', 'magic', 'shared'],
    'github_tools': ['github_tools', 'shared', 'shared_web'],
    'logsite': ['logsite', 'shared', 'shared_web'],
    'magic': ['magic', 'shared'],
    'maintenance': ['decksite', 'magic', 'maintenance', 'shared', 'shared_web'],
    'modo_bugs': ['shared', 'shared_web'],
    'price_grabber': ['magic', 'price_grabber', 'shared'],
    'pylint_monolith': ['pylint_monolith'],
    'rotation_script': ['magic', 'price_grabber', 'rotation_script', 'shared'],
    'shared': [],
    'shared_web': ['shared', 'shared_web'],

    'dev': ['magic', 'shared'],
    'generate_readme': ['discordbot'],
    'run': ['discordbot', 'decksite', 'price_grabber', 'rotation_script', 'magic', 'shared'],
}

class MonolithChecker(BaseChecker):
    __implements__ = IAstroidChecker
    name = 'monolith'
    msgs = {
        'E4101': (
            'Module %s should not be importing %s',
            'invalid-monolith-import',
            'Used when code is breaking the monolith structure'
            ' in dangerous ways.'
        )
    }

    options = ()

    def __init__(self, linter: Optional[PyLinter] = None) -> None:
        BaseChecker.__init__(self, linter)
        self.isort_obj = isort.SortImports(
            file_contents='',
        )

    @check_messages(*(msgs.keys()))
    def visit_importfrom(self, node: astroid.nodes.ImportFrom) -> None:
        """triggered when a from statement is seen"""
        # We only care about imports within the monolith.
        basename = get_basename(node.modname)
        import_category = self.isort_obj.place_module(basename)
        if import_category != 'FIRSTPARTY':
            return
        # Get the name of the module that's doing the importing.
        parent = node
        while not isinstance(parent, astroid.Module):
            parent = parent.parent
        parent_basename = get_basename(parent.name)
        # Get the real name of the imported module
        imported_module = _get_imported_module(node, basename)
        if imported_module is None:
            return
        basename = get_basename(imported_module.name)
        # print("{p} ({pb}) -> {i} ({c})".format(p=parent.name, pb=parent_basename, i=imported_module.name, c=import_category))
        # verify

        if parent_basename == imported_module.name:
            return
        if imported_module.name.startswith(f'{parent_basename}.'):
            return

        acceptable: List[str] = ACCEPTABLE_IMPORTS.get(parent_basename, [])
        if not basename in acceptable:
            self.add_message(
                'invalid-monolith-import',
                line=node.lineno,
                node=node,
                args=(parent_basename, imported_module.name)
            )

def get_basename(modname: str) -> str:
    if modname.startswith('.'):
        return '.' + modname.split('.')[1]
    return modname.split('.')[0]

def _get_imported_module(importnode: astroid.nodes.ImportFrom, modname: str) -> Optional[astroid.nodes.Module]:
    try:
        return importnode.do_import_module(modname)
    except astroid.TooManyLevelsError:
        return None
    except astroid.AstroidBuildingException:
        return None
