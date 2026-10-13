"""Чтение xlsx (с кэшем Streamlit)."""

import re
from pathlib import Path

import openpyxl
import pandas as pd
import streamlit as st

from seating import Category, Student

# Цвет заливки ячейки «Фамилия» в Списки.xlsx → метка.
_FILL_TO_CATEGORY: dict[str, Category] = {
    "FFFF0000": Category.RED,
    "FFFFFF00": Category.YELLOW,
    "FF00FF00": Category.GREEN,
}


def normalize_fio(fio: str) -> str:
    """Ключ для сопоставления ФИО между файлами: регистр, ё/е, прочерк вместо отчества."""
    tokens = [t for t in re.split(r"\s+", fio.strip()) if t and t != "-"]
    return " ".join(tokens).lower().replace("ё", "е")


@st.cache_data
def load_categories(path: str, _mtime: float) -> dict[str, Category]:
    """ФИО (нормализованное) → метка. _mtime сбрасывает кэш при изменении файла."""
    ws = openpyxl.load_workbook(path, read_only=False).active
    result: dict[str, Category] = {}
    for row in ws.iter_rows(min_row=2):
        surname, name, patronymic = (c.value for c in row[1:4])
        if not surname:
            continue
        fio = " ".join(str(v) for v in (surname, name, patronymic) if v)
        fill = row[1].fill
        rgb = fill.fgColor.rgb if fill is not None and fill.fill_type else None
        result[normalize_fio(fio)] = _FILL_TO_CATEGORY.get(rgb, Category.NONE)
    return result


@st.cache_data
def load_sheet(path: str, sheet: str, _mtime: float) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet)
    missing = {"ФИО", "Перцентиль"} - set(df.columns)
    if missing:
        raise ValueError(f"На листе «{sheet}» нет колонок: {', '.join(sorted(missing))}")
    df = df.dropna(subset=["ФИО"])
    # «Примечание» служебное — на сайт не выводим.
    return df[["ФИО", "Перцентиль"]].reset_index(drop=True)


def students_from(df: pd.DataFrame, categories: dict[str, Category]) -> tuple[list[Student], list[str]]:
    """Студенты листа + список ФИО, которых нет в Списки.xlsx (считаются нейтральными)."""
    students: list[Student] = []
    unmatched: list[str] = []
    for pos, (fio, pct) in enumerate(zip(df["ФИО"], df["Перцентиль"])):
        fio = " ".join(str(fio).split())
        key = normalize_fio(fio)
        if categories and key not in categories:
            unmatched.append(fio)
        students.append(
            Student(
                fio=fio,
                percentile=None if pd.isna(pct) else float(pct),
                category=categories.get(key, Category.NONE),
                sheet_pos=pos,
            )
        )
    return students, unmatched


def mtime(path: Path) -> float:
    return path.stat().st_mtime
