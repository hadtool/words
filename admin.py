# ╔══════════════════════════════════════════════════╗
# ║            АДМИН ПАНЕЛЬ — admin.py               ║
# ╚══════════════════════════════════════════════════╝

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_IDS, LOG_CHAT_ID
import database as db
import word_loader

log = logging.getLogger(__name__)


# ── Проверка прав ──────────────────────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def admin_only(func):
    """Декоратор: только для админов."""
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ У тебя нет доступа к этой команде.")
            return
        return await func(update, ctx)
    wrapper.__name__ = func.__name__
    return wrapper


# ── Лог в Telegram-чат ────────────────────────────────────────────────────────

async def log_to_chat(bot, text: str):
    """Отправляет сообщение в лог-чат если задан LOG_CHAT_ID."""
    if not LOG_CHAT_ID:
        return
    try:
        await bot.send_message(LOG_CHAT_ID, text, parse_mode="Markdown")
    except Exception as e:
        log.warning(f"Не удалось отправить лог в чат: {e}")


async def log_user_message(bot, user, text: str):
    """Логирует входящее сообщение от пользователя."""
    uname = f"@{user.username}" if user.username else f"id={user.id}"
    msg = f"📨 *{user.first_name}* ({uname})\n`{text}`"
    await log_to_chat(bot, msg)


async def log_bot_reply(bot, user, text: str):
    """Логирует ответ бота пользователю."""
    uname = f"@{user.username}" if user.username else f"id={user.id}"
    short = text[:200] + "..." if len(text) > 200 else text
    msg = f"🤖 → *{user.first_name}* ({uname})\n`{short}`"
    await log_to_chat(bot, msg)


# ── Команды админа ────────────────────────────────────────────────────────────

@admin_only
async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Главное меню админа /admin"""
    kb = [
        [InlineKeyboardButton("👥 Пользователи", callback_data="adm_users"),
         InlineKeyboardButton("🏆 Лидерборд",   callback_data="adm_leaders")],
        [InlineKeyboardButton("📊 Статистика",   callback_data="adm_stats"),
         InlineKeyboardButton("📖 Словарь",      callback_data="adm_words")],
        [InlineKeyboardButton("📣 Рассылка",     callback_data="adm_broadcast")],
    ]
    await update.message.reply_text(
        "🛠 *Админ-панель*\n\nВыбери раздел:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )


async def handle_admin_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Обрабатывает admin-колбэки. Возвращает True если колбэк был обработан здесь.
    """
    query = update.callback_query
    user_id = update.effective_user.id
    data = query.data

    if not data.startswith("adm_"):
        return False

    if not is_admin(user_id):
        await query.answer("⛔ Нет доступа!", show_alert=True)
        return True

    await query.answer()

    # ── Список пользователей ──────────────────────────────────────────────────
    if data == "adm_users":
        users = db.get_all_users()
        count = len(users)
        lines = [f"👥 *Пользователи ({count}):*\n"]
        for uid, d in list(users.items())[:20]:
            uname = f"@{d['username']}" if d.get("username") else f"id={uid}"
            lines.append(
                f"• *{d['name']}* ({uname}) — {d.get('total_score',0)} очков, "
                f"{d.get('games',0)} игр, последний: {d.get('last_seen','?')[:10]}"
            )
        if count > 20:
            lines.append(f"\n_...и ещё {count - 20} пользователей_")
        await query.message.reply_text("\n".join(lines), parse_mode="Markdown")

    # ── Лидерборд ─────────────────────────────────────────────────────────────
    elif data == "adm_leaders":
        top = db.get_leaderboard(15)
        medals = ["🥇","🥈","🥉"]
        lines = ["🏆 *Топ игроков:*\n"]
        for i, (uid, d) in enumerate(top):
            m = medals[i] if i < 3 else f"{i+1}."
            lines.append(
                f"{m} *{d['name']}* — {d['total_score']} очков "
                f"(серия: {d.get('best_streak',0)}, игр: {d.get('games',0)})"
            )
        if not top:
            lines.append("Пока никто не играл.")
        await query.message.reply_text("\n".join(lines), parse_mode="Markdown")

    # ── Общая статистика ──────────────────────────────────────────────────────
    elif data == "adm_stats":
        users = db.get_all_users()
        total_users = len(users)
        total_games = sum(d.get("games", 0) for d in users.values())
        total_score = sum(d.get("total_score", 0) for d in users.values())
        best = max(users.values(), key=lambda d: d.get("best_streak", 0), default={})
        ws = word_loader.stats()
        await query.message.reply_text(
            f"📊 *Общая статистика*\n\n"
            f"👥 Пользователей: *{total_users}*\n"
            f"🎮 Сыграно игр: *{total_games}*\n"
            f"🏅 Всего очков: *{total_score}*\n"
            f"🔥 Рекорд серии: *{best.get('best_streak', 0)}* ({best.get('name', '?')})\n\n"
            f"📖 Слов в словаре: *{ws['total']}*",
            parse_mode="Markdown"
        )

    # ── Статистика словаря ────────────────────────────────────────────────────
    elif data == "adm_words":
        ws = word_loader.stats()
        lines = [f"📖 *Словарь ({ws['total']} слов):*\n"]
        for letter, count in ws["by_letter"].items():
            lines.append(f"  `{letter.upper()}` — {count} слов")
        await query.message.reply_text("\n".join(lines), parse_mode="Markdown")

    # ── Рассылка: запрос текста ───────────────────────────────────────────────
    elif data == "adm_broadcast":
        ctx.user_data["waiting_broadcast"] = True
        await query.message.reply_text(
            "📣 *Рассылка*\n\n"
            "Напиши текст сообщения которое разослать всем пользователям.\n"
            "Для отмены напиши /cancel",
            parse_mode="Markdown"
        )

    return True


@admin_only
async def cmd_users(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/users — количество пользователей"""
    count = db.get_user_count()
    await update.message.reply_text(
        f"👥 Всего пользователей бота: *{count}*",
        parse_mode="Markdown"
    )


@admin_only
async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/broadcast <текст> — разослать всем"""
    text = " ".join(ctx.args)
    if not text:
        await update.message.reply_text(
            "Использование: /broadcast Ваш текст\n"
            "Или нажми кнопку 📣 Рассылка в /admin"
        )
        return
    await do_broadcast(update, ctx, text)


async def do_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE, text: str):
    """Выполняет рассылку всем пользователям."""
    user_ids = db.get_all_user_ids()
    sent = 0
    failed = 0
    status_msg = await update.message.reply_text(
        f"📣 Начинаю рассылку для *{len(user_ids)}* пользователей...",
        parse_mode="Markdown"
    )

    for uid in user_ids:
        try:
            await ctx.bot.send_message(
                uid,
                f"📣 *Сообщение от администратора:*\n\n{text}",
                parse_mode="Markdown"
            )
            sent += 1
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"📣 *Рассылка завершена!*\n\n"
        f"✅ Доставлено: *{sent}*\n"
        f"❌ Ошибок: *{failed}*",
        parse_mode="Markdown"
    )
    log.info(f"Рассылка: {sent} доставлено, {failed} ошибок")
