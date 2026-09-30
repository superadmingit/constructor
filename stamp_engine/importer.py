"""Разбор выгрузки со страницы данных цеха (формат stamp-shop-data/1): прессы, станки, закалка.

Детали через эту страницу больше не заводятся: у каждой детали свой поток ввода (модель в stamp_engine.sheet).
"""
from __future__ import annotations

FORMAT = "stamp-shop-data/1"


def shop_dict(export: dict) -> dict:
    """Часть выгрузки, которую читает Shop.from_dict. Принимает и выгрузку страницы, и готовый JSON цеха."""
    if export.get("format") not in (None, FORMAT):
        raise ValueError(f"Неизвестный формат выгрузки: {export.get('format')!r}")
    return export.get("shop", export)
