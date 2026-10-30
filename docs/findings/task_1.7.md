# Findings from task 1.7: category research

## Searches and reads

Category research run live on 2026-10-14 for "I need a new frying pan, budget 50 euro", "I need
a new kettle" and "I need a cordless drill"; the supervisor named the categories frying pan,
kettle and drill.

- **Credits.** 7 Tavily credits for the three: two template searches each, and for the drill
  one follow-up ("drill battery replacement cost lifespan") after the read reported a gap. One
  more went to the price search the price fixture was trimmed from, 8 in all; the daily ceiling
  was set to 9.
- **A Dutch search query finds Dutch shops.** That price search, "de buyer mineral b 28 cm
  prijs" with the Netherlands boost, returned bol.com, Klarna, knivesandtools.nl and other Dutch
  shops, where the English category templates returned no Dutch page at all.
- **Surviving factors.** The brief agent's read, three times per category on the cached
  searches (no credits), with the prompts and limits of this task: frying pan 7, 6 and 5
  factors; kettle 8, 8 and 8; drill 7, 8 and 6. No category falls short (fewer than three
  factors in two of three reads), so the quote check stays as it is and no key term is asked
  for. Across the nine reads two factors were left out for a quote not in the result and one
  for a digit in its explanation. Nine more reads, each scored under both quote rules: the rule
  as it stands kept frying pan 8, 8 and 8, kettle 8, 8 and 8, drill 8, 6 and 7; the narrower
  rule the roadmap first named (no hyphens or end punctuation ignored) kept frying pan 7, 7 and
  8, kettle 7, 8 and 8, drill 8, 6 and 7. Both pass; the wider rule keeps one factor more in 3
  of 9 reads, and the developer chose it. To repeat it with the terminal app: delete
  `.cache/live/brief/`, set `TAVILY_DAILY_CREDIT_LIMIT` to the credits already used today so no
  new search runs, run `--skip-all` and read the trail line "Read N search results: ... factors
  kept".
- **What the reads met.** Before the normalisation was widened, quotes failed for a full stop
  at their end and for non-breaking hyphens (`data_sources.md`, "Research rules"). The care template also finds
  off-topic pages (a kettle corn machine, directional drills), which the read ignores. Every
  source in the six searches was English-language and none was Dutch, as task 1.6 found for
  discovery.
- **Time and tokens** are under "Models: time and tokens" below.

## Models: time and tokens

Measured 2026-10-14 with the brief agent's prompts, on the live searches of frying pan, kettle
and drill ("Searches and reads" above).

- **Phrasing moved from the small to the medium tier.** The same phrasing call on four frying
  pan factors: on the small tier (Nano) it took 18, 21, 23, 34, 52, 80 and 85 s, and one more
  call was cut off twice and failed after 79 s; its choices were often not answers to the
  question ("Fits induction", "Does not fit induction"). With its reasoning switched off it took
  3.5 to 5 s, but asked about the product instead of the shopper and wrote choices such as "One
  to two" for a diameter. On the medium tier (Super) it took 5.6 to 11 s in 6 of 6 calls, with
  steady questions and choices. The developer chose the medium tier on this evidence, although
  the task text named the small one.
- **The read needs room to reason.** A read of 15 or 16 search results used 4,643 to 7,485
  completion tokens, the reasoning included, so the default limit of 4,000 cut off 4 of 6
  kettle and drill reads (their JSON ended mid-string, once it was empty). With
  `BRIEF_MAX_TOKENS` at 16,000 every one of eight reads succeeded, in 22 to 37 s with three
  categories read at once; `BRIEF_TIMEOUT_SECONDS` is 120.
- **Time to the questions, from pressing Enter.** `Measure-Command` around a `--skip-all` run,
  with the 4,000-token limit still in place (no read was cut off in these runs):

  | Category | Uncached: searches, read, phrasing | Cached: from the brief store |
  |---|---|---|
  | frying pan ("I need a new frying pan, budget 50 euro") | 41.8 s | 13.5, 14.4, 19.6 s |
  | kettle ("I need a new kettle") | 57.5 s | 7.5, 8.0, 9.7, 10.3 s |
  | drill ("I need a cordless drill"), with a follow-up search and a second read | 59.3 s | 7.4, 10.1, 10.7, 11.8 s |

  Both targets are missed: 30 s uncached in all three, 10 s cached in most runs. A cached run
  spends its time on starting the app (2.8 s) and the supervisor's parsing call (3.5 to 4.8 s
  for "I need a new kettle", 7.5 to 11.6 s for the frying pan with a budget); an uncached one
  adds the read (16 to 37 s), the phrasing call (6 to 11 s) and, when it runs, a second read.
  The roadmap has a task for it. These runs came before the review of task 1.7 changed the
  prompts and raised the token limit; a cached kettle run afterwards took 11.5 s.
