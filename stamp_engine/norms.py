"""Загрузка норм цеха (norms/shop_norms.yaml).

Код берёт ВСЕ коэффициенты отсюда. Если нормы не утверждены
(meta.status != approved), результаты помечаются как черновик."""
from __future__ import annotations

from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "norms" / "shop_norms.yaml"


class Norms:
    def __init__(self, data: dict):
        self.data = data

    @staticmethod
    def load(path: str | Path = DEFAULT_PATH) -> "Norms":
        with open(path, encoding="utf-8") as f:
            return Norms(yaml.safe_load(f))

    @property
    def approved(self) -> bool:
        return self.data.get("meta", {}).get("status") == "approved"

    def item(self, dotted: str) -> dict:
        node = self.data
        for key in dotted.split("."):
            if key not in node:
                raise KeyError(f"Нет нормы {dotted!r} в shop_norms.yaml")
            node = node[key]
        return node

    def get(self, dotted: str) -> float:
        node = self.item(dotted)
        return node["value"] if isinstance(node, dict) and "value" in node else node

    def material(self, group: str) -> dict:
        mats = self.data["materials"]
        if group not in mats:
            raise KeyError(f"Группа материала {group!r} не описана в нормах. "
                           f"Есть: {', '.join(mats)}")
        m = mats[group]
        return {k: (v["value"] if isinstance(v, dict) and "value" in v else v) for k, v in m.items()}

    def x_for(self, r_over_s: float) -> float:
        """Коэффициент нейтрального слоя x (K-фактор) по r/S, линейная интерполяция."""
        table = self.get("bending.x_table")
        if r_over_s <= table[0][0]:
            return table[0][1]
        if r_over_s >= table[-1][0]:
            return table[-1][1]
        for (r0, x0), (r1, x1) in zip(table[:-1], table[1:]):
            if r0 <= r_over_s <= r1:
                return x0 + (x1 - x0) * (r_over_s - r0) / (r1 - r0)
        return table[-1][1]
