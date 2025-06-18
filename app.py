import os
import sys
import sqlite3
from typing import List

import gradio as gr
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

load_dotenv()

api_key = os.getenv("API_KEY")

TEMPERATURE = 0.5
GEN_MODEL = "gemini-2.5-pro"
client = genai.Client(api_key=api_key)

with open("system.txt", encoding="utf-8") as f:
    system_instr = f.read()

SHOW_COMMENT = True

class Card(BaseModel):
    count: int = Field(..., ge=1, le=20)
    name: str
    category: str


if SHOW_COMMENT:
    class Recipe(BaseModel):
        Deck: List[Card]
        Comment: str
else:
    class Recipe(BaseModel):
        Deck: List[Card]

def lookup_card(name: str, cur: sqlite3.Cursor, *, set_name: str | None = None):
    if set_name is not None:
        cur.execute(
            """
            SELECT set_name, number
            FROM cards
            WHERE name = ? AND set_name = ?
            ORDER BY
                regulation IS NULL,
                regulation DESC
            """,
            (name.lower(), set_name.lower()),
        )
        if rows := cur.fetchall():
            return rows[0]

    cur.execute(
        """
        SELECT set_name, number
        FROM cards
        WHERE name = ?
          AND (rarity IS NULL
               OR rarity IN ('common','uncommon','ace spec rare',
                             'rare','rare holo','double rare'))
        ORDER BY
            regulation IS NULL,
            regulation DESC
        """,
        (name.lower(),),
    )
    rows = cur.fetchall()
    return rows[0] if rows else (None, None)


def compile_deck(deck_dict: dict, db_path: str = "pokemon_cards.db") -> dict:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    groups: dict[str, list[tuple]] = {"Pokemon": [], "Trainer": [], "Energy": []}

    for raw_name, (count, category) in deck_dict.items():
        if category == "Pokemon":
            *card_name_parts, set_tag = raw_name.split()
            card_name = " ".join(card_name_parts)
            if set_tag.isdigit():
                groups[category].append((count, raw_name, "", ""))
                continue
            set_name, number = lookup_card(card_name, cur, set_name=set_tag)

        elif category in ("Trainer", "Energy"):
            for chop in range(3):
                candidate = (
                    raw_name if chop == 0 else " ".join(raw_name.split()[:-chop])
                )
                set_name, number = lookup_card(candidate, cur)
                if set_name:
                    break
            if set_name is None:
                sys.stderr.write(f"[WARN] No DB entry for {raw_name!r}\n")
                continue

        else:
            continue

        groups[category].append((count, raw_name, set_name, str(number).replace('swsh', '').replace('sm', '')))

    conn.close()
    return groups


def balance_trainers_to_sixty(groups: dict) -> None:
    total = sum(sum(x[0] for x in groups[c]) for c in groups)
    trainers = groups.get("Trainer", [])

    while total > 60 and trainers:
        max_cnt = max(t[0] for t in trainers)
        for idx in range(len(trainers) - 1, -1, -1):
            cnt, *rest = trainers[idx]
            if cnt == max_cnt:
                trainers[idx] = (cnt - 1, *rest)
                if trainers[idx][0] == 0:
                    trainers.pop(idx)
                total -= 1
                break

    while total < 60 and trainers:
        eligible = [(i, t) for i, t in enumerate(trainers) if t[0] < 4]
        if not eligible:
            break
        min_cnt = min(t[1][0] for t in eligible)
        for idx, (cnt, *rest) in eligible:
            if cnt == min_cnt:
                trainers[idx] = (cnt + 1, *rest)
                total += 1
                break


def format_deck(groups: dict, comment: str) -> tuple[str, str]:
    lines: list[str] = []
    total = 0
    for cat in ("Pokemon", "Trainer", "Energy"):
        entries = groups.get(cat, [])
        if not entries:
            continue
        subtotal = sum(e[0] for e in entries)
        total += subtotal
        lines.append(f"{cat} - {subtotal}")
        for cnt, name, set_name, num in entries:
            if set_name:
                pretty_name = name[:-4] if name[-3:].isupper() else name
                lines.append(
                    f"{cnt} {pretty_name} {set_name.upper()} {num}".replace("  ", " ")
                )
            else:
                lines.append(f"{cnt} {name}")
        lines.append("")
    lines.append(f"Total - {total}")
    return "\n".join(lines), comment


def build_deck(characteristics: str) -> tuple[str, str]:
    response = client.models.generate_content(
        model=GEN_MODEL,
        contents=characteristics,
        config=types.GenerateContentConfig(
            temperature=TEMPERATURE,
            system_instruction=system_instr,
            response_mime_type="application/json",
            response_schema=Recipe,
            thinking_config=types.ThinkingConfig(
                thinking_budget=8192,
            )
        ),
    )

    recipe = response.parsed
    deck_dict = {card.name: (card.count, card.category) for card in recipe.Deck}

    groups = compile_deck(deck_dict)
    balance_trainers_to_sixty(groups)

    if SHOW_COMMENT:
        return format_deck(groups, recipe.Comment)
    else:
        return format_deck(groups, '')


with gr.Blocks(title="Pokémon Deck Builder") as demo:

    with gr.Row():
        with gr.Column(scale=5):
            gr.Markdown(
                """
                # Pokémon Deck Generator
                Describe the deck (strategy, types, featured Pokémon, restrictions, etc.)\n
                Click **Generate Deck**. Each Generations takes on average 2 minutes.\n
                (WIP, not very useful XD)
                """
            )
            inp = gr.Textbox(
                label="Deck characteristics",
                lines=6,
                placeholder="E.g. Fast lightning deck around Pikachu and Raichu…",
            )
            btn = gr.Button("Generate Deck", variant="primary")
            out_comments = gr.Textbox(label="Comments", lines=8, interactive=False)

        with gr.Column(scale=5):
            out_deck = gr.Textbox(label="Deck", lines=40, interactive=False)

    if SHOW_COMMENT:
        out_comments.visible = True
    else:
        out_comments.visible = False
            

    btn.click(fn=build_deck, inputs=inp, outputs=[out_deck, out_comments])

demo.launch(
    server_name="0.0.0.0",
    server_port=7860,
)
