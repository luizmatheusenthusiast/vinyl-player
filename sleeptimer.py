"""Timer de dormir: depois de N minutos a música some devagar (fade) e para.

Lógica pura (sem Qt): quem chama passa o horário atual, então dá para testar sem esperar.
"""

from __future__ import annotations

import time

FADE_SECONDS = 15.0  # nos últimos segundos o volume vai baixando até zero


class SleepTimer:
    def __init__(self):
        self._end: float | None = None

    @property
    def active(self) -> bool:
        return self._end is not None

    def start(self, minutes: float, now: float | None = None):
        now = time.monotonic() if now is None else now
        self._end = now + minutes * 60.0

    def cancel(self):
        self._end = None

    def remaining(self, now: float | None = None) -> float:
        """Segundos que faltam (0 se desligado ou já acabou)."""
        if self._end is None:
            return 0.0
        now = time.monotonic() if now is None else now
        return max(0.0, self._end - now)

    def expired(self, now: float | None = None) -> bool:
        return self._end is not None and self.remaining(now) <= 0.0

    def volume_factor(self, now: float | None = None) -> float:
        """1.0 = volume normal; cai até 0.0 nos últimos FADE_SECONDS."""
        if self._end is None:
            return 1.0
        left = self.remaining(now)
        return 1.0 if left >= FADE_SECONDS else max(0.0, left / FADE_SECONDS)

    def label(self, now: float | None = None) -> str:
        if not self.active:
            return ""
        s = int(self.remaining(now) + 0.999)
        return f"{s // 60}:{s % 60:02d}"
