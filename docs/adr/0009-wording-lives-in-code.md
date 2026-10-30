---
status: accepted
---

# Fixed wording lives in code

The words of every fixed message live only in `src/shopper/wording.py` and `web/lib/wording.ts`.
`docs/wording.md` holds the rules for writing them, not a copy of them.

Why: `wording.md` held every message word for word in tables, and a pytest and a Vitest test
compared each row with its constant. That kept the two in step, but a new message touched four
places (the doc, the module, the test's map of rows to constants, and for the page a second map),
the map alone was some 300 lines, and the doc grew past 500 lines, most of it a copy of strings
that are just as easy to read and search in the modules. The tests checked that two copies agreed,
never that a line came out right; the tests of the logic around the words (which wording applies,
what is left out, how a value is written) stay.

Decided 28 October 2026, in a docs clean-up after task 3.1.3.

## Consequences

- New words are agreed in the task's spec, then written into the module; there is no row to add.
- Notes on what fills a placeholder, and which wording applies when, are comments and docstrings
  beside the template.
- Docs that named a section of `wording.md` name the module, or the constant.

## Considered options

- **Keep the tables and the sync tests, split the doc into a folder.** Rejected: the doc would be
  shorter per file, but every message would still be kept twice.
- **Generate the tables from the modules.** Rejected: a build step for a doc nobody needs to read
  in full, when searching the module finds a message as fast.
