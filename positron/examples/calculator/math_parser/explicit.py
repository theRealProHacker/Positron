"""
Explicitly calculates valid mathematical expressions (using "+-*/" and brackets)
"""

import ast
from numbers import Number
import operator


class MathParserException(SyntaxError):
    pass


def calc(expr: str) -> Number:
    return compute(ast.parse(expr, mode="eval").body)


_op_map = {
    # binary
    ast.Add: operator.__add__,
    ast.Sub: operator.__sub__,
    ast.Div: operator.__truediv__,
    ast.Mult: operator.__mul__,
    # unary
    ast.UAdd: operator.__pos__,
    ast.USub: operator.__neg__,
}


def compute(expr) -> Number:
    match expr:
        case ast.Constant(value=value):
            if not isinstance(value, Number):
                raise MathParserException(
                    f"Not a number {value!r} in {ast.unparse(expr)}"
                )
            return value
        case ast.UnaryOp(op=op, operand=value):
            try:
                return _op_map[type(op)](compute(value))  # type: ignore
            except KeyError:
                raise MathParserException(f"Unknown operation {ast.unparse(expr)}")
        case ast.BinOp(op=op, left=left, right=right):
            try:
                return _op_map[type(op)](compute(left), compute(right))  # type: ignore
            except KeyError:
                raise MathParserException(f"Unknown operation {ast.unparse(expr)}")
        case x:
            raise MathParserException(f"Invalid Node {ast.dump(x)}")
