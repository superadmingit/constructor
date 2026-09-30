"""Плоская геометрия развёртки.

Контур задаётся как в DXF LWPOLYLINE: список вершин [x, y, bulge].
bulge — дуга от этой вершины к следующей: bulge = tan(угол/4),
знак «+» — дуга против часовой стрелки, «−» — по часовой, 0 — прямая.
Все размеры в мм.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

EPS = 1e-6


@dataclass(frozen=True)
class Segment:
    x0: float
    y0: float
    x1: float
    y1: float
    bulge: float = 0.0

    @property
    def is_arc(self) -> bool:
        return abs(self.bulge) > EPS

    def arc(self):
        """Центр, радиус, начальный угол, угол дуги (со знаком)."""
        theta = 4.0 * math.atan(self.bulge)
        dx, dy = self.x1 - self.x0, self.y1 - self.y0
        chord = math.hypot(dx, dy)
        r = chord * (1 + self.bulge ** 2) / (4 * abs(self.bulge))
        mx, my = (self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2
        h = math.sqrt(max(r * r - (chord / 2) ** 2, 0.0))
        if abs(theta) > math.pi:            # дуга больше полуокружности
            h = -h
        nx, ny = -dy / chord, dx / chord     # левая нормаль к хорде
        sign = 1.0 if self.bulge > 0 else -1.0
        cx, cy = mx + sign * nx * h, my + sign * ny * h
        a0 = math.atan2(self.y0 - cy, self.x0 - cx)
        return cx, cy, r, a0, theta

    def length(self) -> float:
        if not self.is_arc:
            return math.hypot(self.x1 - self.x0, self.y1 - self.y0)
        _, _, r, _, theta = self.arc()
        return abs(r * theta)

    def points(self, n_arc: int = 24):
        """Точки сегмента (дуга разбита на n_arc частей), без последней точки."""
        if not self.is_arc:
            return [(self.x0, self.y0)]
        cx, cy, r, a0, theta = self.arc()
        return [(cx + r * math.cos(a0 + theta * i / n_arc),
                 cy + r * math.sin(a0 + theta * i / n_arc)) for i in range(n_arc)]


class Contour:
    """Замкнутый контур развёртки."""

    def __init__(self, vertices):
        if len(vertices) < 3:
            raise ValueError("Контур: нужно минимум 3 вершины")
        self.vertices = [(float(v[0]), float(v[1]), float(v[2]) if len(v) > 2 else 0.0)
                         for v in vertices]
        n = len(self.vertices)
        self.segments = [Segment(self.vertices[i][0], self.vertices[i][1],
                                 self.vertices[(i + 1) % n][0], self.vertices[(i + 1) % n][1],
                                 self.vertices[i][2]) for i in range(n)]

    # --- базовые величины -------------------------------------------------
    def polygon(self, n_arc: int = 24):
        pts = []
        for s in self.segments:
            pts.extend(s.points(n_arc))
        return pts

    def perimeter(self) -> float:
        return sum(s.length() for s in self.segments)

    def area(self) -> float:
        pts = self.polygon(64)
        a = 0.0
        for i in range(len(pts)):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % len(pts)]
            a += x0 * y1 - x1 * y0
        return abs(a) / 2

    def bbox(self):
        pts = self.polygon(64)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)

    def is_rectangle(self, tol: float = 0.01) -> bool:
        """Контур — прямоугольник (такую заготовку режут на гильотине без штампа)."""
        return abs(self.area() - _bbox_area(self.bbox())) < tol * max(1.0, self.area()) and \
            not any(s.is_arc for s in self.segments)

    # --- для резки уступов из прямоугольной заготовки -----------------------
    def segments_off_bbox(self, tol: float = 1e-3):
        """Сегменты, не лежащие на сторонах описанного прямоугольника.

        Если заготовку режут на гильотине прямоугольником, штамп режет
        только эти участки (уступы, скосы, скругления)."""
        x0, y0, x1, y1 = self.bbox()
        out = []
        for s in self.segments:
            if s.is_arc:
                out.append(s)
                continue
            on_edge = ((abs(s.x0 - x0) < tol and abs(s.x1 - x0) < tol) or
                       (abs(s.x0 - x1) < tol and abs(s.x1 - x1) < tol) or
                       (abs(s.y0 - y0) < tol and abs(s.y1 - y0) < tol) or
                       (abs(s.y0 - y1) < tol and abs(s.y1 - y1) < tol))
            if not on_edge:
                out.append(s)
        return out

    # --- пересечения с линией гиба ----------------------------------------
    def chord_on_ray(self, p0, u):
        """Отрезки прямой p0 + t·u (u — единичный вектор) внутри контура: список (t0, t1)."""
        pts = self.polygon(64)
        nx, ny = -u[1], u[0]
        off = 1e-7
        hits = []
        for i in range(len(pts)):
            (ax, ay), (bx, by) = pts[i], pts[(i + 1) % len(pts)]
            da = (ax - p0[0]) * nx + (ay - p0[1]) * ny - off
            db = (bx - p0[0]) * nx + (by - p0[1]) * ny - off
            if da * db < 0:
                k = da / (da - db)
                qx, qy = ax + k * (bx - ax), ay + k * (by - ay)
                hits.append((qx - p0[0]) * u[0] + (qy - p0[1]) * u[1])
        hits.sort()
        return [(hits[i], hits[i + 1]) for i in range(0, len(hits) - 1, 2)]

    def chord_on_line(self, axis: str, pos: float):
        """Отрезки прямой x=pos (axis='x') или y=pos (axis='y') внутри контура.

        Возвращает список (от, до) по второй координате. Нужно, чтобы узнать
        реальную длину линии гиба на заготовке."""
        pts = self.polygon(64)
        pos = pos + 1e-7          # чтобы линия не прошла ровно через вершину
        hits = []
        for i in range(len(pts)):
            (ax, ay), (bx, by) = pts[i], pts[(i + 1) % len(pts)]
            if axis == "x":
                a, b, ua, ub = ax, bx, ay, by
            else:
                a, b, ua, ub = ay, by, ax, bx
            if (a - pos) * (b - pos) < 0:
                t = (pos - a) / (b - a)
                hits.append(ua + t * (ub - ua))
        hits.sort()
        return [(hits[i], hits[i + 1]) for i in range(0, len(hits) - 1, 2)]


def _bbox_area(bb):
    return (bb[2] - bb[0]) * (bb[3] - bb[1])


def segments_length(segments) -> float:
    return sum(s.length() for s in segments)


def segments_centroid(segments):
    """Центр тяжести линий реза (центр давления при резке)."""
    sx = sy = total = 0.0
    for s in segments:
        pts = s.points(24) + [(s.x1, s.y1)]
        for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
            l = math.hypot(bx - ax, by - ay)
            sx += l * (ax + bx) / 2
            sy += l * (ay + by) / 2
            total += l
    if total < EPS:
        return 0.0, 0.0
    return sx / total, sy / total
