---
status: accepted
---

# A finding shows a summary; its quote is checked and never shown

Everywhere else in the app a claim rests on a quote that code finds in the cited result. Findings
(what testers and owners report) work the same way, except for what reaches the user: the
model writes a short summary in its own words, and the quote behind it is checked, written to a
debug log line on the `shopper.findings` logger, and then dropped. It is not on the product
option, the report or the trail, since the trail is shown to the user too
(`docs/architecture/data_sources.md`, "Research rules").

Why: `docs/product.md` says to summarise and link and never copy review text, and review text is
someone else's writing. Showing the quote would copy it; showing a summary with no quote at all
could not be checked. So the quote still has to pass the quote check and the name check, and the
summary is checked against it in code: it may not share a run of 6 or more words with the text
the read saw (the option's name and brand words left out), a number or a generalising word
("many", "often") stands in it only when the quote has it, and it speaks of one unit or one
test. The link to the source is shown, so the user can read the report themselves.

Considered: showing a short quote (copies review text, the thing the product rule forbids), and a
summary with no quote (nothing for code to check it against). Changing this later means changing
the report, the web page and every fixture of the findings read.

The rules are in `docs/architecture/option_evidence.md` ("Findings"); the work is task 1.8.4.
