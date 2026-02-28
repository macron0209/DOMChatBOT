import discord
import json
import os
import re
import random
from flask import Flask, request, redirect, render_template_string
from datetime import datetime
import threading

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

app = Flask(__name__)

# --- JSON読み書き ---
def load_events():
    if not os.path.exists("events.json"):
        return []
    with open("events.json", "r", encoding="utf-8") as f:
        return json.load(f)

def save_events(events):
    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

# --- 正規化・検索・判定 ---
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
    intents_map = {
        "start": ["いつから", "開始", "始まる"],
        "end": ["いつまで", "終了", "終わる", "まだ"],
        "reward": ["報酬", "もらえる", "何が"],
        "content": ["内容", "どんな", "何する"],
        "active": ["今", "現在"]
    }
    for key, words in intents_map.items():
        for w in words:
            if w in question:
                return key
    return None

def is_active(event):
    now = datetime.now()
    start = datetime.strptime(event["start"], "%Y-%m-%d")
    end = datetime.strptime(event["end"], "%Y-%m-%d")
    return start <= now <= end

# --- Discord Bot ---
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

# --- Flask 管理画面 ---
@app.route("/")
def admin():
    events = sorted(load_events(), key=lambda e: e["start"])
    html = """
    <html>
    <head>
        <title>イベント管理</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; }
            h1 { color: #333; }
            table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
            th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            a { text-decoration: none; color: #007BFF; }
            a:hover { text-decoration: underline; }
            form input { margin-bottom: 5px; width: 300px; }
            button { margin-top: 5px; }
        </style>
    </head>
    <body>
        <h1>イベント管理画面</h1>
        <h2>イベント一覧 (開始日順)</h2>
        <table>
            <tr>
                <th>名前</th><th>開始</th><th>終了</th><th>操作</th>
            </tr>
            {% for e in events %}
            <tr>
                <td>{{e.name}}</td>
                <td>{{e.start}}</td>
                <td>{{e.end}}</td>
                <td>
                    <a href="/edit_form?name={{e.name}}">編集</a> |
                    <a href="/delete?name={{e.name}}">削除</a>
                </td>
            </tr>
            {% endfor %}
        </table>

        <h2>イベント追加</h2>
        <form action="/add" method="post">
            名前:<br><input name="name"><br>
            エイリアス(カンマ区切り):<br><input name="aliases"><br>
            開始日(YYYY-MM-DD):<br><input name="start"><br>
            終了日(YYYY-MM-DD):<br><input name="end"><br>
            内容:<br><input name="content"><br>
            報酬:<br><input name="reward"><br>
            <button type="submit">追加</button>
        </form>
    </body>
    </html>
    """
    return render_template_string(html, events=events)

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

# 編集フォーム
@app.route("/edit_form")
def edit_form():
    name = request.args.get("name")
    events = load_events()
    event = next((e for e in events if e["name"] == name), None)
    if not event:
        return redirect("/")
    html = """
    <h1>イベント編集: {{event.name}}</h1>
    <form action="/edit" method="post">
        <input type="hidden" name="original_name" value="{{event.name}}">
        名前:<br><input name="name" value="{{event.name}}"><br>
        エイリアス(カンマ区切り):<br><input name="aliases" value="{{','.join(event.aliases)}}"><br>
        開始日(YYYY-MM-DD):<br><input name="start" value="{{event.start}}"><br>
        終了日(YYYY-MM-DD):<br><input name="end" value="{{event.end}}"><br>
        内容:<br><input name="content" value="{{event.content}}"><br>
        報酬:<br><input name="reward" value="{{event.reward}}"><br>
        <button type="submit">保存</button>
    </form>
    <a href="/">戻る</a>
    """
    return render_template_string(html, event=event)

@app.route("/edit", methods=["POST"])
def edit_event():
    original_name = request.form["original_name"]
    events = load_events()
    for e in events:
        if e["name"] == original_name:
            e["name"] = request.form["name"]
            e["aliases"] = request.form["aliases"].split(",")
            e["start"] = request.form["start"]
            e["end"] = request.form["end"]
            e["content"] = request.form["content"]
            e["reward"] = request.form["reward"]
            break
    save_events(events)
    return redirect("/")

@app.route("/delete")
def delete_event():
    name = request.args.get("name")
    events = load_events()
    events = [e for e in events if e["name"] != name]
    save_events(events)
    return redirect("/")

# --- Flaskバックグラウンド起動 ---
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask).start()
client.run(TOKEN)
