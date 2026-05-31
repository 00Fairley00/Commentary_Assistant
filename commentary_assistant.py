"""
Performance Commentary Assistant
================================

Drafts the first-pass client-report performance commentary from a fund's
sector-level attribution data -- with every claim tagged for how well the
data supports it, and a hard rule against inventing figures.

Optional macro layer (--macro): adds *sourced* market context drawn from a live
web search, so the commentary can note the backdrop to significant sector moves
without the model inventing events from stale memory. Market context is always
cited, kept separate from the fund's own figures, and never stated as causation.

This file is both a command-line tool AND the reusable engine behind the
Streamlit web app (app.py) -- the functions here are imported there, so there is
a single source of truth for the prompt and logic.

Command-line usage
------------------
    pip install anthropic
    export ANTHROPIC_API_KEY="sk-ant-..."        # macOS/Linux

    python commentary_assistant.py --dry-run            # see the prompt (free)
    python commentary_assistant.py                      # base commentary
    python commentary_assistant.py --macro              # + sourced market context
    python commentary_assistant.py --data my_fund.csv --output commentary.md
"""

import argparse
import csv
import os
import sys

# ---------------------------------------------------------------------------
# Fund / report context. Defaults; the web app lets you override these per run.
# ---------------------------------------------------------------------------
FUND_NAME = "Global Equity Fund"
BENCHMARK_NAME = "MSCI World Index"
REPORTING_PERIOD = "Q1 2026"
BASE_CURRENCY = "GBP"

DEFAULT_MODEL = "claude-sonnet-4-6"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA = os.path.join(SCRIPT_DIR, "sample_attribution.csv")


# ---------------------------------------------------------------------------
# System prompt -- built in parts so the macro rules appear only when requested.
# ---------------------------------------------------------------------------
BASE_PROMPT = """\
You are a senior investment performance analyst drafting the performance-\
commentary section of a client report for an equity fund. You write in clear, \
concise British English, in the measured house style of an institutional \
client report: factual, precise, and free of marketing language or hyperbole.

CRITICAL RULES -- these are non-negotiable:

1. Use ONLY figures that appear in the attribution data provided below. Never \
invent, estimate, round beyond what is shown, or recall a number from anywhere \
else. If a figure is not in the data, do not state it.

2. Tag every sentence that makes a factual or interpretive claim with exactly \
one of these tags, in square brackets, at the end of the sentence:
   [GROUNDED]  -- directly supported by a figure in the data.
   [INFERRED]  -- a reasonable read that goes slightly beyond the raw figures \
(for example, attributing a result to "stock selection" because the data shows \
a positive selection effect).
   [UNCERTAIN] -- commenting on something the data does not fully support, or a \
conclusion that would require information not provided.

3. If a reader would reasonably expect detail the data does not contain, say so \
explicitly and tag it [UNCERTAIN]. Do not guess to fill the gap.
"""

MACRO_RULES = """\

4. MARKET CONTEXT -- this report includes a sourced market-context layer:
   - You may add brief market or macroeconomic context for the MOST significant \
sector moves, but ONLY drawn from the web_search tool results, and ONLY for \
events within the reporting period. Use the web_search tool to find this. Never \
rely on your own prior knowledge or memory for market events: it may be out of \
date or simply wrong.
   - Tag every such statement [MARKET CONTEXT]. Each one must be supported by a \
web search result.
   - Do NOT assert that a market event caused a sector's result. Present them \
side by side: the fund's figure first (from the data, [GROUNDED]), then the \
market backdrop ([MARKET CONTEXT], sourced). You may observe that the two are \
consistent, but tag any such linkage [INFERRED] and use cautious wording \
("consistent with", "against a backdrop of") -- never "because of" or "due to" \
as a statement of fact.
   - Do NOT accept any causal premise as given. If an explanation seems \
plausible but the search does not support it, say so. Verify, do not assume.
   - If web search returns nothing reliable for the period, state that no market \
context was found and tag [UNCERTAIN]. Do not invent events to fill the gap.
"""

STRUCTURE_PROMPT = """\

Structure the commentary under these headings:

Overall performance
    One or two sentences: the total active return for the period and the \
headline driver.

Key contributors
    The sectors with the largest positive total effects, noting whether \
allocation or selection drove the result.{macro_contrib}

Key detractors
    The sectors with the largest negative total effects, on the same basis.

Positioning
    A brief, neutral closing note on how the portfolio is positioned relative \
to the benchmark, based only on the weight data.

Finish with a section headed "Source check:" that lists each figure you used \
and confirms it appears in the provided data.{macro_sources} This is an audit \
trail, not commentary -- no tags needed in this section.
"""


def build_system_prompt(use_macro):
    """Assemble the system prompt, including macro rules only when requested."""
    prompt = BASE_PROMPT
    if use_macro:
        prompt += MACRO_RULES
        macro_contrib = (
            " Where a move is significant, you may add one sentence of sourced "
            "market context, tagged [MARKET CONTEXT]."
        )
        macro_sources = (
            " Then list the web sources used for any [MARKET CONTEXT] "
            "statements (title and URL)."
        )
    else:
        macro_contrib = ""
        macro_sources = ""
    prompt += STRUCTURE_PROMPT.format(
        macro_contrib=macro_contrib, macro_sources=macro_sources
    )
    return prompt


