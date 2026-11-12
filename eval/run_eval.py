"""Grounding eval. Runs every question through the real pipeline and scores:

  correctness        answer contains the expected facts (must_contain, case-insensitive)
  citation accuracy  a correct answer cites the expected document/record
  refusal accuracy   out-of-scope and held-back questions get the fixed refusal message
  latency            time to first token

Usage: python -m eval.run_eval [--judge]   (--judge also asks the LLM whether each cited
excerpt really supports the answer, as a second, stricter grounding check)
Writes eval/report.md.
"""
import argparse
import asyncio
import json
import statistics
from pathlib import Path

from app import db
from app.rag import answer_stream

HERE = Path(__file__).parent


async def run_one(q):
    final = None
    async for ev in answer_stream(q["customer"], q["question"], user_id="eval"):
        if ev["type"] == "final":
            final = ev
    return final


async def judge(answer, sources):
    import litellm
    from app.config import settings
    ctx = "\n".join(f"- {s['label']}: {s['excerpt']}" for s in sources)
    r = await litellm.acompletion(model=settings.chat_model, temperature=0, max_tokens=5, messages=[{
        "role": "user", "content": f"Excerpts:\n{ctx}\n\nAnswer:\n{answer}\n\nIs every claim in the answer "
        "supported by the excerpts? Reply only YES or NO."}])
    return r.choices[0].message.content.strip().upper().startswith("YES")


async def main(use_judge):
    db.init()
    qs = json.loads((HERE / "questions.json").read_text())
    rows, lat = [], []
    for q in qs:
        f = await run_one(q)
        lat.append(f["first_token_ms"])
        cited = [s["source"] for s in f["sources"]]
        if q["type"] == "answer":
            correct = (not f["refused"]) and all(m.lower() in f["answer"].lower() for m in q["must_contain"])
            cites_ok = q["expected_source"] in cited
            supported = await judge(f["answer"], f["sources"]) if (use_judge and correct) else None
            ok = correct and cites_ok and supported is not False
        else:
            correct = cites_ok = f["refused"]
            supported, ok = None, f["refused"]
        rows.append({**q, "ok": ok, "correct": correct, "cites_ok": cites_ok, "supported": supported,
                     "answer": f["answer"], "cited": cited, "first_token_ms": f["first_token_ms"]})
        print(f"{'PASS' if ok else 'FAIL'}  {q['id']:<4} {q['type']:<6} {f['first_token_ms']:>5} ms  {q['question']}")

    ans = [r for r in rows if r["type"] == "answer"]
    ref = [r for r in rows if r["type"] != "answer"]
    summary = {
        "answerable correct": f"{sum(r['correct'] for r in ans)}/{len(ans)}",
        "correct answers citing the right source": f"{sum(r['correct'] and r['cites_ok'] for r in ans)}/{sum(r['correct'] for r in ans)}",
        "refusals (out-of-scope + held-back)": f"{sum(r['ok'] for r in ref)}/{len(ref)}",
        "first token p50 / max (ms)": f"{int(statistics.median(lat))} / {max(lat)}",
    }
    if use_judge:
        judged = [r for r in ans if r["supported"] is not None]
        summary["judge: answer supported by cited excerpts"] = f"{sum(r['supported'] for r in judged)}/{len(judged)}"

    md = ["# Grounding eval report", "", "| Metric | Result |", "|---|---|"]
    md += [f"| {k} | {v} |" for k, v in summary.items()]
    md += ["", "| ID | Type | Pass | Question | Answer | Cited | 1st token |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        a = r["answer"].replace("\n", " ").replace("|", "/")
        md.append(f"| {r['id']} | {r['type']} | {'✅' if r['ok'] else '❌'} | {r['question']} | {a} | {', '.join(r['cited']) or '-'} | {r['first_token_ms']} ms |")
    (HERE / "report.md").write_text("\n".join(md) + "\n")
    print()
    for k, v in summary.items():
        print(f"{k:<45} {v}")
    print("\nWrote eval/report.md")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", action="store_true")
    asyncio.run(main(ap.parse_args().judge))
