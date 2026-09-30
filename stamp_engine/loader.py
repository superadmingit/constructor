"""Загрузка детали в любом из двух видов.

1. Модель листовой детали (есть ключ "base"): основание, полки, подсечки, отверстия в размерах гнутой детали.
   Развёртку строит stamp_engine.sheet. Так описывается любая новая деталь.
2. Готовая развёртка (есть ключ "blank"): контур заготовки, отверстия и линии гибов уже в плоских координатах
   (например, из DXF заказчика).
"""
from __future__ import annotations

from .models import Part
from .norms import Norms
from .sheet import to_part_dict, unfold


def part_dict(raw: dict, norms: Norms) -> dict:
    if "base" in raw:
        return to_part_dict(raw, unfold(raw, norms))
    if "blank" in raw:
        return raw
    raise ValueError("Деталь: нужен либо base (модель гнутой детали), либо blank (готовая развёртка).")


def load_part(raw: dict, norms: Norms) -> Part:
    return Part.from_dict(part_dict(raw, norms))
