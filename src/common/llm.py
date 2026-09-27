"""Shared chat-model construction for LLM_PROVIDER-aware agents.

Every agent in this repo picks OpenAI or Gemini from the same env var and
wants the same callbacks/verbose behavior regardless of provider. This
module is the one place that decision lives.
"""

import os

from langchain.chat_models import init_chat_model
from langchain_core.callbacks.streaming_stdout import StreamingStdOutCallbackHandler


def build_chat_model(
    *,
    provider: str | None = None,
    openai_model: str = "gpt-4o",
    gemini_model_env: str = "GEMINI_MODEL",
    gemini_model_default: str = "gemini-flash-latest",
    temperature: float = 0.0,
):
    """Build the chat model per LLM_PROVIDER (env var, default "openai").

    Both branches go through init_chat_model and get the same
    callbacks/verbose treatment, so streaming and logging behavior no
    longer silently differs by provider.

    Pass `provider` when the caller already read/lower-cased LLM_PROVIDER
    itself (e.g. for a startup guard) so it isn't computed twice.
    """
    if provider is None:
        provider = os.getenv("LLM_PROVIDER", "openai").lower()
    callbacks = [StreamingStdOutCallbackHandler()]
    if provider == "gemini":
        return init_chat_model(
            model=os.getenv(gemini_model_env, gemini_model_default),
            model_provider="google_genai",
            temperature=temperature,
            callbacks=callbacks,
            verbose=True,
        )
    return init_chat_model(
        model=openai_model,
        temperature=temperature,
        callbacks=callbacks,
        verbose=True,
    )
