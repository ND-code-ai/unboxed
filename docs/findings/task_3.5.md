# Findings from task 3.5: the deployment

Measured on 2026-10-30 on the Nebius endpoint, for what its documentation leaves out. The steps
are in `docs/building_the_project.md` ("Deployment").

## The "Done when" line

On 2026-10-30 the developer ran the "A kettle, €60" example at `https://truecost-unboxed.vercel.app`
from a phone on mobile data, on the real endpoint, and it reached a report. That run is the
developer's report; nothing in the repo records it on its own.

## What the platform does

**The client's IP.** The proxy (`Server: envoy`) sends one `X-Forwarded-For` entry, a public
address; `X-Forwarded-Host` and `X-Forwarded-Proto` come too. A request with a forged
`X-Forwarded-For` still arrived with one entry, so the proxy replaces the header and does not
append to it. The connection's own address is private, so uvicorn rewrites nothing, which settles
the question task 2.5.2 left open. `TRUSTED_PROXY_HOPS=1` reads the client's address. With the limit
set to 2, a laptop on wifi started two sessions and was refused a third, and a phone on mobile data
then started one: they are counted apart.

**Streams.** Not cut and not held back: events arrived as they were sent, with the 15 s keep-alive
as the longest silence. The longest measured was 186 s (a kettle's answers), and 117 s through raw
`curl -N` (a cordless drill's), so the page did not need its fallback to `GET /sessions/{id}`. The
three examples on a fresh disk took 69 to 186 s for the answers, after a start of 27 to 34 s, each
with three options.

**Stop and start.** The stop took 55 s and the start about 4 minutes. The URL was the same after
both. A session from before was 404: the disk is gone, as the documentation says.

**Region.** The project is in `eu-west2`, not the `eu-north1` the roadmap entry names; `cpu-d3`
`2vcpu-8gb` is accepted there on serverless.

**The registry secret.** Both spellings of the keys are stored, since the Nebius documentation
gives two; which one it reads was not tested.

## Cost per session

From the token counts of the LangSmith traces of the last 45 days, at the prices in
`architecture/models.md`: 29 whole answers runs, median $0.057, from $0.043 to $0.084. A start costs
$0.0003 at the median with its brief stored and up to $0.026 with it researched. The ceiling uses
$0.083: the median answers run plus a researched start.

## Tavily

Its own `/usage` said 496 of the plan's 1,000 credits used this month. The hackathon's 8,000 credits
are an add-on that answer does not show; the developer confirmed them, so 8,504 remain.

## A search that came back empty

The first analysis on the endpoint found no options: "koekenpan kopen" gave 0 results and "frying
pan kopen" 1, where the same requests from the development machine gave 6 each a few minutes later.
A kettle on the endpoint straight after found 6 and gave three options, and the frying pan again,
after a restart, found 3 and gave three options. So it passed, but an empty result is a success
and is cached, for a day on a listing search, so until the restart every frying pan got none
(`left_over_tasks.md`, task 3.6).
