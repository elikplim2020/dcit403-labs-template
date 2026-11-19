"""Lab 2 - the agent's actuators.

Two tools, both taking one line of text and returning one block of text, because
in the ReAct text protocol the result goes straight back into the conversation as
an ``Observation:`` line.

* ``calculator``  - evaluates arithmetic with ``ast`` and never calls ``eval``.
* ``wiki_lookup`` - returns the Wikipedia summary extract for a title.

Run this file directly for the Step 2 checkpoint (both tools tested on their own,
without the model)::

    python tools.py
"""

from __future__ import annotations

import ast
import difflib
import json
import operator as op
import time
import urllib.error
import urllib.parse
import urllib.request

try:  # requests is in requirements.txt; the stdlib fallback keeps tools usable
    import requests  # type: ignore
except ImportError:  # pragma: no cover - exercised only on minimal Python installs
    requests = None


# --------------------------------------------------------------------------- #
# Calculator
# --------------------------------------------------------------------------- #

# Whitelist of the only node types the evaluator will execute.
OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.USub: op.neg,
}

MAX_EXPRESSION_CHARS = 120


def _eval(node: ast.AST):
    """Walk one parsed arithmetic expression and return its numeric value."""
    if isinstance(node, ast.Constant):
        # bool is a subclass of int, and True + 1 is not something we accept.
        if type(node.value) in (int, float):
            return node.value
        raise ValueError("only numbers are supported")
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.operand))
    raise ValueError("Unsupported expression")


def _format_number(value) -> str:
    """Show whole results without a trailing ``.0`` (190.0 -> 190, 175 -> 175)."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def calculator(expression: str) -> str:
    """Evaluate a short arithmetic expression and return the result as text.

    ``eval`` is never used: the expression is parsed with :mod:`ast` and only the
    node types in ``OPS`` are executed, so a string such as
    ``__import__('os').system('dir')`` raises ``ValueError`` instead of running.
    Errors are returned as text, never raised, because a crash inside a tool would
    kill the agent loop.
    """
    if not isinstance(expression, str) or not expression.strip():
        return "Error: empty expression"
    if len(expression) > MAX_EXPRESSION_CHARS:
        return f"Error: expression longer than {MAX_EXPRESSION_CHARS} characters"
    try:
        # A trader writes 1,200 and "1200 - 1,025"; commas are thousands marks.
        expr = expression.replace(",", "").strip()
        value = _eval(ast.parse(expr, mode="eval").body)
    except SyntaxError:
        return "Error: that is not a valid arithmetic expression"
    except ZeroDivisionError:
        return "Error: division by zero"
    except Exception as exc:  # noqa: BLE001 - the agent must always get text back
        return f"Error: {exc}"
    return _format_number(value)


# --------------------------------------------------------------------------- #
# Wikipedia lookup
# --------------------------------------------------------------------------- #

WIKI_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/"
USER_AGENT = "DCIT403-lab02-react-agent/1.0 (student lab; contact: course facilitator)"
MAX_WIKI_CHARS = 800


def _http_get_json(url: str, timeout: int = 10) -> tuple[int, dict]:
    """GET ``url`` and return ``(status, parsed_json)``; raises on network failure."""
    if requests is not None:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
        status = resp.status_code
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        return status, payload

    # stdlib fallback, used when requests is not installed.
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # 404 is an answer, not a crash
        return exc.code, {}


def wiki_lookup(title: str) -> str:
    """Return the opening of the Wikipedia summary for ``title``, or a clear message.

    The model supplies a human title ("Bono East Region"); spaces become
    underscores and the text is URL-encoded before the request. A missing page is
    reported in words the model can pass on, so it can finish gracefully instead of
    inventing a fact.
    """
    title = (title or "").strip().strip('"').strip("'").strip()
    if not title:
        return "Error: empty title"

    slug = urllib.parse.quote(title.replace(" ", "_"), safe="")
    status, payload, error = None, {}, None
    for attempt in range(2):  # one retry: university networks drop single requests
        try:
            status, payload = _http_get_json(WIKI_URL + slug)
            break
        except Exception as exc:  # noqa: BLE001 - offline is a lab condition, not a crash
            error = exc
            if attempt == 0:
                time.sleep(1.0)
    if status is None:
        return f"Error: could not reach Wikipedia ({type(error).__name__}: {error})."

    if status == 404:
        return f"No Wikipedia page found for '{title}'."
    if status != 200:
        return f"Error: Wikipedia returned HTTP {status} for '{title}'."

    extract = (payload or {}).get("extract", "").strip()
    if not extract:
        return f"No summary available for '{title}'."
    if len(extract) > MAX_WIKI_CHARS:
        # Cut on a word boundary so the model does not receive half a word.
        extract = extract[:MAX_WIKI_CHARS].rsplit(" ", 1)[0] + "..."
    return extract


# --------------------------------------------------------------------------- #
# Tool registry - what the loop and the prompt both read
# --------------------------------------------------------------------------- #

TOOLS = {
    "calculator": calculator,
    "wiki_lookup": wiki_lookup,
}

TOOL_HELP = {
    "calculator": "evaluates one arithmetic expression, e.g. 4*185 + 3*95",
    "wiki_lookup": "returns the Wikipedia summary for a title, e.g. Bono East Region",
}


def run_tool(name: str, argument: str) -> str:
    """Run one tool by name and return its text result.

    An unknown tool name is a normal event in a text protocol: the model wrote a
    word that is not in the registry. It returns a corrective message (with the
    nearest name, when there is one) instead of raising, so the loop survives.
    """
    key = (name or "").strip()
    if key not in TOOLS:
        known = ", ".join(sorted(TOOLS))
        close = difflib.get_close_matches(key.lower(), list(TOOLS), n=1, cutoff=0.6)
        hint = f" Did you mean '{close[0]}'?" if close else ""
        return (
            f"Error: unknown tool '{key}'.{hint} "
            f"Available tools: {known}. Use exactly one of these names, or finish."
        )
    try:
        return TOOLS[key](argument)
    except Exception as exc:  # noqa: BLE001 - a tool must never break the loop
        return f"Error: {key} failed ({type(exc).__name__}: {exc})"


if __name__ == "__main__":
    # Step 2 checkpoint: prove both tools work when called directly, and that the
    # calculator refuses code instead of executing it.
    checks = [
        ("4*185 + 3*95", "1025"),
        ("1200 - 1025", "175"),
        ("1140/6", "190"),
        ("1,200 - 1,025", "175"),
        ("__import__('os').system('dir')", "Error"),
        ("2 ** 10", "Error"),  # ** is not in the whitelist, on purpose
        ("1/0", "Error"),
    ]
    print("calculator")
    for expr, expected in checks:
        got = calculator(expr)
        ok = got == expected or (expected == "Error" and got.startswith("Error"))
        print(f"  {'OK ' if ok else 'FAIL'} {expr!r:38} -> {got}")

    print("\nwiki_lookup")
    for title in ("Bono East Region", "Zxqv Market Traders Association of Ghana"):
        result = wiki_lookup(title)
        print(f"  {title!r} -> {result[:110]}{'...' if len(result) > 110 else ''}")

    print("\nrun_tool (unknown name)")
    print(" ", run_tool("Calculator", "1+1"))
