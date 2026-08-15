"""Salience monitor — the switch of the reverie loop (DREAM).

The default-mode drift must not be judged continuously: executive control
kills reverie. The salience network decides *what deserves attention*.
This monitor watches the drift's own telemetry — cheap, local, no model
calls — and fires an event when the stream does something internally
notable:

- jump:        the context EMA moved far from where it was M tokens ago —
               the thought changed region.
- crystallize: entropy dropped after a stretch of wandering — the model
               settled on something after being unsettled.
- recurrence:  the current context is close to a region visited long ago
               (and not recently) — the loop closed on an old theme.

Only on an event does the Review (judge) run. Events carry the window they
refer to, so the reviewer can look at exactly the stretch that fired.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import re

import numpy as np


@dataclass
class SalienceConfig:
    jump_lag: int = 32              # compare EMA now vs EMA `lag` steps ago
    jump_threshold: float = 0.35    # cosine distance that counts as a region change
    stagnation_window: int = 400    # if the context moved less than `stagnation_threshold`
    stagnation_threshold: float = 0.08  # over this many steps, the loop is ruminating
    entropy_floor: float = 0.6      # ...or if entropy has stayed below this (recitation)
    entropy_window: int = 24        # steps for the "recent" entropy average
    entropy_drop: float = 0.45      # relative drop (recent vs previous window) that fires
    entropy_high: float = 2.0       # previous window must have been at least this wandering
    recurrence_min_age: int = 96    # snapshots older than this can be "returned to"
    recurrence_recent: int = 32     # ...but not if the region was visited within this many steps
    recurrence_threshold: float = 0.15  # cosine distance to an old snapshot that counts as return
    snapshot_every: int = 8         # keep one EMA snapshot every N steps
    refractory: int = 24            # minimum steps between two events


def genre_collapse_score(text: str) -> float:
    """Surface signature of falling into web boilerplate / lists / footers.

    Reverie probes on base models sank into 'Terms of Service | © LLC' and
    tag clouds — the deepest attractor of pretraining. Its fingerprint is
    cheap: low lexical diversity, many capitalized words, layout symbols.
    Returns 0 (prose) .. 1 (boilerplate).
    """
    words = text.split()
    if len(words) < 20:
        return 0.0
    uniq = len(set(w.lower() for w in words)) / len(words)
    caps = sum(1 for w in words if w[:1].isupper()) / len(words)
    symbols = sum(text.count(ch) for ch in "|©™®•·") + text.count(" - ") + text.count("http")
    sym_rate = min(1.0, symbols / max(1, len(words) / 10))
    # Parallel-corpus / translation-table collapse: language tags ("ru:",
    # "zh-cn:") and mixed scripts. A base model asked to repeat a premise
    # rationalizes the repetition as a translation table.
    lang_tags = len(re.findall(r"(?m)^\s*[a-z]{2}(?:-[a-z]{2})?:", text))
    non_latin = sum(1 for ch in text if ord(ch) > 0x2E7F) / max(1, len(text))
    parallel = min(1.0, lang_tags / 4.0) * 0.6 + min(1.0, non_latin * 4) * 0.4
    # narrative prose: uniq ~0.7, caps ~0.15, symbols ~0 -> ~0.1
    # boilerplate:     uniq ~0.25, caps ~0.55, symbols high -> ~0.8+
    base = 0.45 * (1 - uniq) + 0.35 * caps + 0.20 * sym_rate
    return float(np.clip(max(base, parallel), 0.0, 1.0))


@dataclass
class SalienceEvent:
    step: int
    kind: str                       # "jump" | "crystallize" | "recurrence" | "stagnation"
    magnitude: float
    window: tuple[int, int]         # [start, end) steps the event refers to
    ref_step: int | None = None     # for recurrence: the old snapshot's step


@dataclass
class _Snapshot:
    step: int
    vec: np.ndarray


class SalienceMonitor:
    """Feed one (context_vector, entropy) per step; get events back."""

    def __init__(self, config: SalienceConfig | None = None) -> None:
        self.cfg = config or SalienceConfig()
        self._step = 0
        self._entropies: list[float] = []
        self._snapshots: list[_Snapshot] = []
        self._last_event_step = -10**9
        self.events: list[SalienceEvent] = []

    @staticmethod
    def _cos_dist(a: np.ndarray, b: np.ndarray) -> float:
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return float(1.0 - (a @ b) / (na * nb))

    def observe(self, context: np.ndarray | None, entropy: float) -> SalienceEvent | None:
        cfg = self.cfg
        step = self._step
        self._step += 1
        self._entropies.append(float(entropy))
        if context is None:
            return None
        vec = np.asarray(context, dtype=np.float64)
        if step % cfg.snapshot_every == 0:
            self._snapshots.append(_Snapshot(step, vec.copy()))

        if step - self._last_event_step < cfg.refractory:
            return None
        event = (
            self._check_jump(step, vec)
            or self._check_crystallize(step)
            or self._check_recurrence(step, vec)
            or self._check_stagnation(step, vec)
        )
        if event is not None:
            self._last_event_step = step
            self.events.append(event)
        return event

    def _check_stagnation(self, step: int, vec: np.ndarray) -> SalienceEvent | None:
        """Rumination: the context has not moved for a long stretch, or entropy
        has sat on the floor (recitation). Not something to review — something
        to break out of; the loop treats it as a kick, not a candidate."""
        cfg = self.cfg
        old = self._snapshot_at_or_before(step - cfg.stagnation_window)
        if old is None or len(self._entropies) < cfg.stagnation_window:
            return None
        moved = self._cos_dist(vec, old.vec)
        recent_entropy = float(np.mean(self._entropies[-cfg.stagnation_window :]))
        if moved < cfg.stagnation_threshold or recent_entropy < cfg.entropy_floor:
            return SalienceEvent(step, "stagnation", 1.0 - moved, (old.step, step + 1))
        return None

    def _snapshot_at_or_before(self, target_step: int) -> _Snapshot | None:
        best = None
        for s in self._snapshots:
            if s.step <= target_step:
                best = s
            else:
                break
        return best

    def _check_jump(self, step: int, vec: np.ndarray) -> SalienceEvent | None:
        old = self._snapshot_at_or_before(step - self.cfg.jump_lag)
        if old is None:
            return None
        d = self._cos_dist(vec, old.vec)
        if d >= self.cfg.jump_threshold:
            return SalienceEvent(step, "jump", d, (old.step, step + 1))
        return None

    def _check_crystallize(self, step: int) -> SalienceEvent | None:
        w = self.cfg.entropy_window
        if len(self._entropies) < 2 * w:
            return None
        recent = float(np.mean(self._entropies[-w:]))
        previous = float(np.mean(self._entropies[-2 * w : -w]))
        if previous >= self.cfg.entropy_high and previous > 0:
            drop = 1.0 - recent / previous
            if drop >= self.cfg.entropy_drop:
                return SalienceEvent(step, "crystallize", drop, (step + 1 - 2 * w, step + 1))
        return None

    def _check_recurrence(self, step: int, vec: np.ndarray) -> SalienceEvent | None:
        cfg = self.cfg
        # visited recently? then it's not a return
        for s in reversed(self._snapshots):
            if step - s.step > cfg.recurrence_recent:
                break
            if self._cos_dist(vec, s.vec) <= cfg.recurrence_threshold and s.step != step:
                return None
        best: _Snapshot | None = None
        best_d = cfg.recurrence_threshold
        for s in self._snapshots:
            if step - s.step < cfg.recurrence_min_age:
                break
            d = self._cos_dist(vec, s.vec)
            if d <= best_d:
                best, best_d = s, d
        if best is not None:
            return SalienceEvent(step, "recurrence", 1.0 - best_d, (best.step, step + 1), ref_step=best.step)
        return None
