import google.generativeai as genai
import sys, sqlite3, ast, re, time
from dotenv import load_dotenv
import os

load_dotenv()

def read_until_double_newline(s=''):
    lines = []
    if s == '':
        for raw in sys.stdin:
            line = re.sub(r'\s+#.*$', '', raw)
            lines.append(line)
            if '}' in raw:
                break
        return '{' + ''.join(lines).split('{', 1)[1]
    
    else:
        for raw in s.splitlines():
            line = re.sub(r'\s+#.*$', '', raw)
            lines.append(line)
            if '}' in raw:
                break
        return '{' + ''.join(lines).split('{', 1)[1]

def load_deck(input_text):
    try:
        deck = ast.literal_eval(input_text)
        if not isinstance(deck, dict):
            raise ValueError("Expected a dict of cards")
        return deck
    except Exception as e:
        sys.exit(f"Failed to parse deck list: {e}")

def lookup_card(name, cursor, set_name=None):
    if set_name is not None:
        cursor.execute("""
            SELECT set_name, number
              FROM cards
            WHERE name = ? AND set_name = ?
        """, (name.lower(), set_name.lower()))
        rows = cursor.fetchall()
        if rows:
            return rows[0][0], rows[0][1]
    
    cursor.execute("""
        SELECT set_name, number, date, card_type
          FROM cards
        WHERE name = ? AND (rarity IS NULL OR rarity IN ('common', 'uncommon', 'ace spec rare', 'rare', 'rare holo'))
      ORDER BY date ASC
    """, (name.lower(),))
    rows = cursor.fetchall()
    if not rows:
        return None, None
    return rows[-1][0], rows[-1][1]

def compile_deck(deck_dict, db_path="pokemon_cards.db"):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    groups = {"Pokemon": [], "Trainer": [], "Energy": []}

    for full_key, (count, category) in deck_dict.items():
        if category == "Pokemon":
            parts = full_key.split(" ")
            name = ' '.join(parts[:-1])
            set_name = parts[-1]
            if set_name.isdigit():
                groups[category].append((count, full_key, '', ''))
                continue
            set_name, number = lookup_card(name, cur, set_name=set_name)

        elif category in ("Trainer", "Energy"):
            for i in range(0, 3):
                full_key = full_key.replace('Dark Energy', 'Darkness Energy')
                parts = full_key.split(" ")
                if i == 0:
                    set_name, number = lookup_card(full_key, cur)
                else:
                    set_name, number = lookup_card(' '.join(parts[:-i]), cur)
                if set_name:
                    break
            if set_name is None:
                sys.stderr.write(f"Warning: no entry found in DB for {full_key!r}\n")
                continue
        groups[category].append((count, full_key, set_name, number))

    conn.close()
    return groups

def print_deck(groups):
    ttotal = 0
    for cat in ("Pokemon", "Trainer", "Energy"):
        entries = groups.get(cat, [])
        if not entries:
            continue
        total = sum(e[0] for e in entries)
        ttotal += total
        print(f"{cat} - {total}")
        for e in entries:
            count, name, set_name, number = e
            print(f"{count} {name.replace(set_name.upper(), '')} {set_name.upper()} {number}".replace('  ', ' '))
        print()
    print(f"Total - {ttotal}")

def main():
    api_key = os.getenv("API_KEY")
    char = input("Enter deck characteristics: ")

    with open('cards.txt', 'r', encoding='utf-8') as f:
        s = f.read()

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-pro-exp-03-25")

    start = time.time()
    print(f"[{time.time() - start:.2f}s] Generating Deck..")
    response = model.generate_content(s + char)
    deck = response.text
    print(f"[{time.time() - start:.2f}s] Parsing Deck..")
    raw = read_until_double_newline(deck)
    deck = load_deck(raw)
    print(f"[{time.time() - start:.2f}s] Compiling Deck..")
    groups = compile_deck(deck)
    print_deck(groups)

if __name__ == "__main__":
    main()
