import ast
import operator
from typing import Callable, Dict

from langchain_core.tools import tool


_ALLOWED_BIN_OPS: Dict[type, Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}

_ALLOWED_UNARY_OPS: Dict[type, Callable[[float], float]] = {
    ast.UAdd: lambda value: value,
    ast.USub: operator.neg,
}


def _safe_eval_math(expr: str) -> float:
    parsed = ast.parse(expr, mode="eval")

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BIN_OPS:
            return _ALLOWED_BIN_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY_OPS:
            return _ALLOWED_UNARY_OPS[type(node.op)](_eval(node.operand))
        raise ValueError("Only numeric math expressions are supported.")

    return _eval(parsed)


@tool
def calculator(expression: str) -> str:
    """Evaluate a numeric math expression (supports +, -, *, /, %, **, parentheses)."""
    try:
        result = _safe_eval_math(expression)
        if result.is_integer():
            return str(int(result))
        return str(result)
    except Exception as exc:
        return f"Error: {exc}"
