"""Схема рассадки на экзамене. Запуск: streamlit run app.py"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from data import load_categories, load_sheet, mtime, students_from
from seating import (
    CapacityError,
    Layout,
    Order,
    Seat,
    SeatMode,
    Student,
    assign,
    build_layout,
    display_name,
    order_students,
)

OCCUPIED_COLOR = "#E5484D"
FREE_COLOR = "#9AA0A6"
UNUSED_COLOR = "rgba(154, 160, 166, 0.45)"
DESK_FILL = "rgba(128, 128, 128, 0.10)"
DESK_LINE = "rgba(128, 128, 128, 0.35)"


def seat_figure(layout: Layout, seating: dict[Seat, Student], initials_only: bool) -> go.Figure:
    fig = go.Figure()

    # Парты — подложка под стульями.
    for r in range(1, layout.rows + 1):
        y = (r - 1) * config.ROW_PITCH
        for x0, x1 in layout.desk_spans:
            fig.add_shape(
                type="rect", x0=x0 - 0.45, x1=x1 + 0.45, y0=y - 0.45, y1=y + 0.45,
                fillcolor=DESK_FILL, line=dict(color=DESK_LINE, width=1), layer="below",
            )
        fig.add_annotation(x=-1.1, y=y, text=str(r), showarrow=False, font=dict(size=11, color=FREE_COLOR))

    unused = [s for s in layout.seats if not s.usable]
    free = [s for s in layout.seats if s.usable and s not in seating]
    taken = [s for s in layout.seats if s in seating]

    def where(seats: list[Seat]) -> list[list[int]]:
        return [[s.row, s.number] for s in seats]

    fig.add_trace(go.Scatter(
        x=[s.x for s in unused], y=[s.y for s in unused], mode="markers", name="Не используется",
        marker=dict(size=9, color="rgba(0,0,0,0)", line=dict(color=UNUSED_COLOR, width=1.2)),
        hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=[s.x for s in free], y=[s.y for s in free], mode="markers", name="Свободно",
        marker=dict(size=14, color=FREE_COLOR),
        customdata=where(free),
        hovertemplate="Свободно<br>Ряд %{customdata[0]}, место %{customdata[1]}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=[s.x for s in taken], y=[s.y for s in taken], mode="markers", name="Занято",
        marker=dict(size=14, color=OCCUPIED_COLOR),
        text=[display_name(seating[s].fio, initials_only) for s in taken],
        customdata=where(taken),
        hovertemplate="<b>%{text}</b><br>Ряд %{customdata[0]}, место %{customdata[1]}<extra></extra>",
    ))

    # Доска над первым рядом.
    x_min = layout.desk_spans[0][0] - 0.45
    x_max = layout.desk_spans[-1][1] + 0.45
    board_y = -1.3
    fig.add_shape(type="line", x0=x_min, x1=x_max, y0=board_y, y1=board_y, line=dict(color=FREE_COLOR, width=4))
    fig.add_annotation(x=(x_min + x_max) / 2, y=board_y - 0.6, text="Доска", showarrow=False,
                       font=dict(size=12, color=FREE_COLOR))

    y_max = (layout.rows - 1) * config.ROW_PITCH + 1
    hidden = dict(showgrid=False, zeroline=False, showticklabels=False, title=None)
    fig.update_xaxes(range=[-1.8, x_max + 0.8], **hidden)
    # Ряд 1 сверху: ось Y развёрнута; квадратные пропорции через scaleanchor.
    fig.update_yaxes(range=[y_max, board_y - 1.3], scaleanchor="x", scaleratio=1, **hidden)
    fig.update_layout(
        height=int(120 + 30 * (y_max - board_y + 1.3)),
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
        hoverlabel=dict(font_size=14),
        dragmode=False,
    )
    return fig


def main() -> None:
    st.set_page_config(page_title="Рассадка на экзамене", page_icon="🪑", layout="centered")

    with st.sidebar:
        st.header("Аудитория")
        room_name = st.radio("Аудитория", list(config.ROOMS), label_visibility="collapsed")
        st.divider()
        st.subheader("Правило рассадки")
        mode = st.selectbox("Какие места занимать", list(SeatMode), format_func=lambda m: m.value)
        order = st.selectbox("Порядок студентов", list(Order), format_func=lambda o: o.value)
        by_category = st.checkbox(
            "Учитывать цветовые метки", value=True,
            help="Красные — первые ряды, затем жёлтые, нейтральные, зелёные — в конце.",
        )

    room = config.ROOMS[room_name]
    st.title(f"Аудитория {room.name}")

    if not config.SEATING_XLSX.exists():
        st.error(f"Не найден файл с рассадкой: {config.SEATING_XLSX.name}")
        st.stop()
    df = load_sheet(str(config.SEATING_XLSX), room.sheet, mtime(config.SEATING_XLSX))

    categories = {}
    if config.LISTS_XLSX.exists():
        categories = load_categories(str(config.LISTS_XLSX), mtime(config.LISTS_XLSX))
    elif by_category:
        st.warning(f"Нет файла {config.LISTS_XLSX.name} — цветовые метки не учитываются.")

    students, unmatched = students_from(df, categories)
    layout = build_layout(room, mode, len(students))
    capacity = sum(s.usable for s in layout.seats)

    try:
        seating = assign(layout, order_students(students, order, by_category))
    except CapacityError as e:
        st.error(
            f"Не хватает мест в аудитории {room.name}: студентов **{e.students}**, "
            f"мест **{e.capacity}** (не хватает {e.students - e.capacity}). "
            "Увеличьте число рядов в config.py или выберите другой режим мест."
        )
        st.stop()

    c1, c2, c3 = st.columns(3)
    c1.metric("Всего мест", capacity)
    c2.metric("Занято", len(seating))
    c3.metric("Свободно", capacity - len(seating))
    st.caption(f"Рядов: {layout.rows} · стульев в аудитории: {len(layout.seats)}")

    st.plotly_chart(
        seat_figure(layout, seating, config.SHOW_INITIALS_ONLY),
        width="stretch",
        config={"displayModeBar": False},
    )

    with st.expander("Список по местам"):
        table = pd.DataFrame(
            [
                {
                    "Ряд": seat.row,
                    "Место": seat.number,
                    "Студент": display_name(student.fio, config.SHOW_INITIALS_ONLY),
                    "Перцентиль": "ИУП" if student.percentile is None else f"{student.percentile:g}",
                }
                for seat, student in seating.items()
            ]
        )
        st.dataframe(table, hide_index=True, width="stretch")

    if unmatched:
        with st.expander(f"Нет в {config.LISTS_XLSX.name}: {len(unmatched)} (считаются нейтральными)"):
            st.write("\n".join(f"- {display_name(f, config.SHOW_INITIALS_ONLY)}" for f in unmatched))


main()
