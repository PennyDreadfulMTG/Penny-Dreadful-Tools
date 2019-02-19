"""
Checker for non-awaited async function calls.
https://gist.github.com/matangover/5e95be78f95e340aae9c4071f0d2834f
"""

import astroid
from pylint.checkers import BaseChecker, utils
from pylint.interfaces import IAstroidChecker


def register(linter):
    linter.register_checker(AsyncAwaitChecker(linter))


class AsyncAwaitChecker(BaseChecker):
    """
    Checks that every async function (or method) call is awaited.
    Example:
        async def my_func():
            await do_something()
        def bad_func():
            # Not awaiting the bad_func!
            my_func()
    The message id is `non-awaited-async`.
    """

    __implements__ = IAstroidChecker

    name = 'async-await-checker'

    MESSAGE_ID = 'non-awaited-async'
    msgs = {
        'E8000': (
            'async function %s() must be awaited',
            MESSAGE_ID,
            'async functions must be awaited',
        ),
    }

    # pylint: disable=protected-access
    @utils.check_messages(MESSAGE_ID)
    def visit_callfunc(self, node):
        """Called for every function call in the source code."""
        if not self.linter.is_message_enabled(self.MESSAGE_ID):
            return

        func_def = utils.safe_infer(node.func)
        if isinstance(func_def, astroid.BoundMethod):
            func_def = func_def._proxied
        if isinstance(func_def, astroid.UnboundMethod):
            func_def = func_def._proxied
        if isinstance(func_def, astroid.AsyncFunctionDef):
            if not isinstance(node.parent, astroid.Await):
                self.add_message(self.MESSAGE_ID, args=func_def.name, node=node)
