# Code review findings (`/code-review max` on PRs #1–#5)

Tracking doc in place of GitHub Issues (disabled on this repository). Findings 1–3 are real bugs and are fixed by the commit that adds this file. The rest are open follow-ups.

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

## Open follow-ups

4. `as_text()` hand-reimplements langchain_core's own `BaseMessage.text`, duplicated across 3 files
   (ray, redis, temporal supply chain agents) instead of using the built-in property.
5. `build_llm()` is duplicated near-verbatim across ~19 files instead of a shared helper in `src/common/`.
6. Temporal's `specialist_activity` rebuilds a new LLM client on every activity call/retry instead of
   caching it once per worker process (~85ms wasted per call for `ChatGoogleGenerativeAI`).
7. `ch09/agents/customer_support_agent.py`'s startup guard only validates `OPENAI_API_KEY`, never
   `GOOGLE_API_KEY` when `LLM_PROVIDER=gemini`.
8. `build_llm()`'s Gemini branch omits `callbacks=[StreamingStdOutCallbackHandler()]` and `verbose=True`
   that the OpenAI branch sets, so streaming/verbose behavior silently differs by provider.
9. Temporal's `to_message()` silently reconstructs any dict with an unrecognized `"type"` as a
   `HumanMessage` instead of raising, which can silently drop `tool_calls` from a mistyped message.
10. `ch09/agents/supply_chain_logistics_agent.py`'s Gemini branch hand-instantiates
    `ChatGoogleGenerativeAI` instead of extending the `init_chat_model()` factory already used for
    the OpenAI branch.
11. Temporal's `supervisor_activity`/`specialist_activity` call blocking, synchronous `.invoke()` with
    no `asyncio.to_thread`/executor offload, risking event-loop stalls under concurrency.
12. `LLM_PROVIDER` is read and lower-cased independently in two places in the same file (startup guard
    and `build_llm()`), instead of computed once.
13. Two different idioms reconstruct a `BaseMessage` from a dict: `to_message()`/`_MESSAGE_TYPES` in the
    temporal file vs. a ternary chain (`deserialize_messages()`) in the redis file.
