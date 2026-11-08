from langchain_openai import ChatOpenAI

from app.config import settings


def get_llm(thinking: bool = False, max_tokens: int = 800) -> ChatOpenAI:
    """Chat model on the local OpenAI-compatible server.

    ``thinking`` toggles Qwen's reasoning mode via the llama.cpp chat-template kwarg. Thinking-off is
    ~30-80x faster and fine for short structured calls; thinking-on is more accurate for synthesis.
    """
    return ChatOpenAI(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.openai_api_key,
        temperature=0,
        max_tokens=max_tokens,
        timeout=settings.llm_timeout,
        max_retries=1,
        extra_body={"chat_template_kwargs": {"enable_thinking": thinking}},
    )


def memo_uses_openrouter() -> bool:
    return bool(settings.openrouter_key)


def get_memo_llm(max_tokens: int) -> ChatOpenAI:
    """Model for the final memo: OpenRouter when a key is configured, otherwise the local model."""
    if not memo_uses_openrouter():
        return get_llm(thinking=settings.synth_thinking, max_tokens=max_tokens)
    return ChatOpenAI(
        model=settings.memo_model,
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_key,
        temperature=0,
        max_tokens=max_tokens,
        timeout=settings.memo_timeout,
        max_retries=1,
        default_headers={"X-Title": "FinSentinel"},
    )
