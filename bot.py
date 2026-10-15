import os, random, requests
from datetime import datetime, timezone, timedelta

DISCORD = "https://discord.com/api/v10"
H = {"Authorization": f"Bot {os.environ['DISCORD_TOKEN']}"}
CHANNEL = os.environ["CHANNEL_ID"]
FORCE = os.environ.get("FORCE") == "true"            # ручной запуск = без кубика и кулдауна
CHANCE = float(os.environ.get("CHANCE", "0.25"))     # шанс срабатывания за запуск
COOLDOWN_MIN = int(os.environ.get("COOLDOWN_MIN", "90"))
MAX_AGE_MIN = int(os.environ.get("MAX_AGE_MIN", "120"))
BASE = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")
MODEL = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")

# игра -> факты, за которые нейронке можно зацепиться (дополни своими)
GAMES = {
    "War Thunder": "танки, самолёты, корабли, реалистичные бои, Абрамс, Т-34, зенитки, тундра, гринд техники",
    "Deadlock": "геройский шутер от Valve, смесь MOBA и шутера, 6 на 6, души, линии, герои с абилками",
    "Helldivers 2": "кооп-шутер, Супер-Земля, управляемая демократия, стратагемы, огонь по своим, жуки и автоматоны",
    "игры с F95zone": "взрослые игры и визуальные новеллы 18+, сотни часов контента, сюжеты, рутовые ветки",
}

SYSTEM = (
    "Ты — наглый рекламный бот в дружеском дискорде. Тебе дают сообщение человека, "
    "контекст беседы и название игры. Ответь ОДНОЙ короткой репликой (1-2 предложения), "
    "которая подхватывает смысл сообщения и естественно сворачивает его в рекламу этой игры. "
    "Шути в духе нативной рекламы, говори по-русски, как человек в чате. "
    "Не пересказывай сообщение, без хештегов, без ссылок, без кавычек."
)

# примеры стиля: (игра, контекст, сообщение, ответ)
SHOTS = [
    ("War Thunder", "", "зачем вообще что-то предзаказывать?", "абрамс можно"),
    ("War Thunder", "-знаю новеллу на 100 часов\n-да лмр знаю, 120 занял вроде",
     "120? ты хотел сказать объект 120?", "он в вар тандере есть как раз, качай"),
    ("War Thunder", "", "я пока играл, несколько лет мечтал о танке с миниганом",
     "в вар тандере есть зенитка с миниганом м163"),
    ("Helldivers 2", "", "кто идёт в кс?", "мы идём. на Супер-Землю. демократия сама себя не распространит, Helldivers 2"),
]

def fmt(game, ctx, text):
    return f"Игра: {game}\nФакты: {GAMES.get(game, '')}\nКонтекст:\n{ctx or '(нет)'}\nСообщение: {text}"

def ask_llm(game, ctx, text):
    msgs = [{"role": "system", "content": SYSTEM}]
    for g, c, t, a in SHOTS:
        msgs += [{"role": "user", "content": fmt(g, c, t)}, {"role": "assistant", "content": a}]
    msgs.append({"role": "user", "content": fmt(game, ctx, text)})
    r = requests.post(
        f"{BASE}/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['LLM_KEY']}"},
        json={"model": MODEL, "messages": msgs, "temperature": 0.9, "max_tokens": 120},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip().strip('"«»')

def main():
    if not FORCE and random.random() > CHANCE:
        return
    me = requests.get(f"{DISCORD}/users/@me", headers=H, timeout=30).json()["id"]
    r = requests.get(f"{DISCORD}/channels/{CHANNEL}/messages?limit=50", headers=H, timeout=30)
    r.raise_for_status()
    msgs = r.json()  # новые -> старые
    now = datetime.now(timezone.utc)

    mine = [m for m in msgs if m["author"]["id"] == me]
    if not FORCE and any(now - datetime.fromisoformat(m["timestamp"]) < timedelta(minutes=COOLDOWN_MIN) for m in mine):
        return
    replied = {m["message_reference"]["message_id"] for m in mine if m.get("message_reference")}

    candidates = [
        (i, m) for i, m in enumerate(msgs)
        if not m["author"].get("bot")
        and len(m["content"]) >= 8
        and "http" not in m["content"]
        and m["id"] not in replied
        and now - datetime.fromisoformat(m["timestamp"]) < timedelta(minutes=MAX_AGE_MIN)
    ]
    if not candidates:
        return
    i, target = random.choice(candidates)
    ctx = "\n".join(f"-{m['content']}" for m in reversed(msgs[i + 1:i + 4]) if m["content"] and not m["author"].get("bot"))
    game = random.choice(list(GAMES))

    reply = ask_llm(game, ctx, target["content"])
    if not reply:
        return
    requests.post(
        f"{DISCORD}/channels/{CHANNEL}/messages",
        headers=H,
        json={
            "content": reply[:400],
            "message_reference": {"message_id": target["id"], "fail_if_not_exists": False},
            "allowed_mentions": {"parse": []},
        },
        timeout=30,
    ).raise_for_status()

main()