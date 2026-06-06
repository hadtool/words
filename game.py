# ╔══════════════════════════════════════════════════╗
# ║             ЛОГИКА ИГРЫ — game.py                ║
# ╚══════════════════════════════════════════════════╝

import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import (
    TURN_TIMEOUT, WARNING_TIME, HINT_PENALTY,
    POINTS_PER_WORD, STREAK_X2, STREAK_X3
)
import word_loader
import database as db
import admin as adm

log = logging.getLogger(__name__)

# game_sessions[chat_id] -> dict
game_sessions: dict[int, dict] = {}


# ── Утилиты ───────────────────────────────────────────────────────────────────

def new_session(user) -> dict:
    return {
        "active": False,
        "last_word": None,
        "used_words": set(),
        "score": 0,
        "streak": 0,
        "hint_count": 0,
        "start_time": None,
        "timer_task": None,
        "warning_task": None,
        "player_id": user.id,
        "player_name": user.first_name,
    }


def get_session(chat_id: int, user=None) -> dict:
    if chat_id not in game_sessions:
        game_sessions[chat_id] = new_session(user)
    return game_sessions[chat_id]


def cancel_timers(st: dict):
    for key in ("timer_task", "warning_task"):
        task = st.get(key)
        if task and not task.done():
            task.cancel()
        st[key] = None


def calc_points(streak: int) -> tuple[int, str]:
    if streak >= STREAK_X3:
        return POINTS_PER_WORD * 3, " 🔥 *×3 бонус!*"
    if streak >= STREAK_X2:
        return POINTS_PER_WORD * 2, " ⚡ *×2 бонус!*"
    return POINTS_PER_WORD, ""


def streak_bar(n: int) -> str:
    filled = min(n, 10)
    return "🟩" * filled + "⬜" * (10 - filled)


def game_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("💡 Подсказка", callback_data="hint"),
        InlineKeyboardButton("📊 Счёт",      callback_data="score"),
        InlineKeyboardButton("🏳 Сдаться",   callback_data="give_up"),
    ]])


# ── Таймер ────────────────────────────────────────────────────────────────────

async def _warning_coroutine(bot, chat_id: int, seconds: int):
    """Предупреждение за WARNING_TIME секунд до конца."""
    await asyncio.sleep(seconds)
    st = game_sessions.get(chat_id)
    if st and st["active"]:
        await bot.send_message(
            chat_id,
            f"⚠️ Осталось *{WARNING_TIME} секунд!* Слово на "
            f"*«{st['last_word'][-1].upper()}»*",
            parse_mode="Markdown"
        )


