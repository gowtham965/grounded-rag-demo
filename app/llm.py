"""Streaming call to the chat model through LiteLLM (any provider). Replaced by a fake in tests."""
from .config import settings


async def llm_stream(messages):
    """Yields text deltas, then one final dict: {prompt_tokens, completion_tokens, cost_usd}."""
    import litellm
    if not settings.chat_model:
        raise RuntimeError("Set CHAT_MODEL in .env")
    resp = await litellm.acompletion(
        model=settings.chat_model, messages=messages, stream=True, temperature=0,
        max_tokens=settings.max_answer_tokens, stream_options={"include_usage": True},
    )
    usage = None
    async for chunk in resp:
        if getattr(chunk, "usage", None):
            usage = chunk.usage
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
    pt = getattr(usage, "prompt_tokens", 0) or 0
    ct = getattr(usage, "completion_tokens", 0) or 0
    try:
        p, c = litellm.cost_per_token(model=settings.chat_model, prompt_tokens=pt, completion_tokens=ct)
        cost = p + c
    except Exception:   # unknown model price -> log cost as NULL rather than fail the answer
        cost = None
    yield {"prompt_tokens": pt, "completion_tokens": ct, "cost_usd": cost}
