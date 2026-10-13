"""Настройки приложения: файлы данных, устройство аудиторий, приватность.

Логика рассадки (seating.py) ничего не знает о конкретных аудиториях —
всё, что относится к помещениям, задаётся здесь.
"""

from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).parent

# Файл рассадки: по листу на аудиторию, колонки «№ | ФИО | Перцентиль | Примечание».
SEATING_XLSX = BASE_DIR / "Экзамен_рассадка_по_аудиториям.xlsx"
# Общий список с цветовой разметкой (заливка ячейки «Фамилия»). Необязателен:
# если файла нет, все студенты считаются нейтральными.
LISTS_XLSX = BASE_DIR / "Списки.xlsx"

# Приватность: True → в подсказке «Фамилия И.» вместо «Фамилия Имя».
SHOW_INITIALS_ONLY = False


@dataclass(frozen=True)
class Desk:
    """Парта в ряду (слева направо).

    seats — сколько стульев за партой;
    use   — индексы стульев (с 0, слева направо), на которые сажаем
            при режиме «по схеме аудитории».
    """

    seats: int
    use: tuple[int, ...]


@dataclass(frozen=True)
class Room:
    """Аудитория: одинаковые ряды парт, ряд 1 — у доски.

    rows=None — подобрать число рядов автоматически, чтобы все поместились,
    и добавить extra_rows пустых рядов сзади.
    """

    name: str
    sheet: str  # имя листа в SEATING_XLSX
    desks: tuple[Desk, ...]
    rows: int | None
    extra_rows: int = 0


# Боковые двойные парты: сажаем на стул у стены.
_LEFT_PAIR = Desk(seats=2, use=(0,))
_RIGHT_PAIR = Desk(seats=2, use=(1,))
# Центральная парта на 4 места: крайние стулья.
_MIDDLE_FOUR = Desk(seats=4, use=(0, 3))

ROOMS: dict[str, Room] = {
    "520": Room(
        name="520",
        sheet="520",
        desks=(_LEFT_PAIR, _MIDDLE_FOUR, _RIGHT_PAIR),
        rows=7,
    ),
    "523-524": Room(
        name="523-524",
        sheet="523-524",
        # TODO: уточнить, на какой стул центральной двойной парты сажать (сейчас левый).
        desks=(_LEFT_PAIR, Desk(seats=2, use=(0,)), _RIGHT_PAIR),
        # Реально рядов ~15; берём столько, чтобы поместились все, + 2 пустых для ориентира.
        rows=None,
        extra_rows=2,
    ),
    "531": Room(
        name="531",
        sheet="531",
        desks=(_LEFT_PAIR, _MIDDLE_FOUR, _RIGHT_PAIR),
        # TODO: уточнить число рядов. Было «около 8», но 8 × 4 = 32 < 33 студентов.
        rows=9,
    ),
}

# Геометрия отрисовки (в «стульях»): шаг между стульями = 1.
AISLE_WIDTH = 1.6  # проход между партами
ROW_PITCH = 1.6  # расстояние между рядами
