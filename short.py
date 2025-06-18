import sqlite3
import re
import random
from typing import List, Dict, Any, Tuple

# Constants
# SUFFIX for the output file
SUFFIX = '''===
List Format:
Name
ace spec(Whether card is an ace spec card)
HP:Health
A:Attacks(different attacks are separated by ';', each move is grouped into {} and in the format {Name|E|C|D}, where E is effect, C is cost and D is damage where applicable)
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
Decks should minimally contain sufficient basic energies, special energies are not compulsory unless are beneficial for deck strategies
Card Names Can be in 3 formats:
Card_Name (e.g drayton) - Used for trainers or energies since they have the same effect regardless of set
Card_Name Set_Name (e.g arcanine SP) - For pokemon that only has 1 type (Same attacks with different prints) in the same set
Card_Name Set_Name Card_Number (e.g wiglett PAR 51) - For pokemon that has the same name but different types in the same set
The names in the list provided are already in the correct format, do not change them

Comment Notes:
Explain the core strategy and card synergies
The comments should be in the format:
Name:
{Deck Name}
Strategy:
{Describe the outline of the strategy}
Synergy:
{Role of each cards, how they work together, and why they are included in the deck}
===
Role:
You are a Pokemon TCG Deck Build Expert, users will give characteristics of a deck and you will build a deck with the cards based only on the card list provided, do not use cards outside of the list provided. Do not create decks blindly, all decks created must have synergy and a strategy .
'''

# Order of rarities for sorting
RARITIES_ORDER = [
    "common", "uncommon", "rare", "rare holo", "promo", "rare ultra", 
    "rare secret", "rare rainbow", "rare holo ex", "rare holo v", 
    "illustration rare", "ultra rare", "double rare", "rare holo gx", 
    "special illustration rare", "rare shiny", "shiny rare", "rare holo vmax", 
    "", "trainer gallery rare holo", "hyper rare", "rare holo lv.x", 
    "rare holo vstar", "rare shiny gx", "ace spec rare", "rare prism star", 
    "rare break", "rare prime", "rare holo star", "classic collection", 
    "legend", "rare shining", "radiant rare", "rare ace", "shiny ultra rare", 
    "amazing rare"
]