def _rows_to_markdown(rows):
    """Turn parsed CSV rows into a tidy markdown table (one source of truth)."""
    if len(rows) < 2:
        raise ValueError("The data needs a header row and at least one data row.")
    header, *body = rows
    lines = ["| " + " | ".join(header) + " |"]
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def load_attribution(csv_path):
    """Read an attribution CSV from disk and return it as a markdown table."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Could not find the data file at:\n  {csv_path}\n\n"
            "Make sure sample_attribution.csv is in the same folder as this "
            "script, or point to it with --data /full/path/to/your_file.csv"
        )
    with open(csv_path, newline="", encoding="utf-8") as f:
        return _rows_to_markdown(list(csv.reader(f)))


def load_attribution_from_text(text):
    """Parse attribution CSV held in a string (used by the web app upload)."""
    return _rows_to_markdown(list(csv.reader(text.splitlines())))


def build_user_message(data_table, use_macro, fund=FUND_NAME,
                       benchmark=BENCHMARK_NAME, period=REPORTING_PERIOD,
                       currency=BASE_CURRENCY):
    """Assemble the user turn: report context plus the data table."""
    msg = (
        f"Fund: {fund}\n"
        f"Benchmark: {benchmark}\n"
        f"Reporting period: {period}\n"
        f"Base currency: {currency}\n\n"
        "Sector-level attribution data (all effects in basis points):\n\n"
        f"{data_table}\n\n"
        "Please draft the performance-commentary section following all of the "
        "rules in your instructions."
    )
    if use_macro:
        msg += (
            f"\n\nFor the most significant sector moves, search for market and "
            f"macroeconomic events that occurred during {period} to provide "
            "sourced context, following the MARKET CONTEXT rules."
        )
    return msg


def generate_commentary(system_prompt, user_message, model, use_macro, api_key=None):
    """Call the Claude API. Returns (commentary_text, [(title, url), ...]).

    Raises RuntimeError with a friendly message on any setup or API problem, so
    both the CLI and the web app can present it cleanly.
    """
    try:
        from anthropic import Anthropic
    except ImportError:
        raise RuntimeError(
            "The 'anthropic' package is not installed. Run: pip install anthropic"
        )

    resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not resolved_key:
        raise RuntimeError(
            "No API key found. Set the ANTHROPIC_API_KEY environment variable, "
            "or supply a key in the web app."
        )

    client = Anthropic(api_key=resolved_key)

    kwargs = {
        "model": model,
        "max_tokens": 2000 if use_macro else 1500,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }
    if use_macro:
        kwargs["tools"] = [
            {"type": "web_search_20250305", "name": "web_search", "max_uses": 5}
        ]

    try:
        message = client.messages.create(**kwargs)
    except Exception as exc:
        raise RuntimeError(f"API call failed: {exc}")

    text = ""
    sources = []
    for block in message.content:
        if getattr(block, "type", None) == "text":
            text += block.text
            for citation in getattr(block, "citations", None) or []:
                url = getattr(citation, "url", None)
                title = getattr(citation, "title", "") or ""
                if url and url not in [s[1] for s in sources]:
                    sources.append((title, url))
    return text, sources


def main():
    parser = argparse.ArgumentParser(
        description="Draft tagged performance commentary from attribution data."
    )
    parser.add_argument("--data", default=DEFAULT_DATA,
                        help="Path to the attribution CSV (default: sample next to script).")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Claude model to use (default: {DEFAULT_MODEL}).")
    parser.add_argument("--output", help="Optional path to save the commentary.")
    parser.add_argument("--macro", action="store_true",
                        help="Add a sourced market-context layer via live web search.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the assembled prompt and exit without calling the API.")
    args = parser.parse_args()

    system_prompt = build_system_prompt(args.macro)

    try:
        data_table = load_attribution(args.data)
    except (FileNotFoundError, ValueError) as e:
        sys.exit(f"Error: {e}")

    user_message = build_user_message(data_table, args.macro)

    if args.dry_run:
        print("=" * 70)
        print("SYSTEM PROMPT" + ("  (macro layer ON)" if args.macro else ""))
        print("=" * 70)
        print(system_prompt)
        print("=" * 70)
        print("USER MESSAGE")
        print("=" * 70)
        print(user_message)
        print("=" * 70)
        print(f"(dry run -- no API call made; web search {'ENABLED' if args.macro else 'disabled'})")
        return

    try:
        commentary, sources = generate_commentary(
            system_prompt, user_message, args.model, args.macro
        )
    except RuntimeError as e:
        sys.exit(f"Error: {e}")

    print(commentary)
    if sources:
        print("\n\nSources (from live web search):")
        for title, url in sources:
            print(f"  - {title}: {url}" if title else f"  - {url}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(commentary)
            if sources:
                f.write("\n\nSources (from live web search):\n")
                for title, url in sources:
                    f.write(f"  - {title}: {url}\n" if title else f"  - {url}\n")
        print(f"\n[Saved to {args.output}]", file=sys.stderr)


if __name__ == "__main__":
    main()
