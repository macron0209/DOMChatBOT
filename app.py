import discord
import json
import os
import re
import random
from flask import Flask, request, redirect
from datetime import datetime
import threading

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

app = Flask(__name__)

def load_events():
    with open("events.json", "r", encoding="utf-8") as f:
        return json.load(f)

def save_events(events):
    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

def normalize(text):
    text = text.lower()
    text = re.sub(r"[！？!?.]", "", text)
    return text

def find_event(question, events):
    for event in events:
        for alias in event["aliases"]:
            if alias.lower() in question:
                return event
    return None

def detect_intent(question):
    intents = {
        "start": ["いつから", "開始", "始まる"],
        "end": ["いつまで", "終了", "終わる", "まだ"],
        "reward": ["報酬", "もらえる", "何が"],
        "content": ["内容", "どんな", "何する"],
        "active": ["今", "現在"]
    }
    for key, words in intents.items():
        for w in words:
            if w in question:
                return key
    return None

def is_active(event):
    now = datetime.now()
    start = datetime.strptime(event["start"], "%Y-%m-%d")
    end = datetime.strptime(event["end"], "%Y-%m-%d")
    return start <= now <= end

@client.event
async def on_message(message):
    if message.author.bot:
        return

    question = normalize(message.content)
    events = load_events()

    if "今やってる" in question:
        active_events = [e["name"] for e in events if is_active(e)]
        if active_events:
            await message.channel.send("現在開催中:\n" + "\n".join(active_events))
        else:
            await message.channel.send("現在開催中のイベントはありません。")
        return

    event = find_event(question, events)
    if not event:
        return

    intent = detect_intent(question)
    if not intent:
        await message.channel.send("どの情報を知りたいですか？")
        return

    if intent == "start":
        answer = event["start"]
    elif intent == "end":
        answer = event["end"]
    elif intent == "reward":
        answer = event["reward"]
    elif intent == "content":
        answer = event["content"]
    elif intent == "active":
        answer = "開催中です！" if is_active(event) else "現在は開催していません。"
    else:
        return

    templates = [
        f"{event['name']}の情報です：{answer}",
        f"{answer}です！",
        f"{event['name']}は{answer}になっています。"
    ]
    await message.channel.send(random.choice(templates))

# --- 管理画面 ---
@app.route("/")
def admin():
    events = load_events()
    return f"<pre>{json.dumps(events, ensure_ascii=False, indent=2)}</pre>"

@app.route("/add", methods=["POST"])
def add_event():
    events = load_events()
    new_event = {
        "name": request.form["name"],
        "aliases": request.form["aliases"].split(","),
        "start": request.form["start"],
        "end": request.form["end"],
        "content": request.form["content"],
        "reward": request.form["reward"]
    }
    events.append(new_event)
    save_events(events)
    return redirect("/")

def run_flask():
    port = int(os.environ.get("PORT", 10000))  # Renderが自動で割り当てるポート
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask).start()

client.run(TOKEN)
