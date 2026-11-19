"""A minimal Groq client, used only when LiteLLM cannot be installed.

The lab code calls models through LiteLLM (`requirements.txt`, and the Codespace
has it). This module implements the same tiny interface - ``model_fn(messages) ->
(text, usage)`` - against Groq's OpenAI-compatible endpoint, so the loop, the parser
and the tools can be exercised on a machine where LiteLLM is unavailable. Nothing in
``react_agent.py`` changes: it receives a ``model_fn`` either way.

The model name is the part after ``groq/`` in ``LLM_MODEL``: LiteLLM's
``groq/openai/gpt-oss-20b`` is Groq's ``openai/gpt-oss-20b``.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
DEFAULT_STOP = ["Observation:"]
RETRY_PAUSES = (2, 4, 8)


def groq_model_name(model: str | None = None) -> str:
    """Turn a LiteLLM model string (``groq/openai/gpt-oss-20b``) into a Groq id."""
    name = model or os.getenv("LLM_MODEL") or f"groq/{DEFAULT_GROQ_MODEL}"
    return name.split("/", 1)[1] if name.startswith("groq/") else DEFAULT_GROQ_MODEL


def make_groq_model(
    model: str | None = None,
    *,
    verbose: bool = False,
    temperature: float = 0.0,
    stop: list[str] | None = None,
    timeout: int = 60,
):
    """Return a ``model_fn`` that calls Groq, with the same retry rule as the lab."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Export it, or run with --scripted for a rehearsal."
        )
    model_name = groq_model_name(model)
    stop_sequences = DEFAULT_STOP if stop is None else stop

    def model_fn(messages):
        body = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
        }
        if stop_sequences:
            body["stop"] = stop_sequences
        request = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "DCIT403-lab02-react-agent/1.0",
            },
            method="POST",
        )
        last_error = None
        for attempt, pause in enumerate((0, *RETRY_PAUSES)):
            if pause:
                if verbose:
                    print(f"    [rate limit] waiting {pause}s and retrying")
                time.sleep(pause)
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                    payload = json.loads(response.read().decode("utf-8"))
                text = (payload["choices"][0]["message"].get("content") or "").strip()
                usage = payload.get("usage") or {}
                counts = (
                    int(usage.get("prompt_tokens", 0) or 0),
                    int(usage.get("completion_tokens", 0) or 0),
                )
                if verbose:
                    print(f"    [groq:{model_name}] {counts[0]}+{counts[1]} tokens")
                return text, counts
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:300]
                last_error = RuntimeError(f"HTTP {exc.code}: {detail}")
                if exc.code not in (429, 500, 502, 503, 504):
                    raise last_error from exc
            except Exception as exc:  # noqa: BLE001 - network drop, try again
                last_error = exc
            if attempt == len(RETRY_PAUSES):
                break
        raise last_error if last_error else RuntimeError("Groq call failed")

    model_fn.model_name = f"groq/{model_name}"  # type: ignore[attr-defined]
    return model_fn
