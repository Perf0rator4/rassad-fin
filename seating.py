"""Чистая логика рассадки: геометрия мест, порядок студентов, распределение.

Без Streamlit — чтобы можно было проверять отдельно.
"""

import math
from dataclasses import dataclass
from enum import Enum

from config import AISLE_WIDTH, ROW_PITCH, Room


class SeatMode(Enum):
    """Какие стулья в ряду используются."""

    SCHEME = "По схеме аудитории"
    EVERY_OTHER = "Через одно место"
    CONSECUTIVE = "Подряд, все места"


class Order(Enum):
    """Базовый порядок студентов (поверх него — приоритет по цвету, если включён)."""

    RATING = "По рейтингу (перцентилю)"
    ALPHABET = "По алфавиту"
    SHEET = "Как в листе"


class Category(Enum):
    """Цветовая метка из «Списки.xlsx». value — порядок заполнения от доски."""

    RED = 0  # доказанное списывание — первые ряды
    YELLOW = 1  # подозрение — следующие ряды
    NONE = 2  # нейтральные — остальные места
    GREEN = 3  # добросовестные — в конец


@dataclass(frozen=True)
class Student:
    fio: str
    percentile: float | None  # None у студентов ИУП
    category: Category
    sheet_pos: int  # позиция в листе, для порядка «как в листе»


@dataclass(frozen=True)
class Seat:
    row: int  # 1 — у доски
    number: int  # номер стула в ряду, слева направо, с 1
    x: float
    y: float
    usable: bool  # можно ли сажать при выбранном режиме


@dataclass(frozen=True)
class Layout:
    seats: list[Seat]
    rows: int
    desk_spans: list[tuple[float, float]]  # x-границы парт (одинаковы для всех рядов)


class CapacityError(Exception):
    def __init__(self, students: int, capacity: int) -> None:
        super().__init__(f"Студентов {students}, а мест {capacity}")
        self.students = students
        self.capacity = capacity


def _row_template(room: Room, mode: SeatMode) -> tuple[list[tuple[float, bool]], list[tuple[float, float]]]:
    """Стулья одного ряда: (x, usable) и x-границы парт."""
    chairs: list[tuple[float, bool]] = []
    spans: list[tuple[float, float]] = []
    x = 0.0
    for desk in room.desks:
        start = x
        for i in range(desk.seats):
            if mode is SeatMode.SCHEME:
                usable = i in desk.use
            elif mode is SeatMode.EVERY_OTHER:
                usable = len(chairs) % 2 == 0  # чётные по сквозной нумерации ряда
            else:
                usable = True
            chairs.append((x, usable))
            x += 1.0
        spans.append((start, x - 1.0))
        x += AISLE_WIDTH  # после парты — проход
    return chairs, spans


def build_layout(room: Room, mode: SeatMode, n_students: int) -> Layout:
    chairs, spans = _row_template(room, mode)
    per_row = sum(usable for _, usable in chairs)
    if room.rows is not None:
        rows = room.rows
    else:
        # Авто: минимум рядов, чтобы все сели, плюс пустые ряды «для ориентира».
        rows = max(1, math.ceil(n_students / per_row)) + room.extra_rows if per_row else 0
    seats = [
        Seat(row=r, number=i + 1, x=x, y=(r - 1) * ROW_PITCH, usable=usable)
        for r in range(1, rows + 1)
        for i, (x, usable) in enumerate(chairs)
    ]
    return Layout(seats=seats, rows=rows, desk_spans=spans)


def order_students(students: list[Student], order: Order, by_category: bool) -> list[Student]:
    if order is Order.RATING:
        # ИУП (без перцентиля) — после всех остальных.
        key = lambda s: (s.percentile is None, s.percentile or 0.0, s.fio)  # noqa: E731
    elif order is Order.ALPHABET:
        key = lambda s: s.fio.replace("ё", "е").replace("Ё", "Е")  # noqa: E731
    else:
        key = lambda s: s.sheet_pos  # noqa: E731
    result = sorted(students, key=key)
    if by_category:
        result = sorted(result, key=lambda s: s.category.value)  # стабильная сортировка
    return result


def assign(layout: Layout, students: list[Student]) -> dict[Seat, Student]:
    """Сажает студентов по порядку: ряд 1 → дальше, в ряду слева направо.

    Если мест не хватает — CapacityError, список не обрезается.
    """
    free = [s for s in layout.seats if s.usable]  # уже в нужном порядке
    if len(students) > len(free):
        raise CapacityError(len(students), len(free))
    return dict(zip(free, students))


def display_name(fio: str, initials_only: bool) -> str:
    """«Фамилия Имя» или «Фамилия И.»."""
    parts = fio.split()
    if len(parts) < 2:
        return fio
    surname, name = parts[0], parts[1]
    return f"{surname} {name[0]}." if initials_only else f"{surname} {name}"
