---
status: accepted
---

# Code drives the research loop; the model does not call tools

Category research and option research both search the web and read the results. Code runs that
loop: it builds each search query from a template, searches, and hands the results to the
model, which returns structured output. The model is not given a search tool to call. Its one
way to steer is a `follow_up_query` field, which code runs only when the read reports gaps and
a call remains.

Why: every value must cite a search result and pass a quote check in code, each agent has a
fixed number of searches, and a template gives the same category the same search query, so the
cache hits. The model client is text in, schema-checked JSON out; tool calling would need tool
schemas and a message loop in the client, multi-turn recorded fixtures, and proof that the
Nemotron models call tools reliably. Templates also keep the user's own words out of search
queries (`docs/eu_market.md`, personal data).

The rules are in `docs/architecture/data_sources.md` ("Research rules").

## Considered options

- **Model-driven tool calling.** The model decides when and what to search until it is
  satisfied or reaches its limit. Rejected for now: the work above for little gain at three
  searches per step, and search queries that vary between runs defeat the cache.
- **A fixed pipeline with no model input.** Rejected: a count of factors is the only thing code
  can judge, so the follow-up search would almost never run. The `gaps` field keeps the
  judgement with the model and the decision with code.

## Changing this later

The seam is the function that runs one research step (search queries in, cited values out).
Tool calling can replace the inside of that function without touching the citation check, the
limits or the cache, as long as the client gains tool support first.
