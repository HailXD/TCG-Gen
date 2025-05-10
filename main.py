from google import genai
from google.genai import types
import sys, sqlite3, ast, re, time
from dotenv import load_dotenv
import os

config = types.GenerateContentConfig(temperature=1)
load_dotenv()


def read_until_double_newline(s: str = "") -> str:
    lines: list[str] = []
    source = s.splitlines() if s else sys.stdin

    for raw in source:
        line = re.sub(r"\s+#.*$", "", raw)
        lines.append(line)
        if "}" in raw:
            break

    return "{" + "".join(lines).split("{", 1)[1]


def load_deck(input_text: str) -> dict:
    """Convert the deck literal to a Python dict[card_key] = (count, category)."""
    try:
        deck = ast.literal_eval(input_text)
        if not isinstance(deck, dict):
            raise ValueError("Expected a dict of cards")
        return deck
    except Exception as e:
        sys.exit(f"Failed to parse deck list: {e}")


def lookup_card(name: str, cursor: sqlite3.Cursor, set_name: str | None = None):
    if set_name is not None:
        cursor.execute(
            """
            SELECT set_name, number
              FROM cards
             WHERE name = ? AND set_name = ?
            """,
            (name.lower(), set_name.lower()),
        )
        rows = cursor.fetchall()
        if rows:
            return rows[0][0], rows[0][1]

    cursor.execute(
        """
        SELECT set_name, number, date, card_type
          FROM cards
         WHERE name = ? AND (rarity IS NULL OR rarity IN ('common', 'uncommon', 'ace spec rare', 'rare', 'rare holo'))
      ORDER BY date ASC
        """,
        (name.lower(),),
    )
    rows = cursor.fetchall()
    if not rows:
        return None, None
    return rows[-1][0], rows[-1][1]


def compile_deck(deck_dict: dict, db_path: str = "pokemon_cards.db") -> dict:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    groups: dict[str, list[tuple]] = {"Pokemon": [], "Trainer": [], "Energy": []}

    for full_key, (count, category) in deck_dict.items():
        if category == "Pokemon":
            parts = full_key.split(" ")
            name = " ".join(parts[:-1])
            set_name = parts[-1]
            if set_name.isdigit():
                groups[category].append((count, full_key, "", ""))
                continue
            set_name, number = lookup_card(name, cur, set_name=set_name)

        elif category in ("Trainer", "Energy"):
            for i in range(0, 3):
                full_key = full_key.replace("Dark Energy", "Darkness Energy")
                parts = full_key.split(" ")
                if i == 0:
                    set_name, number = lookup_card(full_key, cur)
                else:
                    set_name, number = lookup_card(" ".join(parts[:-i]), cur)
                if set_name:
                    break
            if set_name is None:
                sys.stderr.write(f"Warning: no entry found in DB for {full_key!r}\n")
                continue

        else:
            continue

        groups[category].append((count, full_key, set_name, number))

    conn.close()
    return groups



def adjust_trainers_to_sixty(groups: dict) -> None:
    total_cards: int = sum(sum(entry[0] for entry in groups[cat]) for cat in groups)
    trainer_entries = groups.get("Trainer", [])

    while total_cards > 60 and trainer_entries:
        max_count = max(entry[0] for entry in trainer_entries)
        for idx in range(len(trainer_entries) - 1, -1, -1):
            if trainer_entries[idx][0] == max_count:
                cnt, name, set_name, number = trainer_entries[idx]
                trainer_entries[idx] = (cnt - 1, name, set_name, number)
                if trainer_entries[idx][0] == 0:
                    trainer_entries.pop(idx)
                total_cards -= 1
                break
    else:
        if total_cards > 60:
            sys.stderr.write("Warning: Deck still exceeds 60 cards after exhausting Trainer copies.\n")

    groups["Trainer"] = trainer_entries



def print_deck(groups: dict) -> None:
    total_overall = 0
    for cat in ("Pokemon", "Trainer", "Energy"):
        entries = groups.get(cat, [])
        if not entries:
            continue
        subtotal = sum(e[0] for e in entries)
        total_overall += subtotal
        print(f"{cat} - {subtotal}")
        for count, name, set_name, number in entries:
            if set_name is None:
                print(f"{count} {name}")
                continue
            line = f"{count} {name.replace(set_name.upper(), '')} {set_name.upper()} {number}".replace("  ", " ")
            print(line)
        print()
    print(f"Total - {total_overall}")



def main() -> None:
    api_key = os.getenv("API_KEY")
    if not api_key:
        sys.exit("API_KEY not set in environment")

    char = input("Enter deck characteristics: ")

    with open("system.txt", "r", encoding="utf-8") as f:
        system_instruction = f.read()

    client = genai.Client(api_key=api_key)

    start = time.time()
    print(f"[{time.time() - start:.2f}s] Generating Deck..")
    response = client.models.generate_content(
        model="gemini-2.5-pro-exp-03-25",
        contents=[char],
        config=types.GenerateContentConfig(
            max_output_tokens=65535,
            temperature=1,
            system_instruction=system_instruction,
        ),
    )
    deck_text = response.text
    print(deck_text)

    print(f"[{time.time() - start:.2f}s] Parsing Deck..")
    raw_literal = read_until_double_newline(deck_text)
    deck_dict = load_deck(raw_literal)

    print(f"[{time.time() - start:.2f}s] Compiling Deck..")
    groups = compile_deck(deck_dict)
    adjust_trainers_to_sixty(groups)

    print_deck(groups)

if __name__ == "__main__":
    main()
