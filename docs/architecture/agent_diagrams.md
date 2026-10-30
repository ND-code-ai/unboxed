# Agent diagrams

Figures for people, one per agent that runs today, in the order the graph runs them; the README
links them. They add nothing to the docs that hold the rules (named under each heading), so no task
needs to read this file; when an agent's steps change, redraw its figure. How the agents connect is
in `agents.md` ("The graph") and `graph_diagram.md`. The second-hand agent is a stub and the
conversation agent is not built, so neither has a figure.

- [Supervisor](#supervisor-from-input-to-request)
- [Brief agent](#brief-agent-what-matters-and-the-questions)
- [TCO analyzer](#tco-analyzer-how-it-finds-product-options)
- [LCA agent](#lca-agent-the-co2e-to-make-each-option)

## Supervisor: from input to request

The supervisor turns what the user typed or pasted into a request: a product category, a scope
that decides whether the analysis runs and which caveat it carries, and a budget in euros. The
small model (Nemotron 3 Nano) only names the category and scope and points at the budget phrase;
code checks each, reads the amount, fetches a pasted link, and at the end assembles the report
with `calc/`. Code: `src/shopper/agents/supervisor/` and `src/shopper/agents/linked_product/`,
three nodes in `src/shopper/graph/graph.py`. Rules: `supervisor.md`.

```mermaid
flowchart TD
    IN["User input<br/>text, a product link, or both"]

    subgraph PARSE["parse_request"]
        PRE{"Code checks<br/>the raw input"}
        LLM["Small model<br/>Nemotron 3 Nano, temp. 0<br/>names category and scope,<br/>points at the budget phrase,<br/>judges its currency"]
        CAT["Code: category check<br/>max 4 words, max 1 digit<br/>fails: asked once more<br/>runs with no category<br/>and no link: unclear"]
        BUD["Code: budget<br/>only for scopes that run<br/>reads amount and<br/>currency markers<br/>unusable: warning only"]
        ROUTE{"Scope<br/>and link"}
    end

    subgraph LINK["read_link"]
        FETCH["Fetch the page<br/>cache, else Firecrawl<br/>code reads name and<br/>euro price from JSON-LD"]
        NAME{"Product name<br/>on the page?"}
        NAMEIT["Small model names<br/>category and scope<br/>from the product name<br/>unclear becomes general"]
        DETAILS["Small model reads<br/>materials and weight<br/>non-euro price left out<br/>= linked product"]
    end

    ERR["Stops with an error<br/>no report"]
    AGENTS["Brief agent, interview,<br/>TCO, LCA, second-hand"]
    ASM["assemble_report<br/>plain code, calls calc/<br/>writes no trail entry"]
    REP["Report"]
    TRAIL[("Evidence trail")]

    IN --> PRE
    PRE -- "over 2,000 characters" --> ERR
    PRE -- "otherwise" --> LLM
    PRE -- "empty: unclear<br/>two links: several_products" --> ROUTE
    LLM -- "a model call fails" --> ERR
    LLM --> CAT --> BUD --> ROUTE

    ROUTE -- "runs, no link<br/>tuned, general, or<br/>energy_heavy, clothing<br/>with a caveat" --> AGENTS
    ROUTE -- "link, and scope<br/>runs or is unclear" --> FETCH
    ROUTE -- "not_a_product: declined<br/>several_products:<br/>name one<br/>unclear: rephrase" --> ASM

    FETCH --> NAME
    NAME -- "yes, no category" --> NAMEIT
    NAME -- "yes, category known" --> DETAILS
    NAMEIT -- "scope runs" --> DETAILS
    NAMEIT -- "does not run" --> ASM
    NAME -- "no, category known<br/>warning link_unreadable" --> AGENTS
    NAME -- "no, no category<br/>becomes unclear" --> ASM
    DETAILS --> AGENTS

    AGENTS --> ASM --> REP

    PARSE -.-> TRAIL
    LINK -.-> TRAIL
    TRAIL -.-> REP
```

## Brief agent: what matters and the questions

The brief agent finds out what matters when buying a product of the category, then asks the user
about it before any product is searched. The research runs once per category and is kept in the
brief store; each decision factor must quote a search result, and code checks the quote. The
questions come from those factors and end with how often the product will be used. Colours: blue
is a model call that reasons in full, amber one with little reasoning, grey plain code, red the
pause. Code: `src/shopper/agents/brief/` and `src/shopper/tools/brief_store.py`. Rules:
`category_brief.md`, `interview.md` and `reading_answers.md`.

```mermaid
%%{init: {"flowchart": {"wrappingWidth": 320}}}%%
flowchart TD
    Req["Request from the supervisor<br/>category, budget, linked product if any"]
    CatQ{"Category named?"}
    NoCat["No research, nothing cached<br/>usage question only"]
    StoreQ{"Brief store:<br/>brief for this category<br/>and version?"}
    Search["Two Tavily searches at once<br/>templates: buying guide, care"]
    Term["Local category term, e.g. koekenpan<br/>Nemotron 3 Super, full reasoning"]
    Read["Read results into decision factors<br/>Nemotron 3 Super, little reasoning"]
    Checks["Code checks each factor:<br/>quote stands in the cited result,<br/>no digits or banned words, at most 8"]
    GapQ{"Gaps reported or<br/>fewer than 3 factors?"}
    Follow["One follow-up Tavily search<br/>then a second read, same checks;<br/>the read with more factors stands"]
    Phrase["Phrase a question per factor<br/>and pick 4 usage frequencies<br/>Nemotron 3 Super, full reasoning;<br/>code checks every word and number"]
    Store["Brief saved to the store<br/>only if every step succeeded"]
    Stated["Stated answers from the request<br/>Nemotron 3 Super, little reasoning;<br/>the phrase must stand in the request"]
    Draw["Questions asked: up to 4 open ones,<br/>usage last unless stated;<br/>linked product: 2, no care questions"]
    Pause["Pause for the user's answers<br/>pick, Not sure, skip, or write a reply"]
    Reply["Reply read in the user's own words<br/>Nemotron 3 Super, little reasoning;<br/>same checks as the request"]
    Resume["Graph resumes: TCO analyzer<br/>gets the answers and the local term"]

    Req --> CatQ
    CatQ -- no --> NoCat
    NoCat --> Stated
    CatQ -- yes --> StoreQ
    StoreQ -- "hit: stored brief" --> Stated
    StoreQ -- miss --> Search
    StoreQ -- miss --> Term
    Search --> Read
    Read --> Checks
    Checks --> GapQ
    GapQ -- yes --> Follow
    GapQ -- no --> Phrase
    Follow --> Phrase
    Phrase --> Store
    Term --> Store
    Store --> Stated
    Stated --> Draw
    Draw --> Pause
    Pause -- "words written" --> Reply
    Pause -- "choices only" --> Resume
    Reply --> Resume
    Reply -. "read failed or nothing answered:<br/>stays paused" .-> Pause

    classDef full fill:#dbeafe,stroke:#1d4ed8,color:#111;
    classDef little fill:#fef3c7,stroke:#b45309,color:#111;
    classDef code fill:#f3f4f6,stroke:#4b5563,color:#111;
    classDef stop fill:#fee2e2,stroke:#b91c1c,color:#111;
    class Term,Phrase full;
    class Read,Stated,Reply little;
    class Checks,Store,Draw,NoCat code;
    class Pause stop;
```

## TCO analyzer: how it finds product options

The steps of option research as `src/shopper/agents/tco/` runs them (the rules are in
`option_research.md` and `option_evidence.md`). A dotted line
goes to the evidence trail.

```mermaid
flowchart TD
    input(["Request, local category term,<br/>linked product, answers"]) --> search

    subgraph step1 ["1 · Listing pages"]
        search["One search '{term} kopen'<br/>on beslist.nl and kieskeurig.nl"]
        listing["Read each site's listing page<br/>of the whole category (Firecrawl)"]
        merge["Merge the two lists in turn;<br/>the same product named twice is one"]
        search --> listing --> merge
    end

    subgraph step2 ["2 · Judgement by name"]
        by_name["Medium model, reasoning in full:<br/>long, medium, short or unknown<br/>against most of its kind"]
    end

    subgraph step3 ["3 · Product pages, at most 3 at once"]
        order["Read order: one over budget judged long,<br/>then every listed product within budget"]
        offer["Code reads the offer from the page's data:<br/>new, in euro, in stock, outliers dropped,<br/>shipping kept apart"]
        sells["Medium model, little reasoning:<br/>what the page sells, with a quote<br/>code finds on the page"]
        stop{"5 buyable or<br/>12 pages read?"}
        order --> offer --> sells --> stop
        stop -- no --> order
    end

    subgraph step4 ["4 · Judgement by page"]
        by_page["Medium model, reasoning in full,<br/>on each page read: orders the slots"]
    end

    subgraph step5 ["5 · Select, pure code"]
        slot1["Slot 1: the cheapest,<br/>or the linked product"]
        slot2["Slot 2: the durable pick"]
        slot3["Slot 3: the durable pick<br/>within budget"]
        slot1 --> slot2 --> slot3
    end

    subgraph step67 ["6 and 7 · Per option, at the same time"]
        evidence["Evidence: one search and one read,<br/>with the option's own page:<br/>lifespan, what it rests on,<br/>recurring cost, your answers checked"]
        findings["Findings: one search and one read,<br/>up to 3 tester and owner reports"]
    end

    merge --> by_name --> order
    stop -- yes --> by_page --> slot1
    slot3 --> evidence
    slot3 --> findings
    evidence -- "fails an answer" --> refill["Refill that slot once<br/>from the buyable candidates left,<br/>with its own evidence and findings"]
    refill --> output
    evidence --> output
    findings --> output
    output(["Up to 3 options, the linked product first,<br/>with warnings when fewer than two"])

    merge -. "same product, linked product" .-> trail[("Trail: a reason for every<br/>candidate left out<br/>and every empty slot")]
    sells -. "not the item, no quote,<br/>no new euro offer" .-> trail
    slot3 -. "not chosen, empty slot" .-> trail
```

## LCA agent: the CO2e to make each option

The LCA agent estimates the CO2e of making each option with one call to the large model (Nemotron
3 Ultra) for all of them. The model returns materials, masses, emission factors and a
manufacturing range, never a CO2e figure; code checks them, sums them into a range, and `calc/`
uses the range in the 10-year comparison (`docs/adr/0006-tier-3-returns-factors-code-multiplies.md`).
Code: `src/shopper/agents/lca/` and `src/shopper/calc/`. Rules: `lca.md` and `calculations.md`
("CO2e of a model estimate", "CO2e avoided").

```mermaid
%%{init: {"flowchart": {"wrappingWidth": 320}}}%%
flowchart TD
    OPT["Options from the TCO analyzer<br/>with materials and weight<br/>when the product page states them"]

    subgraph LCA["LCA agent · src/shopper/agents/lca/"]
        T12["Tier 1 published figure<br/>Tier 2 benchmark from open data<br/>designed, not built yet"]
        CALL["Tier 3: one call for all options<br/>large tier, Nemotron 3 Ultra, reasoning in full<br/>returns one factor table and, per option,<br/>materials, masses, manufacturing range<br/>invalid JSON is asked for again once"]
        OK{"Valid answer<br/>within 150 s?"}
        CHK["Code checks each option<br/>entry in its place and not declined<br/>factors within 0.05 to 500 kg CO2e per kg<br/>masses and manufacturing above 0<br/>every page material used once"]
        PASS{"Passes?"}
        SCALE["Page states a weight: code scales<br/>the assumed bulk masses to it,<br/>only by a factor of 0.5 to 2"]
        SUM["Code sums mass × factor + manufacturing<br/>at the low and the high end,<br/>then widens so high ≥ 2 × low"]
        RES["LCA result per option<br/>kg CO2e range, label: AI synthetic estimate<br/>source: model estimate, with the model ID<br/>boundary: cradle to gate"]
        NONE["No figure for any option<br/>one co2e_unavailable warning"]
        NONE1["No figure for that option<br/>co2e_unavailable warning<br/>unknown stays unknown"]
    end

    subgraph CALC["Comparison · src/shopper/calc/"]
        HOR["CO2e over the horizon, default 10 years<br/>purchases × the low and the high end"]
        AVOID["CO2e less than the cheapest option<br/>interval difference, missing if ranges overlap<br/>carries the weaker label of the two<br/>for scale: km in an average new car"]
    end

    OPT --> CALL
    T12 -.->|not built| CALL
    CALL --> OK
    OK -->|"no: call failed or<br/>time cap passed"| NONE
    OK -->|yes| CHK
    CHK --> PASS
    PASS -->|"no, or declined"| NONE1
    PASS -->|yes| SCALE
    SCALE --> SUM
    SUM --> RES
    RES --> HOR
    HOR --> AVOID

    classDef notbuilt fill:#f2f2f2,stroke:#999,stroke-dasharray:5 4,color:#777
    classDef gap fill:#fff7e6,stroke:#c98a1b
    class T12 notbuilt
    class NONE,NONE1 gap
```
