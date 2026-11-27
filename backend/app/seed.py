"""Demo family: Mira (3) and the seed cast from CLAUDE.md. Only inserted into an empty database."""

from sqlmodel import Session, select

from app.models import Character, CharacterType, ChildProfile

CHILD: dict = {
    "name": "Mira",
    "age": 3,
    "favourite_things": ["poodles", "the backyard", "bubbles", "mango", "counting stars"],
}

CAST: list[dict] = [
    {
        "name": "Minnie",
        "type": CharacterType.family,
        "description": "A toy poodle who is completely obsessed with her ball.",
        "traits": ["bouncy", "single-minded", "loving"],
        "rules": [
            "Chases her ball at least once per story.",
            'When she does, everyone shouts "Minnie, NOT NOW!"',
            "Her ball accidentally leads everyone to the clue.",
            "Ignores everything except the ball, even dragons.",
        ],
    },
    {
        "name": "Maverick",
        "type": CharacterType.family,
        "description": "A toy poodle and extremely lazy couch king.",
        "traits": ["sleepy", "gentle", "food-motivated"],
        "rules": [
            "Stays on the couch unless food is involved.",
            "Moves only for food, water and belly rubs.",
            "His licks make everything better, even grumpy wolves.",
        ],
    },
    {
        "name": "Tosia",
        "type": CharacterType.original,
        "description": "A tidy, cosy cat who loves routines like bath time and getting dressed.",
        "traits": ["tidy", "calm", "kind"],
        "rules": [
            "Teaches one simple Polish word per story, with its meaning.",
            "Likes things done in the right order.",
        ],
    },
    {
        "name": "Diggles",
        "type": CharacterType.original,
        "description": "A cheeky wombat who digs holes everywhere and steals socks.",
        "traits": ["cheeky", "fiercely loyal to Mira", "always digging"],
        "rules": [
            "Digs at least one hole, often in Tosia's garden.",
            "Has a stolen sock somewhere.",
            "Always sticks up for Mira.",
        ],
    },
    {
        "name": "Baba Yaga",
        "type": CharacterType.folklore,
        "description": "A forgetful old woman from Slavic folk tales who flies in a mortar "
        "and lives in a hut on chicken legs.",
        "traits": ["silly", "forgetful", "secretly kind"],
        "rules": [
            "Always silly, never scary.",
            "Keeps forgetting where she parked her mortar.",
            "Her hut on chicken legs dances when she is happy.",
        ],
    },
    {
        "name": "Red Riding Hood",
        "type": CharacterType.folklore,
        "description": "A brave girl in a red hood, from the old folk tale.",
        "traits": ["brave", "friendly", "generous"],
        "rules": ["Carries a basket of treats to share."],
    },
    {
        "name": "The Gingerbread Man",
        "type": CharacterType.folklore,
        "description": "A speedy gingerbread biscuit, from the old folk tale.",
        "traits": ["speedy", "cheerful", "a bit of a show-off"],
        "rules": [
            'Says "Run, run, as fast as you can!"',
            "Nobody ever eats him.",
        ],
    },
    {
        "name": "The Big Bad Wolf",
        "type": CharacterType.folklore,
        "description": "A grumpy wolf from the old folk tales who is not really bad at all.",
        "traits": ["grumpy", "huffy", "soft-hearted"],
        "rules": [
            "Huffs and puffs but never hurts or frightens anyone.",
            "Stops being grumpy when someone is kind to him.",
        ],
    },
    {
        "name": "The Clever Monkey",
        "type": CharacterType.folklore,
        "description": "A quick-thinking monkey from the Panchatantra who lives in a jamun tree by the river.",
        "traits": ["clever", "playful", "generous"],
        "rules": [
            "Solves a problem with a clever idea.",
            "Shares jamun fruit from his tree.",
        ],
    },
    {
        "name": "The Crocodile",
        "type": CharacterType.folklore,
        "description": "A big, friendly crocodile from the Panchatantra who lives in the river.",
        "traits": ["friendly", "a little gullible", "strong swimmer"],
        "rules": [
            "Gives friends rides across the river.",
            "Never chomps anyone.",
        ],
    },
]


def seed_if_empty(session: Session) -> None:
    if session.exec(select(ChildProfile)).first() is None:
        session.add(ChildProfile(**CHILD))
    if session.exec(select(Character)).first() is None:
        session.add_all(Character(**data) for data in CAST)
    session.commit()
