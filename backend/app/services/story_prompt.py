"""Builds the story-generation prompt from the child profile and the chosen characters."""

from app.models import Character, ChildProfile

# Target length by age, in words. Age 3 is a 3-5 minute read aloud.
WORD_RANGES: dict[int, tuple[int, int]] = {
    2: (200, 400),
    3: (300, 600),
    4: (400, 700),
    5: (500, 800),
    6: (600, 900),
}

SYSTEM_PROMPT = """You write gentle stories for young children, to be read aloud by a parent.

Rules you always follow:
- The child is the hero of the story.
- Nothing frightening: no danger, threats, injuries, monsters that scare, or sad endings.
  Folklore characters are always friendly and silly.
- Use short sentences and simple words a young child knows.
- Follow every character's rules exactly. They are running jokes the child looks forward to.
- Use only the characters you are given, plus everyday people and animals.
  Never use characters from films, TV, games or modern books.
- End warm and happy. The story request says whether it is for bedtime.
- The setting has an Australian backyard and bush feel, with a family that has Indian and Polish heritage.

Format:
- First line: the story title, starting with "# ".
- Then the story in short paragraphs of plain text.
- Words from another language (like a Polish word) go in *single asterisks*, for italics.
- No other headings, lists, bold or markdown."""


def word_range(age: int) -> tuple[int, int]:
    return WORD_RANGES.get(age, WORD_RANGES[3])


def describe_character(character: Character) -> str:
    lines = [f"- {character.name}: {character.description}"]
    if character.traits:
        lines.append(f"  Personality: {', '.join(character.traits)}.")
    for rule in character.rules:
        lines.append(f"  Rule: {rule}")
    return "\n".join(lines)


BEDTIME_ENDING = (
    "This is a bedtime story: keep the pace gentle, and end calm and cosy, "
    "with everyone getting sleepy, ready for bed."
)
ANYTIME_ENDING = (
    "This story is for any time of day, not bedtime: it can be playful and lively, "
    "and ends warm and happy (no need for anyone to fall asleep)."
)


def build_story_messages(child: ChildProfile, characters: list[Character], *, bedtime: bool = False) -> list[dict]:
    """The system prompt is the same for every story; everything that varies is in the user message."""
    low, high = word_range(child.age)
    favourites = ", ".join(child.favourite_things) or "none given"
    cast = "\n".join(describe_character(c) for c in characters)
    user_prompt = f"""Write a story.

{BEDTIME_ENDING if bedtime else ANYTIME_ENDING}

The hero: {child.name}, aged {child.age}. Favourite things: {favourites}.

Characters in this story:
{cast}

Length: {low}-{high} words."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
