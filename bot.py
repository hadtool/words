import logging
import random
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ─── CONFIG ───────────────────────────────────────────────────────────────────
BOT_TOKEN = "8466542476:AAGxcVeK_ZVp9bg-paEh7xXVupqBRi4V8Ic"
TURN_TIMEOUT = 30          # seconds per turn
HINT_PENALTY  = 3          # points deducted per hint
WIN_STREAK    = 10         # words in a row to win a round
POINTS_PER_WORD = 10

# ─── WORD DATABASE ────────────────────────────────────────────────────────────
# large curated list so the bot always has an answer
WORDS = [
    "apple","elephant","tiger","rabbit","bear","rock","kangaroo","owl","wolf","fox",
    "lion","nature","eagle","leopard","duck","king","gorilla","antelope","eel","llama",
    "alligator","robin","needle","exit","text","table","every","yellow","window","winter",
    "river","rain","night","tiger","rest","train","nail","lamp","planet","tower",
    "radar","dream","map","pink","kiss","snake","echo","ocean","neon","net",
    "nest","trunk","knot","tree","egg","gift","flag","game","moon","name",
    "note","event","trust","star","rabbit","bat","tap","pet","top","pan",
    "run","now","war","rope","oven","van","nap","pen","ten","tan",
    "arm","mad","bag","cab","dam","fan","gap","ham","jam","lab",
    "mat","nag","oak","pad","rag","sad","tab","wag","yam","zap",
    "ace","ice","age","ale","ape","arc","are","ate","awe","axe",
    "bid","big","bit","box","boy","bud","bug","bun","bus","but",
    "cap","car","cat","cop","cot","cow","cry","cup","cut","dad",
    "day","dig","dim","dip","dog","dot","dry","dug","dye","ear",
    "eat","end","era","eve","eye","far","fat","few","fin","fit",
    "fix","fly","fog","for","fur","gag","gas","gel","gem","get",
    "god","got","gun","gut","guy","had","has","hat","hay","her",
    "hid","him","hip","his","hit","hog","hop","hot","how","hub",
    "hug","hum","hut","ill","imp","inn","ion","ire","irk","ivy",
    "jab","jar","jaw","jay","jet","jig","job","jog","jot","joy",
    "jug","jut","keg","key","kid","kin","kit","lag","lap","law",
    "lax","lay","led","leg","lid","lip","lit","log","lot","low",
    "lug","lye","nip","nit","nob","nod","nor","not","nun","nut",
    "odd","off","oft","ohm","oil","old","one","opt","orb","ore",
    "our","out","owe","own","pay","pea","peg","pew","pie","pig",
    "pit","ply","pod","pop","pot","pro","pub","pug","pun","pup",
    "pus","put","rag","ram","ran","rat","raw","ray","red","ref",
    "rep","rev","rid","rig","rim","rip","rob","rod","rot","row",
    "rub","rug","rum","rut","rye","sag","sap","sat","saw","say",
    "sea","set","sew","she","shy","sin","sip","sir","sis","sit",
    "six","ski","sky","sly","sob","sod","son","sop","sot","sow",
    "soy","spa","spy","sub","sue","sum","sun","sup","tar","tax",
    "tea","the","thy","tie","tin","tip","toe","ton","too","toy",
    "try","tub","tug","tun","two","urn","use","vat","vet","vex",
    "via","vie","vim","vow","wad","was","wax","web","wed","wet",
    "who","why","wig","win","wit","woe","wok","won","woo","wry",
    "yak","yap","yaw","yea","yet","yew","you","zag","zap","zig",
    "zip","zoo",
    "abstract","accident","account","achieve","action","active","actual","address",
    "advance","advice","affect","agency","agent","agree","ahead","almost",
    "already","always","amount","animal","answer","anyone","appeal","apply",
    "argue","around","arrive","aspect","assume","attack","attempt","attend",
    "balance","beauty","become","before","behind","belief","better","beyond",
    "border","bother","bottom","branch","breath","bridge","bright","broken",
    "budget","burden","button","camera","cancel","career","cause","center",
    "certain","chance","change","charge","choose","circle","citizen","claim",
    "client","common","complete","concept","concern","confirm","connect","consider",
    "contain","content","control","corner","correct","create","culture","damage",
    "decide","define","degree","demand","depend","design","detail","develop",
    "differ","dinner","direct","divide","double","during","effect","effort",
    "either","emerge","enable","energy","engage","enough","ensure","entire",
    "expect","explain","extend","factor","family","famous","follow","forest",
    "forget","formal","figure","filter","finish","former","forward","friend",
    "future","gather","general","global","ground","growth","happen","happen",
    "health","heart","heaven","height","history","honest","honour","impact",
    "improve","income","indeed","inside","intent","invest","island","itself",
    "journey","justice","kitchen","knowledge","language","launch","leader",
    "learn","leave","length","letter","likely","listen","little","living",
    "manage","market","matter","member","memory","mental","method","middle",
    "minute","modern","moment","money","motion","message","manner","mirror",
    "nation","nature","nearly","notice","number","object","offer","often",
    "online","option","orange","others","parent","pattern","people","person",
    "period","picture","player","please","plenty","policy","popular","position",
    "power","press","price","process","produce","profit","project","protect",
    "provide","public","purpose","quality","quickly","reason","reduce","remain",
    "remove","report","result","return","reveal","review","sector","secure",
    "select","series","signal","single","social","source","speech","spirit",
    "spread","stable","status","still","story","street","strong","student",
    "subject","suffer","supply","system","tackle","target","theory","thought",
    "title","today","together","toward","travel","truly","typical","under",
    "until","update","value","vehicle","version","village","vision","visual",
    "vital","voice","volume","watch","welcome","within","wonder","worker","world",
    "happen","yellow","explore","active","simple","sample","minute","gentle",
    "example","exercise","express","extreme","gather","general","handle","happen",
    "harvest","imagine","improve","include","increase","indeed","inform",
    "involve","journal","measure","mention","natural","operate","outside",
    "perfect","perform","prepare","prevent","primary","private","problem",
    "program","promise","support","surface","survey","survive","teacher",
    "trouble","university","usually","various","whether","without","yourself",
]

