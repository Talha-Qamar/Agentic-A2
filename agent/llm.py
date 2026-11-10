"""LLM access for every node: config-routed model, bounded retries, fallback model, metering.

    out = await complete_json("analyst", system, user, JobSpecOut)

* the node name selects the tier and model from agent/config.yaml (never from code);
* JSON is validated with Pydantic; one repair attempt with the validation error;
* transient errors retry with exponential backoff, then the node's fallback model is tried;
* every call is metered (tokens, latency, USD) into the active Meter and the trace.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from . import settings
from .tracing import LLMCall, record, span

T = TypeVar("T", bound=BaseModel)
_clients: dict[str, object] = {}


class LLMError(RuntimeError):
    pass


def _client(provider: str):
    if provider in _clients:
        return _clients[provider]
    from openai import AsyncOpenAI
    p = settings.get(f"providers.{provider}")
    key = os.environ.get(p["api_key_env"], "") if p.get("api_key_env") else "ollama"
    if not key:
        raise LLMError(f"missing API key env {p['api_key_env']} for provider {provider}")
    c = AsyncOpenAI(base_url=p["base_url"], api_key=key, timeout=settings.get("llm.request_timeout_s", 60), max_retries=0)
    _clients[provider] = c
    return c


def _cost(model: str, tin: int, tout: int) -> float:
    pr = settings.price(model)
    return round(tin / 1e6 * pr["input"] + tout / 1e6 * pr["output"], 8)


async def _call(node: str, spec: dict, messages: list[dict], json_mode: bool, max_tokens: int | None,
                temperature: float | None) -> tuple[str, int, int]:
    if spec["provider"] == "stub":
        from .stub_llm import stub_complete
        text = stub_complete(node, messages)
        return text, sum(len(m["content"]) // 4 for m in messages), len(text) // 4
    client = _client(spec["provider"])
    msgs = [dict(m) for m in messages]
    if spec.get("think") is False and msgs and msgs[0]["role"] == "system":
        msgs[0]["content"] += "\n/no_think"
    kwargs: dict = dict(model=spec["model"], messages=msgs,
                        temperature=settings.get("llm.temperature", 0.2) if temperature is None else temperature,
                        max_tokens=max_tokens or settings.get("llm.max_output_tokens", 1200))
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if spec.get("reasoning_effort"):
        kwargs["reasoning_effort"] = spec["reasoning_effort"]
    resp = await client.chat.completions.create(**kwargs)
    text = resp.choices[0].message.content or ""
    u = resp.usage
    return text, (u.prompt_tokens if u else 0), (u.completion_tokens if u else 0)


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def parse_json(text: str) -> dict:
    t = _strip_think(text)
    t = re.sub(r"^```(?:json)?|```$", "", t.strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


async def complete(node: str, system: str, user: str, *, json_mode: bool = False, max_tokens: int | None = None,
                   temperature: float | None = None) -> str:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    last_err: Exception | None = None
    for use_fallback in (False, True):
        spec = settings.model_for(node, fallback=use_fallback)
        retries = settings.get("llm.max_retries", 2)
        for attempt in range(retries + 1):
            t0 = time.perf_counter()
            try:
                with span(f"llm.{node}", {"llm.model": spec["model"], "llm.provider": spec["provider"],
                                          "llm.fallback": use_fallback}) as s:
                    text, tin, tout = await _call(node, spec, messages, json_mode, max_tokens, temperature)
                    if s is not None:
                        s.set_attribute("llm.token_count.prompt", tin)
                        s.set_attribute("llm.token_count.completion", tout)
                        s.set_attribute("llm.cost_usd", _cost(spec["model"], tin, tout))
                record(LLMCall(node, spec["provider"], spec["model"], tin, tout, round(time.perf_counter() - t0, 3),
                               _cost(spec["model"], tin, tout), fallback=use_fallback))
                return text
            except Exception as e:  # noqa: BLE001
                last_err = e
                status = getattr(e, "status_code", None)
                record(LLMCall(node, spec["provider"], spec["model"], 0, 0, round(time.perf_counter() - t0, 3), 0.0,
                               fallback=use_fallback, error=f"{type(e).__name__}: {str(e)[:120]}"))
                if status in (400, 401, 403, 404):
                    break  # not transient: go to fallback model
                wait = settings.get("llm.backoff_base_s", 2.0) * (2 ** attempt)
                if status == 429:
                    wait = max(wait, 8.0)
                await asyncio.sleep(min(wait, 30))
    raise LLMError(f"{node}: all models failed: {last_err}")


async def complete_json(node: str, system: str, user: str, schema: type[T], *, max_tokens: int | None = None) -> T:
    sys_prompt = system + "\n\nReturn ONLY a JSON object matching this JSON schema:\n" + json.dumps(
        schema.model_json_schema(), separators=(",", ":"))
    text = await complete(node, sys_prompt, user, json_mode=True, max_tokens=max_tokens)
    try:
        return schema.model_validate(parse_json(text))
    except (ValidationError, json.JSONDecodeError, ValueError) as e:
        repair = (user + "\n\nYour previous answer was invalid JSON for the schema. Error:\n" + str(e)[:800] +
                  "\nPrevious answer:\n" + text[:1500] + "\nReturn a corrected JSON object only.")
        text2 = await complete(node, sys_prompt, repair, json_mode=True, max_tokens=max_tokens)
        return schema.model_validate(parse_json(text2))


def load_prompt(name: str) -> str:
    """Prompts live in agent/prompts/<name>.md (versioned; no inline prompts in code)."""
    p = settings.ROOT / "agent" / "prompts" / f"{name}.md"
    text = p.read_text()
    return re.sub(r"^<!--.*?-->\s*", "", text, flags=re.S)
