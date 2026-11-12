"""Test helpers: fake LLMs and a one-call way to run a question through the pipeline."""
import asyncio


def fake_llm(cite="[1]"):
    """Echoes the start of source [1] followed by the given citation."""
    async def _stream(messages):
        src = messages[1]["content"].split("\n")[2]          # body text of source [1]
        for w in f"{src[:80]} {cite}".split(" "):
            yield w + " "
        yield {"prompt_tokens": 10, "completion_tokens": 5, "cost_usd": 0.0}
    return _stream


async def no_llm(_messages):
    raise AssertionError("LLM must not be called")
    yield


def ask(rag, customer, q):
    """Run one question through the pipeline and return the final event."""
    async def go():
        return [ev async for ev in rag.answer_stream(customer, q)][-1]
    return asyncio.run(go())