WORDS = list(set(w.lower().strip() for w in WORDS if len(w) >= 3))

# index: first letter -> list of words
from collections import defaultdict
WORD_INDEX = defaultdict(list)
for w in WORDS:
    WORD_INDEX[w[0]].append(w)

# ─── STATE ────────────────────────────────────────────────────────────────────
# game_state[chat_id] = {
#   active, last_word, used_words, score, streak, hint_used,
#   turn_task, start_time, hint_count
# }
game_state = {}

# leaderboard[user_id] = {name, total_score, games, best_streak}
leaderboard = {}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def get_state(chat_id):
    if chat_id not in game_state:
        game_state[chat_id] = {
            "active": False, "last_word": None, "used_words": set(),
            "score": 0, "streak": 0, "hint_used": False,
            "turn_task": None, "start_time": None, "hint_count": 0,
            "player_id": None, "player_name": None
        }
    return game_state[chat_id]

def bot_pick_word(letter: str, used: set) -> str | None:
    candidates = [w for w in WORD_INDEX.get(letter, []) if w not in used]
    return random.choice(candidates) if candidates else None

def validate_english(word: str) -> bool:
    return word.isalpha() and word.lower() in set(WORDS)

def update_leaderboard(uid, name, score, streak):
    if uid not in leaderboard:
        leaderboard[uid] = {"name": name, "total_score": 0, "games": 0, "best_streak": 0}
    leaderboard[uid]["name"] = name
    leaderboard[uid]["total_score"] += score
    leaderboard[uid]["games"] += 1
    leaderboard[uid]["best_streak"] = max(leaderboard[uid]["best_streak"], streak)

def fmt_leaderboard() -> str:
    if not leaderboard:
        return "🏆 Таблица лидеров пока пуста."
    sorted_lb = sorted(leaderboard.items(), key=lambda x: x[1]["total_score"], reverse=True)
    medals = ["🥇","🥈","🥉"]
    lines = ["🏆 *Таблица лидеров*\n"]
    for i, (uid, d) in enumerate(sorted_lb[:10]):
        medal = medals[i] if i < 3 else f"{i+1}."
        lines.append(
            f"{medal} *{d['name']}* — {d['total_score']} очков "
            f"(игр: {d['games']}, рекорд серии: {d['best_streak']})"
        )
    return "\n".join(lines)

# ─── TIMEOUT ──────────────────────────────────────────────────────────────────

