"""
LLM-generated qualitative narrative -- industry context, trend
commentary, and macro/currency risk discussion.

HARD BOUNDARY: this module only ever receives already-computed,
finalized numbers (from NormalizedStatement / DcfValuationResult) as
read-only context. It returns TEXT ONLY. It must never be used to
generate, adjust, or "sanity check" a number that flows into the
DCF/comps math -- that boundary is enforced by this function's type
signature (it returns str, nothing else) and by convention: callers
must never parse this text back into a number for use elsewhere.

The system prompt explicitly instructs the model to only reference
numbers it was given, never invent one, and to say so if asked for a
number it wasn't given.
"""

from __future__ import annotations

from tse_valuator.llm.client import get_client


_SYSTEM_PROMPT = """You are a financial analyst assistant writing qualitative \
commentary for a Tehran Stock Exchange equity valuation report.

STRICT RULES:
- Only reference numbers explicitly given to you in the context below. \
Never calculate, estimate, or invent a financial figure.
- All financial figures given to you are HISTORICAL, ALREADY-REPORTED, \
AUDITED data unless explicitly labeled as a projection, forecast, or \
estimate. Do not describe historical data as "projected" or "forecasted."
- If asked something that would require a number you were not given, \
say plainly that the data was not provided -- do not guess.
- Your job is qualitative synthesis only: industry context, trend \
interpretation, and macro/currency risk commentary. The quantitative \
valuation (DCF, comps) has already been computed by deterministic code \
and is not your responsibility to verify or second-guess numerically.
- Flag genuine uncertainty or limitations plainly rather than writing \
confidently about things you cannot know.
"""


#def generate_qualitative_narrative(context: dict, model: str = "gpt-4o-mini") -> str:
def generate_qualitative_narrative(context: dict, model: str = "gpt-4o-mini", language: str = "English") -> str:
    """
    Generates qualitative commentary given a dict of already-computed
    facts (company name, financial figures, DCF result, etc.). The
    context dict's values are the ONLY numbers the model is allowed to
    reference -- it cannot fetch or invent anything else.
    """
    client = get_client()

    context_lines = "\n".join(f"- {key}: {value}" for key, value in context.items())
    user_message = (
        f"Here is the computed financial data for this company:\n\n{context_lines}\n\n"
        "Write a brief (3-4 paragraph) qualitative analysis covering: "
        "(1) what the financial trend shown suggests about the business, "
        "(2) relevant macro/currency risk context for a company reporting "
        "in Iranian rial, and (3) any notable caveats about this analysis.\n\nRespond in {language}."
    )#(3) any notable caveats about this analysis.")

    response = client.chat.completions.create(
        model=model,
        max_tokens=1000,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )

    return response.choices[0].message.content