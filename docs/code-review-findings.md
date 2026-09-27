# Code review findings (`/code-review max` on PRs #1–#5)

Tracking doc in place of GitHub Issues (disabled on this repository). Findings 1–3 were fixed in PR #6. Findings 4–10 are fixed by the commit that updates this file. Findings 11–13 are still open.

## Fixed

1. **`supply_chain_logistics_multi_agent.py` crashes with Gemini: missing `as_text()` normalizer**
   `route_to_specialist()` (line 265) and `actor_node()` (line 299) treated `.content` as a plain string.
   Gemini returns `AIMessage.content` as a list of content blocks, so this crashed with
   `AttributeError: 'list' object has no attribute 'strip'` (confirmed by live execution) before any
   specialist could run. Fixed by applying the same `as_text()` normalizer already used in the
   ray/redis/temporal sibling files.

2. **`uv.lock` not regenerated after adding `langchain-google-genai`**
   `pyproject.toml` declares `langchain-google-genai>=2.0.0` but the lockfile was never updated, so
   `uv sync --locked`/`--frozen` (typical CI) fails outright. Fixed by regenerating `uv.lock`.

3. **Ray/Temporal specialist actors always take the tool-call branch**
   `SpecialistActor.process_task` (`ray_supply_chain_multi_agent.py:203`) and the equivalent in
   `temporal_supply_chain_multi_agent.py` used `hasattr(first, "tool_calls")`, which is always `True`
   on an `AIMessage` even when `tool_calls == []`. This silently doubled LLM calls on every plain
   (non-tool-call) response. Fixed by switching to `getattr(first, "tool_calls", None)`, matching every
   other file in the codebase.

4. **`as_text()` hand-reimplemented `BaseMessage.text`** — removed the duplicated helper from all 4
   supply chain files (ray, redis, temporal, and the logistics multi-agent file) and switched every call
   site to the built-in `msg.text` property (`langchain_core.messages.base.BaseMessage.text`), which does
   the same content-block normalization.
5. **`build_llm()` duplicated near-verbatim across 19 files** — added `src/common/llm.py::build_chat_model()`
   as the one place that picks OpenAI vs. Gemini from `LLM_PROVIDER`. Every one of the 19 files' `build_llm()`
   is now a thin wrapper that calls it (`return build_chat_model().bind_tools(TOOLS)`, or just
   `return build_chat_model()` for the 4 multi-agent files that bind tools per-role in their callers).
6. **Temporal rebuilt the specialist LLM on every activity call** — `specialist_activity` now keeps a
   module-level `_specialist_llm_cache: Dict[str, Any]` keyed by `agent_name` and only calls `build_llm()`
   the first time a given specialist runs in that worker process; retries and subsequent calls reuse the
   cached client.
7. **Startup guard never validated `GOOGLE_API_KEY`** — `ch09/agents/customer_support_agent.py`'s guard now
   also raises `ValueError("GOOGLE_API_KEY is not set")` when `LLM_PROVIDER=gemini` and the key is missing.
8. **Gemini branch missing `callbacks`/`verbose`** — fixed as part of #5: `build_chat_model()` sets
   `callbacks=[StreamingStdOutCallbackHandler()], verbose=True` on both branches, so this is now
   structurally impossible to reintroduce per-file.
9. **Temporal's `to_message()` silently defaulted unknown types to `HumanMessage`** — it now raises
   `ValueError` when a message dict's `"type"` isn't one of `human`/`ai`/`system`/`tool`, instead of
   silently misreconstructing it (and dropping fields like `tool_calls` in the process).
10. **`supply_chain_logistics_agent.py` hand-instantiated `ChatGoogleGenerativeAI`** — fixed as part of #5:
    `build_chat_model()` routes both providers through `init_chat_model()` (`model_provider="google_genai"`
    for Gemini), so this file's Gemini branch now goes through the same factory as its OpenAI branch.

## Open follow-ups

11. Temporal's `supervisor_activity`/`specialist_activity` call blocking, synchronous `.invoke()` with
    no `asyncio.to_thread`/executor offload, risking event-loop stalls under concurrency.
12. `LLM_PROVIDER` is read and lower-cased independently in two places in the same file (startup guard
    and `build_llm()`), instead of computed once. (Reading it once per `build_chat_model()` call is no
    longer duplicated *within* each of the 19 call-site files after #5/#8/#10 — this is now scoped to
    files, like `customer_support_agent.py`, that also read it in their own startup guard.)
13. Two different idioms reconstruct a `BaseMessage` from a dict: `to_message()`/`_MESSAGE_TYPES` in the
    temporal file vs. a ternary chain (`deserialize_messages()`) in the redis file.
