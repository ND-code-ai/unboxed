"""Finding a phrase a model copied from a text, as pure functions.

One normalisation serves every check that a model's words stand in a text: the budget phrase in
the request (docs/architecture/supervisor.md), a stated requirement's phrase in the request
(docs/architecture/reading_answers.md) and a quote in a search result
(docs/architecture/data_sources.md, "Research rules").
"""

from shopper.agents.shared.model_text import HYPHENS_AND_DASHES

# What may stand at either end of a phrase without counting: punctuation, quote marks, an ellipsis.
_PHRASE_EDGES = " .,;:!?'\"" + chr(0x2026)
# Curly quotes become straight ones, and every hyphen and dash a plain hyphen.
_PLAIN_MARKS = str.maketrans(
    {
        **dict.fromkeys("‘’‚‛", "'"),
        **dict.fromkeys("“”„‟", '"'),
        **dict.fromkeys(HYPHENS_AND_DASHES, "-"),
    }
)


def plain(text: str) -> str:
    """The text compared as written: lower case, single spaces, straight quotes, plain hyphens."""
    return _plain_with_positions(text)[0]


def find_phrase(phrase: str, text: str) -> tuple[int, int] | None:
    """Where the phrase stands in the text, as the start and end of that part of the text;
    missing when it is not there.

    Case, whitespace, non-breaking spaces, curly quotes and the kind of hyphen or dash do not
    count. Nor does the punctuation at the phrase's two ends, when the phrase is not found with
    it: a model that ends a phrase with a full stop where the text goes on after a comma has
    still copied it. An empty phrase stands nowhere.
    """
    plain_text, positions = _plain_with_positions(text)
    for wanted in dict.fromkeys((plain(phrase), plain(phrase).strip(_PHRASE_EDGES))):
        at = plain_text.find(wanted) if wanted else -1
        if at >= 0:
            return positions[at], positions[at + len(wanted) - 1] + 1
    return None


def _plain_with_positions(text: str) -> tuple[str, tuple[int, ...]]:
    """The plain text, and for each of its characters the position in the text it came from."""
    characters: list[str] = []
    positions: list[int] = []
    for position, character in enumerate(text):
        # isspace() also holds for a non-breaking space.
        if character.isspace():
            if characters and characters[-1] != " ":
                characters.append(" ")
                positions.append(position)
            continue
        for plain_character in character.translate(_PLAIN_MARKS).casefold():
            characters.append(plain_character)
            positions.append(position)
    if characters and characters[-1] == " ":
        characters.pop()
        positions.pop()
    return "".join(characters), tuple(positions)
