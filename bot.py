# ╔══════════════════════════════════════════════════╗
# ║              ГЛАВНЫЙ ФАЙЛ — bot.py               ║
# ╚══════════════════════════════════════════════════╝

import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from config import BOT_TOKEN, LOG_FILE, ADMIN_IDS
import database as db
import word_loader
import game
import admin as adm

# ── Логирование ───────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)


# ── /start ────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.first_name, user.username)

    await adm.log_to_chat(
        ctx.bot,
        f"👤 *{user.first_name}* (@{user.username or user.id}) написал /start"
    )

    kb = [
        [InlineKeyboardButton("🎮 Начать игру",   callback_data="start_game"),
         InlineKeyboardButton("📖 Правила",        callback_data="rules")],
        [InlineKeyboardButton("🏆 Таблица лидеров", callback_data="leaderboard")],
    ]
    await update.message.reply_text(
        f"👋 Привет, *{user.first_name}!*\n\n"
        f"Добро пожаловать в *Word Chain* — игру в цепочку слов!\n\n"
        f"🔤 Я говорю слово → ты отвечаешь на его последнюю букву\n"
        f"⏱ 30 секунд на каждый ход\n"
        f"🏅 Зарабатывай очки и попади в топ!\n\n"
        f"Нажми *Начать игру* или /start_game",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )


# ── /cancel ───────────────────────────────────────────────────────────────────

async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.pop("waiting_broadcast", None)
    await update.message.reply_text("❌ Отменено.")


# ── /leaderboard ──────────────────────────────────────────────────────────────

async def cmd_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    top = db.get_leaderboard(10)
    medals = ["🥇","🥈","🥉"]
    lines = ["🏆 *Таблица лидеров*\n"]
    for i, (uid, d) in enumerate(top):
        m = medals[i] if i < 3 else f"{i+1}."
        lines.append(
            f"{m} *{d['name']}* — {d['total_score']} очков "
            f"(серия: {d.get('best_streak',0)}, игр: {d.get('games',0)})"
        )
    if not top:
        lines.append("Пока никто не играл. Будь первым! 🎮")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /rules ────────────────────────────────────────────────────────────────────

async def cmd_rules(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Правила Word Chain*\n\n"
        "1. Напиши любое английское слово (≥3 букв)\n"
        "2. Бот отвечает словом на *последнюю букву* твоего\n"
        "3. Ты отвечаешь на *последнюю букву* слова бота\n"
        "4. Слова *не повторяются*!\n"
        "5. На каждый ход *30 секунд* — за 5 сек до конца предупреждение\n\n"
        "🏅 *Очки:*\n"
        "• +10 за каждое слово\n"
        "• ×2 при серии 5+ слов ⚡\n"
        "• ×3 при серии 10+ слов 🔥\n"
        "• −3 за подсказку 💡\n\n"
        "🏆 Результаты сохраняются в таблице лидеров!",
        parse_mode="Markdown"
    )


# ── Общий обработчик колбэков ─────────────────────────────────────────────────

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    # Сначала проверяем admin-колбэки
    if await adm.handle_admin_callback(update, ctx):
        return

    # Потом игровые
    if await game.handle_game_callback(update, ctx):
        return

    # Общие кнопки из /start меню
    await query.answer()

    if data == "start_game":
        user = update.effective_user
        db.register_user(user.id, user.first_name, user.username)
        st = game.get_session(update.effective_chat.id, user)
        game.cancel_timers(st)
        st.update({
            "active": True, "last_word": None, "used_words": set(),
            "score": 0, "streak": 0, "hint_count": 0,
            "start_time": __import__("datetime").datetime.now(),
            "player_id": user.id, "player_name": user.first_name,
        })
        from config import TURN_TIMEOUT
        msg = (
            f"🎮 *Игра началась, {user.first_name}!*\n\n"
            f"Напиши любое английское слово (мин. 3 буквы).\n"
            f"⏱ На каждый ход *{TURN_TIMEOUT} секунд*!"
        )
        await query.message.reply_text(msg, reply_markup=game.game_keyboard(), parse_mode="Markdown")
        game.start_timers(ctx, update.effective_chat.id, st)

    elif data == "leaderboard":
        top = db.get_leaderboard(10)
        medals = ["🥇","🥈","🥉"]
        lines = ["🏆 *Таблица лидеров*\n"]
        for i, (uid, d) in enumerate(top):
            m = medals[i] if i < 3 else f"{i+1}."
            lines.append(f"{m} *{d['name']}* — {d['total_score']} очков")
        if not top:
            lines.append("Пока пусто!")
        await query.message.reply_text("\n".join(lines), parse_mode="Markdown")

    elif data == "rules":
        await query.message.reply_text(
            "📖 *Правила:*\n"
            "• Английские слова ≥3 букв\n"
            "• Каждое — на последнюю букву предыдущего\n"
            "• 30 сек на ход, предупреждение за 5 сек\n"
            "• +10 очков, ×2 (серия 5+), ×3 (серия 10+)",
            parse_mode="Markdown"
        )


# ── Обработчик текста (слова + рассылка) ─────────────────────────────────────

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.first_name, user.username)

    # Режим ожидания текста рассылки (только для админов)
    if ctx.user_data.get("waiting_broadcast") and user.id in ADMIN_IDS:
        ctx.user_data.pop("waiting_broadcast")
        await adm.do_broadcast(update, ctx, update.message.text)
        return

    # Игровая логика
    await game.handle_word(update, ctx)


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    # Загружаем слова
    count = word_loader.load_words()
    log.info(f"Слов загружено: {count}")

    # Загружаем БД
    db.load()
    log.info(f"Пользователей в БД: {db.get_user_count()}")

    # Строим приложение
    app = Application.builder().token(BOT_TOKEN).build()

    # Команды пользователя
    app.add_handler(CommandHandler("start",        cmd_start))
    app.add_handler(CommandHandler("start_game",   game.cmd_start_game))
    app.add_handler(CommandHandler("leaderboard",  cmd_leaderboard))
    app.add_handler(CommandHandler("rules",        cmd_rules))
    app.add_handler(CommandHandler("cancel",       cmd_cancel))

    # Команды админа
    app.add_handler(CommandHandler("admin",        adm.cmd_admin))
    app.add_handler(CommandHandler("users",        adm.cmd_users))
    app.add_handler(CommandHandler("broadcast",    adm.cmd_broadcast))

    # Колбэки и текст
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    log.info("Бот запущен!")
    print("✅ Бот запущен! Нажми Ctrl+C для остановки.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
