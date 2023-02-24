"""
A console application

`Console()` returns a `Task`. When that is run, user input can be taken asynchronously while other code is running.
This console acts as an interpreter and evals the expression, printing the result.

However, the console will only work if DEBUG mode is turned on and the dependency `aioconsole` can be imported.
If not `Console()` will just return a `sleep(0)` task.
"""
import asyncio

import positron.config as config

uses_aioconsole = config.DEBUG
if uses_aioconsole:
    try:
        import aioconsole
    except ImportError:
        uses_aioconsole = False

from positron.J import SingleJ, J
import positron.utils as util


def e(q: str):
    """
    Helper for console: Try `e("p")` and you will get the first p element
    """
    return SingleJ(q)._elem


async def _Console(context):
    """
    The Console takes input asynchronously and executes it. For debugging purposes only
    """
    while True:
        try:
            __x_______ = await aioconsole.ainput(">>> ")
            print("Thing:", repr(bytes(__x_______, encoding="ascii")))
            args = [__x_______, globals(), context]
            try:
                r = eval(*args)
                if r is not None:
                    print(r)
            except SyntaxError:
                exec(*args)
        except asyncio.exceptions.CancelledError:
            break
        except Exception as e:
            print("Console error:", e, e.args)


def Console(context):
    """
    This gives an actual _Console in DEBUG mode else it gives a fake console task
    """
    return util.create_task(_Console(context) if uses_aioconsole else asyncio.sleep(0))


__all__ = ["Console"]
