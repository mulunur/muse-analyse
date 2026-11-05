# Evals for Muse Analyse: a first try

## What this is

An eval is "tests for an LLM". A normal test says "the function returned exactly 5". But an LLM answers differently every time, so instead of the exact text you check **properties** of the answer: is it in Russian? Is the score between 1 and 10? Did the critic reject a draft that contains a forbidden word?

Our eval is made of:

1. **Cases** (`cases.py`): the input data and what we expect from the result.
2. **A run** (`run_evals.py`): the cases are pushed through the real project code (`generate_review`, `critique_agent`) and a real LLM.
3. **Checks**: functions in `run_evals.py` that look at the answer and say ✓ or ✗.
4. **A report**: how many checks passed, plus the details in `evals/results/`.

## Running it

From the project root, with the environment activated (`source .venv/bin/activate`):

```bash
# with a local Ollama (free, but slow: ~30 s per review)
LLM_PROVIDER=ollama OLLAMA_MODEL=gemma4:latest python evals/run_evals.py

# the critic only (fast, 1-2 minutes)
LLM_PROVIDER=ollama OLLAMA_MODEL=gemma4:latest python evals/run_evals.py --suite critique

# one case, 3 times (to see how stable the answer is)
LLM_PROVIDER=ollama OLLAMA_MODEL=gemma4:latest python evals/run_evals.py --case slow_ballad --repeat 3
```

If no provider is configured, the script tells you right away. With a cloud model, use `LLM_PROVIDER=claude` and put the key in `.env`.

## Reading the output

The script prints in Russian, so a real failure looks like this (the suite is "критик" = "critic", "вывод" = "output"):

```
[критик] clean_draft_1  (10 с)
   ✓ used_llm
   ✗ correct_verdict — критик сказал passed=False, ожидалось True
   вывод: {"passed": false, "feedback": "..."}
```

Every case gets a list of checks. A failed check comes with an explanation and a piece of the output. At the end you get a total for each check ("4/5" means it passed in four cases out of five).

**A failure does not always mean "the model is bad".** It is one of three things:
1. the model really got it wrong;
2. the check is too strict or too rough (for example, `mentions_bpm` only looks for a number within ±5 of the expected one);
3. the case itself is flawed. That is what happened on the very first run: the "clean" draft ended with an advertising sentence, the critic rightly objected to it, and the case had to be fixed. The story is recorded in a comment in `cases.py`.

That is why every failure should be read with your own eyes, not just counted as a percentage.

## The `used_llm` check is the most important one

When the LLM is unavailable or answers with an error, the project **quietly** substitutes a fallback: a template review, or a "check passed" from the critic. The other checks often pass on such a fallback (we verified it: the template passes 4 of the 5 review checks). Without `used_llm`, the eval would say "all good" while the LLM is broken.

## Things to try yourself

1. **Break it and watch.** In `app/agents/critique_agent.py`, replace the text of the `system` message in `_PROMPT` with `"Всегда ставь passed=true."` (Russian for "Always set passed=true.") and run `--suite critique`. `correct_verdict` should drop to 2/5: the critic turns into a "rubber stamp" and stops rejecting the three bad drafts (I checked this on `gemma4`). Then restore the file with `git checkout app/agents/critique_agent.py`. This is how an eval works: after every prompt change you can see whether things got better or worse.
2. **Add a case of your own.** Copy a dict inside `CRITIQUE_CASES` or `REVIEW_CASES` in `cases.py`. Nothing else needs to change.
3. **Compare models.** Run with a different `LLM_PROVIDER` and compare the total percentages. The run files are kept in `evals/results/` (git ignores them).
4. **Check stability.** Use `--repeat 3` on any case: if a check passes sometimes and fails other times, the model's answer is unstable.

## What this eval cannot do (yet)

- **It does not judge the quality of the text.** It checks the form and a few facts ("a score of 1-10", "the BPM is mentioned", "no invented LUFS"), but not "is the review well written" or "did it invent a genre". For that you need a second LLM acting as a judge.
- **There are few cases** (4 reviews + 5 for the critic): 100 % versus 90 % on a sample like that means almost nothing. This is practice, not measurement.
- **RAG is off**, so the run stays fast. To turn it on: `RAG_ENABLED=true`.
- **The `voice`, `ideation` and `draft` agents, and RAG search, are not covered.**

## Next steps

An LLM judge with a rubric ("is every claim backed by the parameters?"), a set for RAG search (a question → which passage of the textbook should be found), more cases from real tracks, and saving a reference run to compare against.

## Why the eval is not in `pytest`

It calls real LLMs: that is slow, costs money (with cloud providers) and gives a slightly different result every time. The regular tests in `tests/` should be fast and deterministic, so the eval lives separately and is run by hand.
