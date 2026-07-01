import os
from dotenv import load_dotenv

load_dotenv()

import anthropic
from tools import TOOLS, TOOL_FNS

client = anthropic.Anthropic()

MODEL = "claude-haiku-4-5-20251001"

SYSTEM = """You are a churn analytics assistant for a SaaS company.

You have two tools:
- sql_query: precise aggregations, counts, group-bys over the full 1000-user dataset
- semantic_search: find users with similar behavior patterns via vector similarity

Strategy:
1. For questions about counts, rates, averages, or ranked lists → use sql_query
2. For questions about patterns, similar users, or exploratory discovery → use semantic_search
3. For complex questions → use both and synthesize the results

Always:
- Show the SQL you ran (quote it) so the user can verify
- Present tabular results as markdown tables
- Give a 1-2 sentence business insight after the data
"""


def run_agent(question: str) -> str:
    messages = [{"role": "user", "content": question}]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            text_blocks = [b.text for b in response.content if hasattr(b, "text")]
            return "\n".join(text_blocks)

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                fn = TOOL_FNS[block.name]
                result = fn(**block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})


if __name__ == "__main__":
    questions = [
        "What are the top churn reasons by plan type?",
        "Which features are associated with retention?",
    ]
    for q in questions:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        print("=" * 60)
        print(run_agent(q))