async def turn_timeout(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    await asyncio.sleep(TURN_TIMEOUT)
    st = get_state(chat_id)
    if not st["active"]:
        return
    update_leaderboard(st["player_id"], st["player_name"], st["score"], st["streak"])
    st["active"] = False
    await context.bot.send_message(
        chat_id,
        f"⏰ *Время вышло!*\n\n"
        f"Слово было: *{st['last_word']}*\n"
        f"Твой счёт: *{st['score']}* очков | Серия: *{st['streak']}*\n\n"
        f"Напиши /start_game чтобы сыграть снова.",
        parse_mode="Markdown"
    )

def cancel_timer(st):
    if st.get("turn_task") and not st["turn_task"].done():
        st["turn_task"].cancel()

# ─── COMMANDS ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🎮 Начать игру", callback_data="start_game")],
        [InlineKeyboardButton("🏆 Лидеры", callback_data="leaderboard"),
         InlineKeyboardButton("📖 Правила", callback_data="rules")],
    ]
    await update.message.reply_text(
        "👋 *Word Chain Bot* — игра в слова!\n\n"
        "Ты называешь английское слово, я отвечаю словом на его последнюю букву.\n"
        "Потом ты снова — на последнюю букву моего слова. И так далее!\n\n"
        "Выбери действие:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

async def cmd_start_game(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    st = get_state(chat_id)
    cancel_timer(st)

    st.update({
        "active": True, "last_word": None, "used_words": set(),
        "score": 0, "streak": 0, "hint_used": False,
        "hint_count": 0, "start_time": datetime.now(),
        "player_id": user.id, "player_name": user.first_name
    })

    kb = [[InlineKeyboardButton("💡 Подсказка", callback_data="hint"),
           InlineKeyboardButton("🏳 Сдаться", callback_data="give_up")]]

    await update.message.reply_text(
        f"🎮 *Игра началась!*\n\n"
        f"Напиши любое английское слово (мин. 3 буквы).\n"
        f"У тебя *{TURN_TIMEOUT} секунд* на каждый ход!\n\n"
        f"⏱ Таймер пошёл...",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

    task = asyncio.create_task(turn_timeout(ctx, chat_id))
    st["turn_task"] = task

async def cmd_score(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    st = get_state(update.effective_chat.id)
    if not st["active"]:
        await update.message.reply_text("Сейчас нет активной игры. /start_game")
        return
    elapsed = int((datetime.now() - st["start_time"]).total_seconds())
    await update.message.reply_text(
        f"📊 *Твой счёт*\n\n"
        f"Очки: *{st['score']}*\n"
        f"Серия: *{st['streak']}*\n"
        f"Использовано слов: *{len(st['used_words'])}*\n"
        f"Время игры: *{elapsed} сек*\n"
        f"Подсказок использовано: *{st['hint_count']}*",
        parse_mode="Markdown"
    )

async def cmd_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(fmt_leaderboard(), parse_mode="Markdown")

async def cmd_rules(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Правила игры*\n\n"
        "1. Ты пишешь любое английское слово (≥3 букв)\n"
        "2. Бот отвечает словом на *последнюю букву* твоего слова\n"
        "3. Ты отвечаешь на последнюю букву слова бота\n"
        "4. Слова *не повторяются*!\n"
        "5. На каждый ход *30 секунд*\n\n"
        "🏅 *Очки:*\n"
        f"• +{POINTS_PER_WORD} за каждое слово\n"
        f"• Бонус ×2 за серию 5+\n"
        f"• Бонус ×3 за серию 10+\n"
        f"• −{HINT_PENALTY} за подсказку\n\n"
        "💡 *Подсказка* — бот покажет первые буквы слова\n"
        "🏳 *Сдаться* — закончить игру",
        parse_mode="Markdown"
    )

# ─── MAIN MESSAGE HANDLER ─────────────────────────────────────────────────────

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    st = get_state(chat_id)

    if not st["active"]:
        await update.message.reply_text(
            "Игра не запущена. Напиши /start_game 🎮"
        )
        return

    word = update.message.text.strip().lower()

    # must be letters only
    if not word.isalpha():
        await update.message.reply_text("❌ Только буквы! Попробуй ещё раз.")
        return

    if len(word) < 3:
        await update.message.reply_text("❌ Слово должно быть минимум 3 буквы!")
        return

    # check it's a real word
    if not validate_english(word):
        await update.message.reply_text(
            f"❓ *«{word}»* — я не знаю такого слова!\n"
            "Попробуй другое английское слово.",
            parse_mode="Markdown"
        )
        return

    # check first letter matches
    if st["last_word"] is not None:
        required = st["last_word"][-1]
        if word[0] != required:
            await update.message.reply_text(
                f"❌ Слово должно начинаться на букву *«{required.upper()}»*!\n"
                f"Моё слово было: *{st['last_word']}*",
                parse_mode="Markdown"
            )
            return

    # check not used
    if word in st["used_words"]:
        await update.message.reply_text(
            f"🔄 Слово *«{word}»* уже использовалось! Придумай другое.",
            parse_mode="Markdown"
        )
        return

    # ✅ Valid word
    cancel_timer(st)
    st["used_words"].add(word)
    st["streak"] += 1
    st["hint_used"] = False

    # scoring with streak bonus
    multiplier = 3 if st["streak"] >= WIN_STREAK else (2 if st["streak"] >= 5 else 1)
    points = POINTS_PER_WORD * multiplier
    st["score"] += points

    bonus_msg = ""
    if multiplier == 3:
        bonus_msg = " 🔥 *TRIPLE бонус!*"
    elif multiplier == 2:
        bonus_msg = " ⚡ *Двойной бонус!*"

    # Bot picks word
    next_letter = word[-1]
    bot_word = bot_pick_word(next_letter, st["used_words"])

    if not bot_word:
        # Bot loses!
        update_leaderboard(user.id, user.first_name, st["score"], st["streak"])
        st["active"] = False
        await update.message.reply_text(
            f"🎉 *Ты победил!*\n\n"
            f"Я не знаю слов на букву *«{next_letter.upper()}»*!\n\n"
            f"🏅 Счёт: *{st['score']}* очков\n"
            f"🔥 Серия: *{st['streak']}* слов\n\n"
            f"Напиши /start_game чтобы сыграть снова!",
            parse_mode="Markdown"
        )
        return

    st["used_words"].add(bot_word)
    st["last_word"] = bot_word

    # streak display
    streak_bar = "🟩" * min(st["streak"], 10)
    next_req = bot_word[-1].upper()

    kb = [[InlineKeyboardButton("💡 Подсказка", callback_data="hint"),
           InlineKeyboardButton("🏳 Сдаться", callback_data="give_up")]]

    await update.message.reply_text(
        f"✅ *{word}* — принято!{bonus_msg}\n"
        f"+{points} очков | Серия: {st['streak']} {streak_bar}\n\n"
        f"🤖 Моё слово: *{bot_word}*\n\n"
        f"Твоё слово должно начинаться на *«{next_req}»*\n"
        f"⏱ У тебя *{TURN_TIMEOUT} сек*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

    # restart timer
    task = asyncio.create_task(turn_timeout(ctx, chat_id))
    st["turn_task"] = task

# ─── CALLBACK BUTTONS ─────────────────────────────────────────────────────────

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    st = get_state(chat_id)
    data = query.data

    if data == "start_game":
        user = update.effective_user
        cancel_timer(st)
        st.update({
            "active": True, "last_word": None, "used_words": set(),
            "score": 0, "streak": 0, "hint_used": False,
            "hint_count": 0, "start_time": datetime.now(),
            "player_id": user.id, "player_name": user.first_name
        })
        kb = [[InlineKeyboardButton("💡 Подсказка", callback_data="hint"),
               InlineKeyboardButton("🏳 Сдаться", callback_data="give_up")]]
        await query.message.reply_text(
            f"🎮 *Игра началась!*\n\n"
            f"Напиши любое английское слово (мин. 3 буквы).\n"
            f"⏱ У тебя *{TURN_TIMEOUT} секунд* на каждый ход!",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        task = asyncio.create_task(turn_timeout(ctx, chat_id))
        st["turn_task"] = task

    elif data == "leaderboard":
        await query.message.reply_text(fmt_leaderboard(), parse_mode="Markdown")

    elif data == "rules":
        await query.message.reply_text(
            "📖 *Правила:*\n"
            "• Называй английские слова ≥3 букв\n"
            "• Каждое слово — на последнюю букву предыдущего\n"
            "• Слова не повторяются\n"
            "• 30 секунд на ход\n"
            f"• +{POINTS_PER_WORD} очков за слово, бонус ×2 (серия 5+), ×3 (серия 10+)\n"
            f"• −{HINT_PENALTY} очков за подсказку",
            parse_mode="Markdown"
        )

    elif data == "hint":
        if not st["active"]:
            await query.message.reply_text("Нет активной игры!")
            return
        if st["last_word"] is None:
            await query.message.reply_text("Сначала напиши первое слово!")
            return
        letter = st["last_word"][-1]
        candidates = [w for w in WORD_INDEX.get(letter, []) if w not in st["used_words"]]
        if not candidates:
            await query.message.reply_text(f"😮 Слов на «{letter.upper()}» не осталось — ты почти выиграл!")
            return
        hint_word = random.choice(candidates)
        # show first 2 letters + underscores
        hint = hint_word[:2] + "_" * (len(hint_word) - 2)
        st["score"] = max(0, st["score"] - HINT_PENALTY)
        st["hint_count"] += 1
        await query.message.reply_text(
            f"💡 *Подсказка:* `{hint.upper()}` ({len(hint_word)} букв)\n"
            f"−{HINT_PENALTY} очков. Текущий счёт: *{st['score']}*",
            parse_mode="Markdown"
        )

    elif data == "give_up":
        if not st["active"]:
            return
        cancel_timer(st)
        update_leaderboard(st["player_id"], st["player_name"], st["score"], st["streak"])
        st["active"] = False
        await query.message.reply_text(
            f"🏳 *Игра завершена!*\n\n"
            f"🏅 Счёт: *{st['score']}* очков\n"
            f"🔥 Лучшая серия: *{st['streak']}*\n"
            f"📝 Слов сыграно: *{len(st['used_words']) // 2}*\n\n"
            f"Напиши /start_game чтобы сыграть снова!",
            parse_mode="Markdown"
        )

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("start_game", cmd_start_game))
    app.add_handler(CommandHandler("score", cmd_score))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("rules", cmd_rules))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()