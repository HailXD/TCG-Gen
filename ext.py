# if os.path.exists(PTCG-database), cd into it and git pull, otherwise, gitclone it
import os

# if os.path.exists("PTCG-database"):
#     os.chdir("PTCG-database")
#     os.system("git pull")
# else:
#     os.system("git clone https://github.com/type-null/PTCG-database")
	
import glob
import orjson
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from datetime import datetime

def load_json(file_path):
    with open(file_path, 'rb') as f:
        return orjson.loads(f.read())

json_files = glob.glob("PTCG-database/data_en/**/*.json", recursive=True)
total_files = len(json_files)

all_data = []
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = [executor.submit(load_json, f) for f in json_files]

    with tqdm(total=total_files, desc="Loading JSON files") as pbar:
        for future in as_completed(futures):
            data = future.result()
            all_data.append(data)
            pbar.update(1)

formats = set()
rarities = set()

for data in all_data:
    formats.update(data.keys())
    if 'rarity' in data:
        rarities.add(data['rarity'])

import sqlite3

all_columns = set()
for doc in all_data:
    for key in doc.keys():
        all_columns.add(key)

desired_order = [
    "set_name",
    "number",

    "name",
    "card_type",
    "types",
    "hp",
    "level",
    "stage",
    "evolve_from",

    "rarity",
    "rarity_img",

    "abilities",
    "attacks",
    "effect",
    "tera_effect",
    "vstar_power",
    "ancient_trait",
    "poke_power",
    "poke_body",
    "held_item",
    "rule_box",

    "weakness",
    "resistance",
    "retreat",
    "tags",

    "set_full_name",
    "set_code",
    "set_total",
    "regulation",
    "series",
    "author",
    "date",
    "flavor_text",

    "img",
    "set_img",
    "url"
]

column_values = {}
for doc in all_data:
    for key, val in doc.items():
        column_values.setdefault(key, []).append(val)

non_null_columns = []
for col, vals in column_values.items():
    if any(val is not None for val in vals):
        non_null_columns.append(col)

ordered_columns = [col for col in desired_order if col in non_null_columns]
remaining_columns = sorted(set(non_null_columns) - set(ordered_columns))
final_columns = ordered_columns + remaining_columns

conn = sqlite3.connect("pokemon_cards.db")
cursor = conn.cursor()

cursor.execute("DROP TABLE IF EXISTS cards;")

cols_definition = ", ".join([f'"{col}" TEXT' for col in final_columns])
create_table_sql = f"CREATE TABLE IF NOT EXISTS cards ({cols_definition});"
cursor.execute(create_table_sql)

placeholders = ", ".join(["?" for _ in final_columns])
insert_sql = f"INSERT INTO cards ({', '.join(final_columns)}) VALUES ({placeholders})"

for doc in all_data:
    row = []
    for col in final_columns:
        val = doc.get(col, None)
        if not str(val).startswith("http"):
            val = str(val).lower().replace('pokémon', 'pokemon').replace("(item)", "item", 1).replace('’', "'")
        
        if val.isnumeric():
            val = str(int(val))
        if col == "date" and val:
            dt = datetime.strptime(val, "%b %d, %Y")
            val = dt.strftime("%Y-%m-%d")
        row.append(str(val))
    cursor.execute(insert_sql, row)

conn.commit()
conn.close()

os.system("streamlit run app.py --server.port 8501 --server.address 0.0.0.0")