def fetch_cards_from_db(db_path: str = "pokemon_cards.db") -> List[sqlite3.Row]:
    """
    Fetches Pokemon card data from the SQLite database.
    
    Args:
        db_path: The path to the SQLite database file.
        
    Returns:
        A list of rows, where each row is a dictionary-like object representing a card.
    """
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, set_name, types, number, hp, effect, abilities, attacks, retreat, evolve_from, rarity, card_type, regulation
            FROM cards
            WHERE series LIKE 'sv%' OR series LIKE 'swsh%' OR series LIKE 'sm%'
            ORDER BY set_name, CAST(number AS INTEGER)
        """)
        return cursor.fetchall()

def get_rarity_index(rarity: str) -> int:
    """
    Gets the index of a rarity string from the RARITIES_ORDER list.
    Lower index means higher priority.
    
    Args:
        rarity: The rarity string of the card.
        
    Returns:
        The index of the rarity in the list.
    """
    try:
        return RARITIES_ORDER.index(rarity.lower())
    except ValueError:
        return len(RARITIES_ORDER)

def group_and_filter_cards(cards: List[sqlite3.Row]) -> List[sqlite3.Row]:
    """
    Groups cards and filters out duplicates based on regulation and rarity.
    - For Pokémon, grouping is by name and attacks.
    - For other cards, grouping is by name.
    - The most recent regulation is preferred.
    - If regulations are the same, the card with the better rarity (lower index) is chosen.
    
    Args:
        cards: A list of card data from the database.
        
    Returns:
        A filtered list of cards.
    """
    grouped_cards = {}
    for card in cards:
        card_type = (card['card_type'] or '').lower()
        name = card['name']
        if card_type != 'pokemon':
            name = re.sub(r'\(.*?\)', '', name).strip()

        key = (name, card['attacks'] or '') if card_type == 'pokemon' else name
        
        if key not in grouped_cards:
            grouped_cards[key] = card
        else:
            existing_card = grouped_cards[key]
            
            existing_reg = existing_card['regulation'] or ''
            new_reg = card['regulation'] or ''

            if new_reg > existing_reg:
                grouped_cards[key] = card
            elif new_reg == existing_reg and get_rarity_index(card['rarity']) < get_rarity_index(existing_card['rarity']):
                grouped_cards[key] = card
                
    return list(grouped_cards.values())

def format_card_string(card: sqlite3.Row, name_set_counts: Dict[Tuple[str, str], int]) -> str:
    """
    Formats a single card into the required string format.
    
    Args:
        card: The card data.
        name_set_counts: A dictionary counting Pokémon with the same name in the same set.
        
    Returns:
        A formatted string representing the card.
    """
    card_name = format_card_name(card, name_set_counts)
    attributes = format_card_attributes(card)
    
    full_string = f"{card_name}|{attributes}"
    return clean_card_string(full_string)

def format_card_name(card: sqlite3.Row, name_set_counts: Dict[Tuple[str, str], int]) -> str:
    """Formats the name part of the card string."""
    if card['card_type'] == 'pokemon':
        set_name_upper = card['set_name'].upper().replace('PROMO_SWSH', 'SP').replace('PR-SW', 'SP').replace('PR-SM', 'SMP').replace('PR-SV', 'SVP')
        base_name = f"{card['name']} {set_name_upper}"
        
        # Add card number if there are multiple versions in the same set
        if name_set_counts.get((card['name'], card['set_name']), 0) > 1:
            number_str = ''.join(filter(str.isdigit, card['number']))
            base_name += f" {number_str.lstrip('0')}"
        return base_name
    else:
        return ' '.join(card['name'].split())

def format_card_attributes(card: sqlite3.Row) -> str:
    """Formats the attributes part of the card string."""
    parts = []
    if card['rarity'] == 'ace spec rare':
        parts.append('ace spec')
    if card['hp'] and card['hp'].lower() != 'none':
        parts.append(f"HP:{card['hp']}")
    if card['types'] and card['types'].lower() != 'none':
        parts.append(f"T:{card['types']}")
    if card['effect'] and card['effect'].lower() != 'none':
        parts.append(f"E:{card['effect']}")
    if card['abilities'] and card['abilities'].lower() != 'none':
        parts.append(f"AB:{card['abilities']}")
    if card['attacks'] and card['attacks'].lower() != 'none':
        parts.append(f"A:{card['attacks'].replace('|', ':')}")
    if card['retreat'] is not None and str(card['retreat']).lower() not in ('none', '1'):
        parts.append(f"R:{card['retreat']}")
    if card['evolve_from'] and card['evolve_from'].lower() != 'none':
        parts.append(f"F:{card['evolve_from']}")
    if card['regulation'] and card['regulation'].lower() != 'none':
        parts.append(f"RE:{card['regulation']}")
        
    return "|".join(parts)

def clean_card_string(card_str: str) -> str:
    """Cleans up the formatted card string."""
    s = card_str.replace('.|', '|')
    s = re.sub(r'\(.*?\)', '', s)
    s = re.sub(r'\s{2,}', '.', s)
    s = s.replace(' .', '.').replace(' ,', ',')
    parts = [part.strip() for part in s.split('|')]
    return "|".join(filter(None, parts))

def write_cards_to_file(cards: List[sqlite3.Row], out_path: str = "system.txt"):
    """
    Writes the final formatted list of cards to a text file.
    
    Args:
        cards: The list of cards to write.
        out_path: The path to the output file.
    """
    # Count Pokémon with the same name in the same set to decide if card number is needed
    name_set_counts = {}
    for card in cards:
        if (card['card_type'] or '').lower() == 'pokemon':
            key = (card['name'], card['set_name'])
            name_set_counts[key] = name_set_counts.get(key, 0) + 1

    random.shuffle(cards)

    seen_names = set()
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('Card List:\n')
        for card in cards:
            formatted_card = format_card_string(card, name_set_counts)
            card_name = formatted_card.split('|')[0]
            if card_name in seen_names:
                continue
            
            seen_names.add(card_name)
            f.write(formatted_card.replace('\n', '') + '\n')
        f.write(SUFFIX)

def main():
    """Main function to fetch, process, and write card data."""
    all_cards = fetch_cards_from_db()
    filtered_cards = group_and_filter_cards(all_cards)
    # Sort for consistent output before shuffling for randomness in the list
    filtered_cards.sort(key=lambda c: (c['card_type'] != 'pokemon', c['set_name'], c['number']))
    write_cards_to_file(filtered_cards)

if __name__ == "__main__":
    main()
