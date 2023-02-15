"""
Implicit does the same as explicit but internally it doesn't compute the values itself.
Instead it only checks if the give expression is a valid mathematical expression and then just evals it.
"""
import ast
from numbers import Number


def calc(expr: str):
    if is_valid(ast.parse(expr, mode="eval").body):
        return eval(expr)
    raise SyntaxError


valid_ops = {ast.Add, ast.Sub, ast.Div, ast.Mult, ast.UAdd, ast.USub}


def is_valid(expr) -> bool:
    match expr:
        case ast.Constant(value=value):
            return isinstance(value, Number)
        case ast.UnaryOp(op=op, operand=value):
            return type(op) in valid_ops and is_valid(value)
        case ast.BinOp(op=op, left=left, right=right):
            return type(op) in valid_ops and is_valid(left) and is_valid(right)
        case _:
            return False