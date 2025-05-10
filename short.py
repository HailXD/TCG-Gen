import sqlite3
import re

SUFFIX = '''===
Format:
Name
HP:Health
A:Attacks(C:Cost,N:Name,E:Effect,D:Damage,S:Suffix)
R:Retreat Cost(If not written, is 1)
E:Effects
V:Vstar Power
T:Types
F:Evolve From
===
Return your results a dictionary in the format:
```json
{
    "Pokemon Set_Name": [Count, "Pokemon"],
    "Trainer Name": [Count, "Trainer"],
    "Energy Type": [Count, "Energy"],
}
```
As an example, if you wanted 3 Arcanine SP, 1 Wiglett PAR 51, 3 drayton, 2 Darkness Energy and 1 Lightning Energy, that entry will look like
```json
{
    "arcanine SP": [3,"Pokemon"],
    "wiglett PAR 51": [1, "Pokemon"],
    "drayton": [3,"Trainer"],
    "Darkness Energy": [2,"Energy"],
    "Lightning Energy": [1,"Energy"]
}
Pokemon must have set names, while card numbers are only needed when there are multiple versions of the same card in the same set
Trainer does not need to have set names or card numbers
Energy does not need to have set names or card numbers

```
===
Notes:
Decks should have 60 cards
Explain the synergy and strategy
Don't write comments in the json
For energy, don't need write "Basic"
Do not any cards outside of the list
Send the deck before the explanations
Type can be Pokemon, Trainer or Energy
For Special Energies, classify them as "Energy"
The notes does not need to be in dictionary form, it should be outside the json block
Card Names Can be in 3 formats:
Card_Name (e.g drayton) - Used for trainers or energies since they have the same effect regardless of set
Card_Name Set_Name (e.g arcanine SP) - For pokemon that only has 1 type (Same attacks with different prints) in the same set
Card_Name Set_Name Card_Number (e.g wiglett PAR 51) - For pokemon that has the same name but different types in the same set
In the output use the name format given in the list
Pokemon attacks cost and types are shortened to one letter, where: C = Colorless;G = Grass;R = Fire;W = Water;L = Lightning;P = Psychic;M = Metal;F = Fighting;D = Darkness
===
OVERIDES:
ONLYDECK (No Explanations, only return json): Y
===
Create a deck with the characteristics: '''  

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

SHORTENED_ENERGY = {
    'grass': 'g',
    'fire': 'r',
    'water': 'w',
    'lightning': 'l',
    'psychic': 'p',
    'fighting': 'f',
    'metal': 'm',
    'darkness': 'd',
    'colorless': 'c',
}

ENERGY_TO_LETTER = {k: v.upper() for k, v in SHORTENED_ENERGY.items()}

def fetch_cards(db_path="pokemon_cards.db"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT name, set_name, types, number, hp, effect, abilities, attacks, retreat, evolve_from, rarity, card_type, vstar_power
        FROM cards
        WHERE regulation IN ('g', 'h', 'i', 'f')
        ORDER BY set_name, CAST(number AS INTEGER)
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

def rarity_index(rarity: str) -> int:
    """Return the index of a rarity in RARITIES_ORDER, or a large number if unknown."""
    try:
        return RARITIES_ORDER.index(rarity.lower())
    except ValueError:
        return len(RARITIES_ORDER)

def _shorten_energy_names(text: str) -> str:
    """Replace full energy names in any casing with their single-letter codes."""
    for full, letter in ENERGY_TO_LETTER.items():
        pattern = re.compile(rf'\b{full}\b', flags=re.IGNORECASE)
        text = pattern.sub(letter, text)
    return text

def write_cards_txt(cards, out_path="cards.txt"):
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

    name_set_counts = {}
    for c in selected:
        if (c['card_type'] or '').lower() == 'pokemon':
            key = (c['name'], c['set_name'])
            name_set_counts[key] = name_set_counts.get(key, 0) + 1

    with open(out_path, 'w', encoding='utf-8') as f:
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
                types_str = c['types'][2:-2]
                types_clean = types_str.replace('"', '').replace("'", '')
                short_types = ''.join(
                    ENERGY_TO_LETTER.get(t.strip().lower(), t.strip()[0].upper())
                    for t in types_clean.split(',') if t.strip()
                )
                s += f"T:{short_types}|"

            if c['effect'] and c['effect'].lower() != 'none':
                s += f"E:{c['effect']}|"

            if c['vstar_power'] and c['vstar_power'].lower() != 'none':
                s += f"V:{c['vstar_power']}|"

            if c['abilities'] and c['abilities'].lower() != 'none':
                ab = "'".join(c['abilities'].split("effect': '", 1)[1].split("'")[:-1])
                s += f"AB:{ab}|"

            if c['attacks'] and c['attacks'].lower() != 'none':
                attacks = c['attacks'][2:-2]
                attacks = (attacks.replace('}, {', '|')
                                   .replace(", 'effect': none", '')
                                   .replace("'amount': ", '')
                                   .replace(", 'damage': none", '')
                                   .replace(': ', ':')
                                   .replace(', ', ',')
                                   .replace("'", '')
                                   .replace(",suffix:", ''))
                
                attacks = _shorten_energy_names(attacks)
                s += f"A:{attacks}|"

            if c['retreat'] is not None and str(c['retreat']).lower() not in ('none', '1'):
                s += f"R:{c['retreat']}|"

            if c['evolve_from'] and c['evolve_from'].lower() != 'none':
                s += f"F:{c['evolve_from']}|"

            f.write(s[:-1].replace('\n', '\\') + '\n')
        f.write(SUFFIX)

if __name__ == "__main__":
    cards = fetch_cards()
    write_cards_txt(cards)
