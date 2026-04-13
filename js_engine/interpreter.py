"""Very small JavaScript interpreter implementation."""

from __future__ import annotations

import ast
import re
from typing import Any, Dict, List

from security.sandbox import Sandbox
from utils.logger import get_logger


class JavaScriptRuntimeError(RuntimeError):
    """Raised for interpreter errors."""


class JavaScriptInterpreter:
    """Interpret a small subset of JavaScript."""

    def __init__(self, sandbox: Sandbox | None = None) -> None:
        """Initialize runtime environment."""

        self.sandbox = sandbox or Sandbox()
        self.variables: Dict[str, Any] = {}
        self.logger = get_logger("js_engine.interpreter")

    def execute(self, source: str) -> List[str]:
        """Execute script and return console output lines."""

        output: List[str] = []
        statements = self._split_statements(source)
        for statement in statements:
            self._execute_statement(statement.strip(), output)
        return output

    def _split_statements(self, source: str) -> List[str]:
        """Split source into top-level statements including if/else blocks."""

        statements: List[str] = []
        buffer: List[str] = []
        brace_depth = 0
        for char in source:
            buffer.append(char)
            if char == "{":
                brace_depth += 1
            elif char == "}":
                brace_depth -= 1
            elif char == ";" and brace_depth == 0:
                statements.append("".join(buffer).strip())
                buffer = []
        if "".join(buffer).strip():
            statements.append("".join(buffer).strip())
        return statements

    def _execute_statement(self, statement: str, output: List[str]) -> None:
        """Execute one JS statement."""

        if not statement:
            return

        if statement.startswith("if"):
            self._execute_if_else(statement, output)
            return

        if statement.startswith("console.log"):
            payload = self._extract_call_arg(statement)
            value = self._eval_expression(payload)
            output.append(str(value))
            self.logger.info("console.log: %s", value)
            return

        declaration_match = re.match(r"^(?:var|let|const)\s+([A-Za-z_][\w]*)\s*=\s*(.+);?$", statement)
        if declaration_match:
            var_name = declaration_match.group(1)
            expression = declaration_match.group(2).rstrip(";")
            self.variables[var_name] = self._eval_expression(expression)
            return

        assignment_match = re.match(r"^([A-Za-z_][\w]*)\s*=\s*(.+);?$", statement)
        if assignment_match:
            var_name = assignment_match.group(1)
            expression = assignment_match.group(2).rstrip(";")
            if var_name not in self.variables:
                raise JavaScriptRuntimeError(f"Unknown variable: {var_name}")
            self.variables[var_name] = self._eval_expression(expression)
            return

        self._eval_expression(statement.rstrip(";"))

    def _execute_if_else(self, statement: str, output: List[str]) -> None:
        """Execute simple if/else block syntax."""

        match = re.match(
            r"^if\s*\((.*?)\)\s*\{(.*?)\}(?:\s*else\s*\{(.*?)\})?;?$",
            statement,
            flags=re.S,
        )
        if not match:
            raise JavaScriptRuntimeError("Malformed if/else statement")

        condition_expr, true_block, false_block = match.group(1), match.group(2), match.group(3)
        if self._truthy(self._eval_expression(condition_expr)):
            for inner in self._split_statements(true_block):
                self._execute_statement(inner.strip(), output)
        elif false_block is not None:
            for inner in self._split_statements(false_block):
                self._execute_statement(inner.strip(), output)

    def _extract_call_arg(self, statement: str) -> str:
        """Extract function call argument text inside parentheses."""

        start = statement.find("(")
        end = statement.rfind(")")
        if start == -1 or end == -1 or end <= start:
            raise JavaScriptRuntimeError("Malformed function call")
        return statement[start + 1 : end]

    def _eval_expression(self, expression: str) -> Any:
        """Safely evaluate arithmetic and comparison expressions."""

        expression = expression.strip()
        try:
            node = ast.parse(expression, mode="eval")
        except SyntaxError as error:
            raise JavaScriptRuntimeError(f"Invalid expression: {expression}") from error

        return self._eval_ast(node.body)

    def _eval_ast(self, node: ast.AST) -> Any:
        """Recursively evaluate a restricted AST subset."""

        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            if node.id in self.variables:
                return self.variables[node.id]
            raise JavaScriptRuntimeError(f"Undefined symbol: {node.id}")

        if isinstance(node, ast.BinOp):
            left = self._eval_ast(node.left)
            right = self._eval_ast(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            raise JavaScriptRuntimeError("Unsupported binary operator")

        if isinstance(node, ast.Compare) and len(node.ops) == 1 and len(node.comparators) == 1:
            left = self._eval_ast(node.left)
            right = self._eval_ast(node.comparators[0])
            op = node.ops[0]
            if isinstance(op, ast.Eq):
                return left == right
            if isinstance(op, ast.NotEq):
                return left != right
            if isinstance(op, ast.Lt):
                return left < right
            if isinstance(op, ast.LtE):
                return left <= right
            if isinstance(op, ast.Gt):
                return left > right
            if isinstance(op, ast.GtE):
                return left >= right
            raise JavaScriptRuntimeError("Unsupported comparator")

        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -self._eval_ast(node.operand)

        raise JavaScriptRuntimeError("Unsupported expression")

    def _truthy(self, value: Any) -> bool:
        """Apply JavaScript-like truthy evaluation for basic types."""

        return bool(value)
