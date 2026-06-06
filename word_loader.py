# ╔══════════════════════════════════════════════════╗
# ║           ЗАГРУЗЧИК СЛОВ — word_loader.py        ║
# ║  Читает файлы words/a.txt, words/b.txt и т.д.   ║
# ╚══════════════════════════════════════════════════╝

import os
import random
import logging
from collections import defaultdict
from config import WORDS_DIR, MIN_WORD_LEN

log = logging.getLogger(__name__)

# Словарь: буква -> список слов
_index: dict[str, list[str]] = defaultdict(list)
_all_words: set[str] = set()


def load_words() -> int:
    """Загружает все слова из файлов words/*.txt. Возвращает общее кол-во слов."""
    _index.clear()
    _all_words.clear()

    if not os.path.isdir(WORDS_DIR):
        log.error(f"Папка '{WORDS_DIR}' не найдена!")
        return 0

    total = 0
    for filename in sorted(os.listdir(WORDS_DIR)):
        if not filename.endswith(".txt"):
            continue
        letter = filename[0].lower()
        filepath = os.path.join(WORDS_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                words = [
                    line.strip().lower()
                    for line in f
                    if line.strip().isalpha() and len(line.strip()) >= MIN_WORD_LEN
                ]
            _index[letter].extend(words)
            _all_words.update(words)
            total += len(words)
            log.info(f"Загружен {filename}: {len(words)} слов")
        except Exception as e:
            log.error(f"Ошибка чтения {filename}: {e}")

    log.info(f"Итого загружено слов: {total}")
    return total


def is_valid(word: str) -> bool:
    """Проверяет, есть ли слово в словаре."""
    return word.lower() in _all_words


def get_word(letter: str, used: set) -> str | None:
    """Возвращает случайное слово на букву letter, не из used. None если нет."""
    candidates = [w for w in _index.get(letter.lower(), []) if w not in used]
    return random.choice(candidates) if candidates else None


def get_hint(letter: str, used: set) -> str | None:
    """Возвращает случайное слово-подсказку (первые 2 буквы + ___)."""
    word = get_word(letter, used)
    if not word:
        return None
    return word[:2] + "_" * (len(word) - 2), len(word)


def stats() -> dict:
    """Статистика словаря."""
    return {
        "total": len(_all_words),
        "by_letter": {k: len(v) for k, v in sorted(_index.items())},
    }
