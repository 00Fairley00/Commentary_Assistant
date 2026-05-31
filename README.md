# Performance Commentary Assistant

A small tool that drafts the first-pass performance-commentary section of an
equity-fund client report from sector-level attribution data — with every claim
tagged for how well the underlying data supports it, and a hard rule against
inventing figures.

Built as a demonstrable example of using the Claude API for a real
asset-management workflow.

---

## The problem it addresses

Writing quarterly performance commentary is slow, repetitive, and easy to get
subtly wrong. It's a natural fit for a language model — *except* that the one
thing you cannot tolerate in a regulated client report is a fabricated or
mis-stated number. A generic "summarise this for me" prompt will happily invent
a plausible figure to round out a sentence.

This tool's whole point is the discipline that prevents that:

- **Anti-fabrication rule** — the model may use *only* the figures present in
  the input data, and is told explicitly never to invent or recall numbers.
- **Confidence tagging** — every claim is tagged `[GROUNDED]`,
  `[INFERRED]`, or `[UNCERTAIN]`, so a human reviewer can see at a glance which
  statements are read straight from the data and which are interpretation.
- **Source-check audit trail** — the output ends with a list of every figure
  used, confirming each traces back to the data.

That combination is what separates a toy from something a performance team
could actually review and trust.

---

## Setup

### 1. Install Python and the SDK

You need Python 3.8 or newer (check with `python3 --version`). Then install the
one dependency:

```bash
pip install anthropic
```

### 2. Get an API key

Sign in at <https://console.anthropic.com>, go to **Settings → API Keys**, and
create a key. It will look like `sk-ant-api03-...`.

> **Treat this key like a password.** Anyone who has it can spend money on your
> account. Never paste it into your code, commit it to git, or share it in a
> message or document. If a key is ever exposed, revoke it in the console and
> create a new one. The steps below keep the key out of your code entirely.

### 3. Make the key available to the script ("installing" it)

The script reads the key from an **environment variable** called
`ANTHROPIC_API_KEY`. You don't put the key in the code — you set it in your
operating system, and the script picks it up automatically. There are two ways:
just for the current terminal session, or permanently.

**macOS / Linux**

For the current terminal session only (forgotten when you close the window):

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-your-real-key-here"
```

To set it permanently, add that same line to your shell's startup file so it's
set every time you open a terminal. Most modern Macs use zsh:

```bash
# Append the line to your zsh config, then reload it
echo 'export ANTHROPIC_API_KEY="sk-ant-api03-your-real-key-here"' >> ~/.zshrc
source ~/.zshrc
```

(If you use bash instead of zsh, replace `~/.zshrc` with `~/.bashrc`.)

**Windows**

In PowerShell, permanently (then close and reopen the terminal):

```powershell
setx ANTHROPIC_API_KEY "sk-ant-api03-your-real-key-here"
```

Or set it through the GUI: search the Start menu for *"Edit the system
environment variables"* → **Environment Variables…** → under **User variables**
click **New…**, name it `ANTHROPIC_API_KEY`, and paste the key as the value.

### 4. Check it worked

```bash
# macOS / Linux
echo $ANTHROPIC_API_KEY

# Windows (PowerShell)
echo $env:ANTHROPIC_API_KEY
```

If it prints your key, you're set. Now run:

```bash
python commentary_assistant.py
```

If you see a "No API key found" message, the variable isn't set in *this*
terminal — on Windows, remember `setx` only takes effect in new terminals you
open afterwards.

> **Optional — a `.env` file.** Some people prefer keeping the key in a local
> `.env` file (loaded with the `python-dotenv` package) rather than a shell
> config. That's fine, but if you do, add `.env` to your `.gitignore` so it's
> never committed. The environment-variable method above needs no extra
> packages, so it's the simplest place to start.

## Run it

```bash
# Inspect the exact prompt without calling the API (free, no key needed)
python commentary_assistant.py --dry-run

# Generate commentary from the included sample data
python commentary_assistant.py

# Use your own attribution file and save the result
python commentary_assistant.py --data my_fund.csv --output commentary.md
```

The input is a CSV of sector-level Brinson attribution — the kind of output a
FactSet or StatPro attribution run produces. See `sample_attribution.csv` for
the expected columns.

---

## What the output looks like

The model returns commentary in the house style, with inline tags, e.g.
(illustrative of the expected shape):

> **Overall performance**
> The Fund returned 3.85% over the period against 3.40% for the benchmark, an
> active return of +45 basis points. [GROUNDED] The result was driven primarily
> by stock selection, which contributed +24bps versus +21bps from allocation.
> [GROUNDED]
>
> **Key contributors**
> Information Technology was the largest positive contributor at +42bps, with
> selection (+30bps) the main driver and a modest allocation benefit (+12bps)
> from the Fund's overweight position. [GROUNDED] Health Care added +37bps,
> almost entirely through selection (+33bps). [GROUNDED] ...
>
> **Source check:**
> All figures used (active return +45bps, IT +42bps / +30bps / +12bps, ...)
> appear in the provided data. No figures were used that are not in the input.

If you ask it to comment on something the data can't support — *why* a sector
lagged, or individual stock names — it will say so and tag it `[UNCERTAIN]`
rather than guess.

---

## Honest limitations

(Worth as much as the code itself — judgement matters more than capability.)

- **Single period, sector level only.** No multi-period trends, no security-level
  attribution, no currency decomposition.
- **The tags are the model's own self-assessment.** They make review faster;
  they are not a formal verification. A human still signs off.
- **No live data.** Input is a static CSV. Connecting a real feed is the
  obvious next step (see below).
- **Not compliance-approved.** This drafts a *first pass* for a human to edit,
  not final client-facing text.

---

## Where it goes next (the stretch path)

1. **Wrap it in a simple interface** so it's demonstrable without the command
   line.
2. **Connect a live data source** — e.g. the FactSet MCP connector — so it pulls
   attribution directly instead of reading a CSV. This turns a script into a
   real integration.
3. **Add evals** — a set of test cases that confirm the model never fabricates a
   figure and always tags correctly. "I built evals for it" is language taken
   straight from Anthropic's Applied AI job descriptions.

---

## Why this exists

I spent years writing the performance section of client reports by hand. This is
me rebuilding that workflow on a frontier model — and, more importantly, working
out how to make such a tool trustworthy enough for a regulated environment,
which is the actual hard part.
