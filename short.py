import sqlite3
import re
import random

SUFFIX = '''===
List Format:
Name
ace spec(Whether card is an ace spec card)
HP:Health
A:Attacks(different attacks are separated by ';', Moves are seperated into 'name:effect:damage:cost' format)
AB:Abilities(If not written, is none)
R:Retreat Cost(If not written, is 1)
E:Effects
T:Types
F:Evolve From
RE:Regulation
===
Return your results in the format:
As an example, if you wanted 3 Arcanine SP, 1 Wiglett PAR 51, 3 drayton, 8 Darkness Energy and 11 Lightning Energy, that entry will look like
```json
{
    "Deck": [Name:arcanine SP,Count:3,Type:Pokemon],[Name:wiglett PAR 51,Count:1,Type:Pokemon],[Name:drayton,Count:3,Type:Trainer],[Name:Darkness Energy,Count:8,Type:Energy],[Name:Lightning Energy,Count:11,Type:Energy],
    "Comment": The deck... (Explanations)
}
```
Pokemon must have set names, while card numbers are only needed when there are multiple versions of the same card in the same set
Trainer does not need to have set names or card numbers
Energy does not need to have set names or card numbers
===
Important Checks:
Energies required for attacks must be included in the deck, do not include energies that are not required for attacks or miss them
Each deck must have exactly 60 cards

Deck Notes:
Type can be Pokemon, Trainer or Energy
Basic Energies can have unlimited of each, any other card including special energies are limited to 4 each, ace spec and radiant pokemon limited to 1 per deck
For Special Energies, classify them as "Energy"
For energy, don't need write "Basic"
Card Names Can be in 3 formats:
Card_Name (e.g drayton) - Used for trainers or energies since they have the same effect regardless of set
Card_Name Set_Name (e.g arcanine SP) - For pokemon that only has 1 type (Same attacks with different prints) in the same set
Card_Name Set_Name Card_Number (e.g wiglett PAR 51) - For pokemon that has the same name but different types in the same set
The names in the list provided are already in the correct format, do not change them

Comment Notes:
Explain the core strategy and card synergies
The entire explanation should be in the comment field, nothing should be outside of the json block
The comments should be in the format:
Short tl;dr of the deck's strategy
Strategy (Overall strategy of the deck)
{Describe the rough outline of the strategy}
Card Synergies (How different cards work together)
No markdown syntax, just plain text
- 

===
Role:
You are a Pokemon TCG Deck Build Expert, users will give characteristics of a deck and you will build a deck with explanations with the cards based only on the card list provided, do not use cards outside of the list provided.
'''

RARITIES_ORDER = [
    'common', 'uncommon', 'rare', 'rare holo', 'promo', 'ultra rare', 'no rarity',
    'rainbow rare', 'rare holo ex', 'rare secret', 'shiny rare', 'holo rare v',
    'illustration rare', 'double rare', 'rare holo gx', 'special illustration rare',
    'holo rare vmax', 'trainer gallery holo rare', 'hyper rare', 'rare holo lv.x',
    'trainer gallery holo rare v', 'ace spec rare', 'rare shiny gx', 'holo rare vstar',
    'trainer gallery ultra rare', 'rare break', 'rare prism star', 'rare prime',
    'rare holo star', 'legend', 'rare shining', 'shiny rare v or vmax', 'radiant rare',
    'shiny ultra rare', 'trainer gallery secret rare', 'trainer gallery holo rare v or vmax',
    'amazing rare'
]

def fetch_cards(db_path="pokemon_cards.db"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT name, set_name, types, number, hp, effect, abilities, attacks, retreat, evolve_from, rarity, card_type, regulation
        FROM cards
        WHERE regulation IN ('d', 'e', 'f', 'g', 'h', 'i', 'j')
        ORDER BY set_name, CAST(number AS INTEGER)
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

def rarity_index(rarity: str) -> int:
    try:
        return RARITIES_ORDER.index(rarity.lower())
    except ValueError:
        return len(RARITIES_ORDER)

def write_cards_txt(cards, out_path="system.txt"):
    grouped = {}
    for c in cards:
        card_type = (c['card_type'] or '').lower()
        if card_type == 'pokemon':
            key = (c['name'], c['attacks'] or '')
        else:
            key = c['effect'] or None
        if key is None:
            grouped[key] = c
        else:
            if key not in grouped:
                grouped[key] = c
            else:
                if rarity_index(c['rarity']) < rarity_index(grouped[key]['rarity']):
                    grouped[key] = c

    selected = list(grouped.values())
    selected.sort(key=lambda c: (c['card_type'] != 'pokemon', c['set_name'], c['number']))

    random.shuffle(selected)

    name_set_counts = {}
    for c in selected:
        if (c['card_type'] or '').lower() == 'pokemon':
            key = (c['name'], c['set_name'])
            name_set_counts[key] = name_set_counts.get(key, 0) + 1

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('Card List:\n')
        for c in selected:
            n = ''
            found = False
            for i in c['number'].upper():
                if not i.isdigit():
                    n += i
                    continue
                if not found and i == '0':
                    continue
                n += i
                found = True

            if c['card_type'] == 'pokemon':
                base_name = f"{c['name']} {c['set_name'].upper().replace('PROMO_SWSH', 'SP')}"
                if name_set_counts[(c['name'], c['set_name'])] > 1:
                    base_name += f" {n}"
                s = f"{base_name}|"
            else:
                s = f"{' '.join(c['name'].split(' '))}|"

            if c['rarity'] == 'ace spec rare':
                s += 'ace spec|'

            if c['hp'] and c['hp'].lower() != 'none':
                s += f"HP:{c['hp']}|"

            if c['types'] and c['types'].lower() != 'none':
                s += f"T:{c['types']}|"

            if c['effect'] and c['effect'].lower() != 'none':
                s += f"E:{c['effect']}|"

            if c['abilities'] and c['abilities'].lower() != 'none':
                ab = c['abilities']
                s += f"AB:{ab}|"

            if c['attacks'] and c['attacks'].lower() != 'none':
                attacks = c['attacks']
                s += f"A:{attacks}|"

            if c['retreat'] is not None and str(c['retreat']).lower() not in ('none', '1'):
                s += f"R:{c['retreat']}|"

            if c['evolve_from'] and c['evolve_from'].lower() != 'none':
                s += f"F:{c['evolve_from']}|"

            if c['regulation'] and c['regulation'].lower() != 'none':
                s += f"RE:{c['regulation']}|"

            s = s.replace('.|', '|')
            s = re.sub(r'\(.*?\)', '', s)
            s = re.sub(r'\s{2,}', '.', s)
            s = s.replace(' .', '.')
            s = s.replace(' ,', ',')
            f.write(s[:-1].replace('\n', '') + '\n')
        f.write(SUFFIX)

if __name__ == "__main__":
    cards = fetch_cards()
    write_cards_txt(cards)
