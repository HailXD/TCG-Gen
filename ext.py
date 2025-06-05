import os
import json
import sqlite3

SETS_PATH = 'pokemon-tcg-data/sets/en.json'
CARDS_DIR = 'pokemon-tcg-data/cards/en'
DB_PATH = 'pokemon_cards.db'

def create_connection(db_path):
    conn = sqlite3.connect(db_path)
    return conn

def create_table(conn):
    cursor = conn.cursor()
    cursor.execute(
        '''
        DROP TABLE IF EXISTS cards
        '''
    )
    cursor.execute(
        '''
        CREATE TABLE cards (
            name TEXT,
            set_name TEXT,
            types TEXT,
            number TEXT,
            hp TEXT,
            effect TEXT,
            abilities TEXT,
            attacks TEXT,
            retreat INTEGER,
            evolve_from TEXT,
            rarity TEXT,
            card_type TEXT,
            vstar_power TEXT,
            regulation TEXT,
            date TEXT,
            img TEXT
        )
        '''
    )
    conn.commit()

def process_card(card, assoc):
    name = card.get('name', '').lower()
    card_id = card.get('id', '')
    if '-' in card_id:
        set_id, number = card_id.split('-', 1)
    else:
        set_id, number = '', ''
    set_name = assoc.get(set_id, '').lower()

    types_list = [t.lower() for t in card.get('types', [])]
    types = ','.join(types_list)

    hp = str(card.get('hp', '')).lower()

    card_type = card.get('supertype', '').lower().replace('é', 'e')

    effect = ''
    if card_type == 'trainer':
        effect = '\n'.join(card.get('rules', [])).lower()

    abilities_data = card.get('abilities', [])
    abilities = ''
    vstar_power = ''
    if abilities_data:
        abilities = abilities_data[0].get('text', '').lower()
        for ab in abilities_data:
            if ab.get('type', '').lower() == 'vstar power':
                vstar_power = ab.get('text', '').lower()
                break

    attacks_data = card.get('attacks', [])
    attack_parts = []
    for atk in attacks_data:
        name_part = atk.get('name', '').lower()
        text_part = atk.get('text', '').lower()
        cost_part = ','.join([c.lower() for c in atk.get('cost', [])])
        damage_part = str(atk.get('damage', '')).lower()
        s = '(' + name_part
        if text_part:
            s += '|E:' + text_part
        if cost_part:
            s += '|C:' + cost_part
        if damage_part:
            s += '|D:' + damage_part
        s += ')'
        attack_parts.append(s)
    attacks = ';'.join(attack_parts)

    retreat = len(card.get('retreatCost', []))

    evolve_from = card.get('evolvesFrom', '').lower()
    rarity = card.get('rarity', '').lower()
    regulation = card.get('regulationMark', '').lower()
    date = card.get('releaseDate', '').lower()
    img = card.get('images', {}).get('large', '').lower()

    return (name, set_name, types, number.lower(), hp, effect,
            abilities, attacks, retreat, evolve_from, rarity,
            card_type, vstar_power, regulation, date, img)

def main():
    if not os.path.exists(SETS_PATH) or not os.path.isdir(CARDS_DIR):
        print("The dataset folder 'pokemon-tcg-data' was not found. "
              "Please upload it and try again.")
        return
    
    with open(SETS_PATH, 'r', encoding='utf-8') as f:
        sets = json.load(f)
    assoc = {s['id']: s['ptcgoCode'].lower()
             for s in sets if 'ptcgoCode' in s}

    conn = create_connection(DB_PATH)
    create_table(conn)
    cursor = conn.cursor()

    total_inserted = 0
    for filename in os.listdir(CARDS_DIR):
        file_path = os.path.join(CARDS_DIR, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            cards = json.load(f)
        for card in cards:
            card_id = card.get('id', '')
            set_id = card_id.split('-')[0] if '-' in card_id else ''
            if set_id not in assoc:
                continue
            row = process_card(card, assoc)
            cursor.execute(
                '''
                INSERT INTO cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''',
                row
            )
            total_inserted += 1

    conn.commit()
    conn.close()
    print(f"Database created at {DB_PATH} with {total_inserted} cards.")

main()
