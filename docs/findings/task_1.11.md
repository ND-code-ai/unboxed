# Findings from task 1.11: the option research batch

Task 1.11 shipped four items of the 1.10 grill (`docs/findings/task_1.10.md`, "Decided", items 9
and 12) and changed two on 22 October 2026, once the code was checked against the recorded data.
The live cost was **3 medium-tier calls on Nebius** to record the price reads below. No Tavily or
Firecrawl credits were spent.

## The replay of the 1.10 price searches

The three price searches behind the wrong prices of task 1.10 were in `.cache/live/` from
21 October 2026. A price search lasts one day in the cache, so the replay does not read them
there. They were copied into `tests/fixtures/tavily/price-replay-*.json` as trimmed copies, each
result keeping its URL and title and the lines the read cites, cut from the live content. They
hold no key and no personal data, only Tavily's own `request_id`. The real model's price read
was then recorded once over each, with the new prompt (`tests/fixtures/nebius/price-replay-*.json`,
medium tier, little reasoning). The offline tests (`tests/agents/tco/test_tco_price.py`, "The
recorded price searches of task 1.10, replayed") replay those replies. They also check that the
read's input is unchanged, so a prompt change asks for a new recording.

| Wrong price in 1.10 | What the read said about its page | Rejected by |
|---|---|---|
| Oxo Ceramic Professional Non-Stick, €183.72, amazon.nl | `set_or_bundle`, quoting "OXO Professional 8" and 10" Frying Pan Set" | the page sells a set or bundle |
| GreenPan Stanley Tucci Ceramic Nonstick, €799, allesduurzaam.nl | `set_or_bundle`, quoting its "11-Piece Cookware Set" | the page sells a set or bundle |
| Brother XM2701, €21.39, kieskeurig.nl | `part_or_accessory`, quoting "Brother XM2701 Sewing Machine User Guide", also flagged "accessory" | an earlier check: the read called the page `other`, not a comparison site |

All three are rejected, and each snippet shows what its page sells. The Oxo and the GreenPan now
have no accepted price at all. Their other amounts are for another product (an OXO salad
spinner, a GreenPan saucepan) or for a listing. The Brother takes €175 at u-buy.be, a shop's
page for the machine itself. The Brother's €21.39 is caught here by the page kind, which comes
before the classification. The classification would have caught it as well, but this one reply
does not prove that on its own. kieskeurig.nl is a comparison site, so the page kind was a
misreading that happened to help.

The classification was not right everywhere. In the GreenPan read, the "Stanley Tucci Ceramic
Nonstick 2-Quart Saucepan" and the "Greenpan Padova Smokey Blue Grillpan" came back as
`the_item`, though for a frying pan they are `other_kind`. The name check rejected the saucepan's
amounts, and the grill pan's quotes held no euro marker. The three wrong prices were classified
right, but two other products were not, so task 1.12, which reuses the classification, should
count how often it is right before it is relied on alone.

## The outlier rule was dropped

Item 12 had a candidate's price dropped when under a third of the median of the other
candidates' prices, with at least three others. On the recorded data it drops real cheap
candidates. The kettle's Russell Hobbs Structure (€40.95) and Bonavita (€57.31) both fall
against the Fellow (€185.95) and the Cuisinart (€234.17, from amazon.nl), whose median is
€185.95. The Tramontina 20 cm pan (€39.95) falls against €45, €158.95 and €237.95. The rule
would remove the cheap baseline whenever two imported or premium candidates are priced. The
classification above already rejects the user guide that motivated the rule. The developer
dropped the rule, and matrix row 6 is not shipped.

## A timeout is already retried once

Row 10 assumed a model call that timed out was not retried. It is: `nebius_chat` creates the
`openai` client with `max_retries=1`, and the client sends a request that timed out once more.
A fake transport showed two requests for a call that timed out once, and two for one that timed
out twice, which then came back as a `timeout` (`tests/test_llm.py`). So the kettle's
follow-up shortlist in task 1.10 timed out twice, at `OPTION_RESEARCH_TIMEOUT_SECONDS` (120 s)
each. A retry in `_ask` would have made up to four tries, and none was added. The test pins the
behaviour, and `models.md` ("The client") states it. Whether 120 s is too short for a shortlist
of every result so far is left to the 1.10 reruns (`left_over_tasks.md`).

## Temperature: the models' recommendation, and why it was split off

Row 11 was to run the extracting reads at a low temperature after checking the models'
recommendation. The model cards, read on 22 October 2026, recommend otherwise:

- Nemotron 3 Super: "temperature=1.0 and top_p=0.95 across all tasks and serving backends",
  the low-effort mode included
  ([model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16)).
- Nemotron 3 Nano: 1.0 and top_p 1.0 for reasoning tasks, 0.6 and 0.95 for tool calling
  ([model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16)).
- Neither card warns against temperature 0 with reasoning on, and neither recommends it.
  Nebius documents a default of 1 and no per-model values
  ([API reference](https://docs.tokenfactory.nebius.com/api-reference/inference/create-chat-completion.md)).

A low temperature goes against the recommendation for every read that reasons. Its effect on
consistency, and any repetition, would have to be measured, not assumed. The change moved to its
own task in the roadmap (task 1.14), as the developer asked for if the session ran long.