async def _timeout_coroutine(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Срабатывает по истечении времени."""
    await asyncio.sleep(TURN_TIMEOUT)
    st = game_sessions.get(chat_id)
    if not st or not st["active"]:
        return
    st["active"] = False
    db.update_score(st["player_id"], st["score"], st["streak"])
    await ctx.bot.send_message(
        chat_id,
        f"⏰ *Время вышло!* Пока-пока! 👋\n\n"
        f"Последнее слово было: *{st['last_word'] or '—'}*\n"
        f"🏅 Счёт: *{st['score']}* | 🔥 Серия: *{st['streak']}*\n\n"
        f"Напиши /start\_game чтобы сыграть снова!",
        parse_mode="Markdown"
    )
    log.info(f"Таймаут у {st['player_name']} (id={st['player_id']}), score={st['score']}")


def start_timers(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int, st: dict):
    cancel_timers(st)
    warn_in = TURN_TIMEOUT - WARNING_TIME
    if warn_in > 0:
        st["warning_task"] = asyncio.create_task(
            _warning_coroutine(ctx.bot, chat_id, warn_in)
        )
    st["timer_task"] = asyncio.create_task(
        _timeout_coroutine(ctx, chat_id)
    )


# ── Команды ───────────────────────────────────────────────────────────────────

async def cmd_start_game(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    st = get_session(chat_id, user)
    cancel_timers(st)

    st.update({
        "active": True, "last_word": None, "used_words": set(),
        "score": 0, "streak": 0, "hint_count": 0,
        "start_time": datetime.now(),
        "player_id": user.id, "player_name": user.first_name,
    })

    msg = (
        f"🎮 *Игра началась, {user.first_name}!*\n\n"
        f"Напиши любое английское слово (мин. 3 буквы).\n"
        f"Я отвечу словом на его последнюю букву.\n"
        f"⏱ На каждый ход *{TURN_TIMEOUT} секунд*!"
    )
    await update.message.reply_text(msg, reply_markup=game_keyboard(), parse_mode="Markdown")
    await adm.log_bot_reply(ctx.bot, user, msg)
    start_timers(ctx, chat_id, st)


async def handle_word(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает слово от игрока."""
    chat_id = update.effective_chat.id
    user = update.effective_user
    st = get_session(chat_id, user)

    raw = update.message.text.strip()
    await adm.log_user_message(ctx.bot, user, raw)

    # Режим ожидания текста рассылки
    if ctx.user_data.get("waiting_broadcast") and user.id in ctx.bot_data.get("admins", []):
        pass  # handled in bot.py

    if not st["active"]:
        reply = "Игра не запущена. Напиши /start_game 🎮"
        await update.message.reply_text(reply)
        await adm.log_bot_reply(ctx.bot, user, reply)
        return

    word = raw.lower()

    # Проверки
    if not word.isalpha():
        reply = "❌ Только буквы! Попробуй ещё раз."
        await update.message.reply_text(reply)
        return

    if len(word) < 3:
        reply = "❌ Минимум 3 буквы!"
        await update.message.reply_text(reply)
        return

    if not word_loader.is_valid(word):
        reply = f"❓ *«{word}»* — нет в словаре. Попробуй другое слово."
        await update.message.reply_text(reply, parse_mode="Markdown")
        return

    if st["last_word"] and word[0] != st["last_word"][-1]:
        req = st["last_word"][-1].upper()
        reply = (
            f"❌ Слово должно начинаться на *«{req}»*!\n"
            f"Моё слово: *{st['last_word']}*"
        )
        await update.message.reply_text(reply, parse_mode="Markdown")
        return

    if word in st["used_words"]:
        reply = f"🔄 *«{word}»* уже использовалось!"
        await update.message.reply_text(reply, parse_mode="Markdown")
        return

    # ✅ Слово принято
    cancel_timers(st)
    st["used_words"].add(word)
    st["streak"] += 1
    pts, bonus = calc_points(st["streak"])
    st["score"] += pts

    # Бот выбирает ответ
    next_letter = word[-1]
    bot_word = word_loader.get_word(next_letter, st["used_words"])

    if not bot_word:
        # Бот проиграл!
        db.update_score(user.id, st["score"], st["streak"])
        st["active"] = False
        reply = (
            f"🎉 *Ты победил, {user.first_name}!*\n\n"
            f"У меня нет слов на букву *«{next_letter.upper()}»*!\n\n"
            f"🏅 Счёт: *{st['score']}* очков\n"
            f"🔥 Серия: *{st['streak']}* слов\n\n"
            f"/start_game — сыграть снова"
        )
        await update.message.reply_text(reply, parse_mode="Markdown")
        await adm.log_bot_reply(ctx.bot, user, reply)
        return

    st["used_words"].add(bot_word)
    st["last_word"] = bot_word
    bar = streak_bar(st["streak"])

    reply = (
        f"✅ *{word}* — принято!{bonus}\n"
        f"+{pts} очков | Серия: {st['streak']} {bar}\n\n"
        f"🤖 Моё слово: *{bot_word}*\n\n"
        f"Твоё слово должно начинаться на *«{bot_word[-1].upper()}»*\n"
        f"⏱ У тебя *{TURN_TIMEOUT} сек*"
    )
    await update.message.reply_text(reply, reply_markup=game_keyboard(), parse_mode="Markdown")
    await adm.log_bot_reply(ctx.bot, user, f"✅ {word} → 🤖 {bot_word}")

    start_timers(ctx, chat_id, st)


# ── Callback кнопки игры ─────────────────────────────────────────────────────

async def handle_game_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    data = query.data
    chat_id = update.effective_chat.id
    user = update.effective_user
    st = get_session(chat_id, user)

    if data not in ("hint", "score", "give_up"):
        return False

    await query.answer()

    if data == "hint":
        if not st["active"]:
            await query.message.reply_text("Нет активной игры!")
            return True
        if not st["last_word"]:
            await query.message.reply_text("Сначала напиши первое слово!")
            return True
        result = word_loader.get_hint(st["last_word"][-1], st["used_words"])
        if not result:
            await query.message.reply_text(
                f"😮 Слов на «{st['last_word'][-1].upper()}» не осталось — ты почти выиграл!"
            )
            return True
        hint_str, wlen = result
        st["score"] = max(0, st["score"] - HINT_PENALTY)
        st["hint_count"] += 1
        await query.message.reply_text(
            f"💡 *Подсказка:* `{hint_str.upper()}` ({wlen} букв)\n"
            f"−{HINT_PENALTY} очков → счёт: *{st['score']}*",
            parse_mode="Markdown"
        )

    elif data == "score":
        if not st["active"]:
            await query.message.reply_text("Нет активной игры!")
            return True
        elapsed = int((datetime.now() - st["start_time"]).total_seconds())
        await query.message.reply_text(
            f"📊 *Текущий счёт*\n\n"
            f"🏅 Очки: *{st['score']}*\n"
            f"🔥 Серия: *{st['streak']}*\n"
            f"📝 Слов: *{len(st['used_words']) // 2}*\n"
            f"💡 Подсказок: *{st['hint_count']}*\n"
            f"⏱ Время: *{elapsed} сек*",
            parse_mode="Markdown"
        )

    elif data == "give_up":
        if not st["active"]:
            return True
        cancel_timers(st)
        db.update_score(st["player_id"], st["score"], st["streak"])
        st["active"] = False
        await query.message.reply_text(
            f"🏳 *Игра завершена!*\n\n"
            f"🏅 Счёт: *{st['score']}* очков\n"
            f"🔥 Серия: *{st['streak']}*\n"
            f"📝 Слов сыграно: *{len(st['used_words']) // 2}*\n\n"
            f"/start_game — сыграть снова",
            parse_mode="Markdown"
        )

    return True
