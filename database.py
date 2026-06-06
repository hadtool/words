# ╔══════════════════════════════════════════════════╗
# ║           БАЗА ДАННЫХ — database.py              ║
# ║  Хранит пользователей и лидерборд в JSON файле  ║
# ╚══════════════════════════════════════════════════╝

import json
import os
import logging
from datetime import datetime
from config import DB_FILE

log = logging.getLogger(__name__)

_db = {
    "users": {},       # user_id -> {name, username, first_seen, last_seen, total_score, games, best_streak}
    "leaderboard": {}, # user_id -> {total_score, games, best_streak}
}


def _save():
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(_db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"Ошибка сохранения БД: {e}")


def load():
    global _db
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                _db = json.load(f)
            log.info(f"БД загружена: {len(_db['users'])} пользователей")
        except Exception as e:
            log.error(f"Ошибка загрузки БД: {e}")
    else:
        log.info("БД не найдена, создаём новую")
        _save()


def register_user(user_id: int, name: str, username: str | None):
    uid = str(user_id)
    now = datetime.now().isoformat()
    if uid not in _db["users"]:
        _db["users"][uid] = {
            "name": name,
            "username": username or "",
            "first_seen": now,
            "last_seen": now,
            "total_score": 0,
            "games": 0,
            "best_streak": 0,
        }
        log.info(f"Новый пользователь: {name} (id={user_id})")
    else:
        _db["users"][uid]["name"] = name
        _db["users"][uid]["username"] = username or ""
        _db["users"][uid]["last_seen"] = now
    _save()


def update_score(user_id: int, score: int, streak: int):
    uid = str(user_id)
    if uid not in _db["users"]:
        return
    _db["users"][uid]["total_score"] += score
    _db["users"][uid]["games"] += 1
    _db["users"][uid]["best_streak"] = max(
        _db["users"][uid].get("best_streak", 0), streak
    )
    _save()


def get_all_user_ids() -> list[int]:
    return [int(uid) for uid in _db["users"].keys()]


def get_user_count() -> int:
    return len(_db["users"])


def get_user(user_id: int) -> dict | None:
    return _db["users"].get(str(user_id))


def get_leaderboard(top: int = 10) -> list[tuple]:
    """Возвращает топ N пользователей по total_score."""
    users = [
        (uid, d) for uid, d in _db["users"].items() if d.get("total_score", 0) > 0
    ]
    users.sort(key=lambda x: x[1]["total_score"], reverse=True)
    return users[:top]


def get_all_users() -> dict:
    return _db["users"]
