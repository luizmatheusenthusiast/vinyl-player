"""Ordem de reprodução: aleatório, repetir, próxima e anterior.

Não depende do Qt, então pode ser testado sozinho. Só trabalha com números (a posição de cada
música na lista); quem toca de verdade é a janela principal.
"""

from __future__ import annotations

import random
from enum import Enum


class Repeat(Enum):
    OFF = "off"  # toca a lista uma vez e para
    ALL = "all"  # quando a lista acaba, recomeça
    ONE = "one"  # repete a mesma música


_NEXT_REPEAT = {Repeat.OFF: Repeat.ALL, Repeat.ALL: Repeat.ONE, Repeat.ONE: Repeat.OFF}
HISTORY_LIMIT = 300


class PlayQueue:
    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        self.count = 0
        self.current = -1
        self.shuffle = False
        self.repeat = Repeat.OFF
        self._queue: list[int] = []    # no aleatório: o que ainda não tocou nesta rodada
        self._history: list[int] = []  # o que já tocou (para o botão "voltar" no aleatório)

    # ---------------------------------------------------------------- configuração
    def reset(self, count: int):
        """Nova lista de músicas."""
        self.count = count
        self.current = -1
        self._history.clear()
        self._queue.clear()
        if self.shuffle:
            self._refill()

    def set_shuffle(self, enabled: bool):
        self.shuffle = enabled
        self._queue.clear()
        if enabled:
            self._refill()

    def cycle_repeat(self) -> Repeat:
        """Desligado -> toda a lista -> só esta música -> desligado."""
        self.repeat = _NEXT_REPEAT[self.repeat]
        return self.repeat

    def pick_start(self) -> int:
        """Por onde começar uma lista nova: a primeira música, ou uma qualquer no aleatório."""
        if self.count == 0:
            return -1
        return self.rng.randrange(self.count) if self.shuffle else 0

    # ---------------------------------------------------------------- navegação
    def jump_to(self, index: int):
        """O usuário escolheu uma música (ou a lista começou nela)."""
        if not 0 <= index < self.count:
            return
        if self.current >= 0 and self.current != index:
            self._push_history(self.current)
        self.current = index
        if index in self._queue:
            self._queue.remove(index)

    def next(self, auto: bool = False) -> int | None:
        """Próxima música. `auto=True` quando a música acabou sozinha; devolve None para parar."""
        if self.count == 0:
            return None
        if auto and self.repeat is Repeat.ONE and self.current >= 0:
            return self.current

        if self.shuffle:
            if not self._queue:
                if auto and self.repeat is Repeat.OFF:
                    return None  # tocou todas as músicas uma vez: acabou
                self._refill()
            target = self._queue.pop(0) if self._queue else max(self.current, 0)
        else:
            target = self.current + 1
            if target >= self.count:
                if auto and self.repeat is Repeat.OFF:
                    return None  # fim da lista
                target = 0  # apertando "próxima" no fim da lista, volta ao começo

        if self.current >= 0 and self.current != target:
            self._push_history(self.current)
        self.current = target
        return target

    def previous(self) -> int | None:
        """Música anterior. None = não há anterior (quem chamou deve só recomeçar a música)."""
        if self.count == 0:
            return None

        if self.shuffle:
            if not self._history:
                return None
            target = self._history.pop()
            if self.current >= 0 and self.current != target:
                self._queue.insert(0, self.current)  # "próxima" depois de "voltar" retorna a ela
            self.current = target
            return target

        target = (self.current - 1) % self.count if self.current >= 0 else self.count - 1
        self.current = target
        return target

    # ---------------------------------------------------------------- internos
    def _refill(self):
        self._queue = [i for i in range(self.count) if i != self.current]
        self.rng.shuffle(self._queue)

    def _push_history(self, index: int):
        self._history.append(index)
        if len(self._history) > HISTORY_LIMIT:
            del self._history[0]
