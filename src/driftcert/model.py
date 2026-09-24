"""Exact finite-set drift model. No floating point and no third-party packages."""
from __future__ import annotations
from dataclasses import dataclass, replace
from bisect import bisect_left
from typing import Iterator


def integer(x: object, name: str) -> int:
    if type(x) is not int or x.bit_length() > 256:
        raise ValueError(f'{name}: expected an integer of at most 256 bits')
    return x


@dataclass(frozen=True)
class Segment:
    lo: int
    hi: int
    a: int
    b: int
    q: int = 1

    def predict(self, x: int) -> int:
        return (self.a * x + self.b) // self.q


@dataclass(frozen=True)
class Contract:
    insert: int
    delete: int
    edits: int
    size_lo: int
    size_hi: int

    def with_edits(self, edits: int) -> 'Contract':
        return replace(self, edits=edits)


@dataclass(frozen=True)
class Instance:
    lo: int
    hi: int
    keys: tuple[int, ...]
    segments: tuple[Segment, ...]
    contract: Contract

    def validate(self) -> None:
        for name in ('lo', 'hi'):
            integer(getattr(self, name), name)
        if self.lo > self.hi or len(self.keys) > 100000 or len(self.segments) > 100000:
            raise ValueError('invalid domain or input entry limit exceeded')
        previous = self.lo - 1
        for k in self.keys:
            integer(k, 'key')
            if not previous < k <= self.hi:
                raise ValueError('keys must be sorted, unique and inside the domain')
            previous = k
        endpoint = self.lo
        for s in self.segments:
            for name in ('lo', 'hi', 'a', 'b', 'q'):
                integer(getattr(s, name), 'segment.' + name)
            if s.lo != endpoint or s.hi < s.lo or s.q <= 0:
                raise ValueError('segments must partition the domain and have positive denominator')
            endpoint = s.hi + 1
        if not self.segments or endpoint != self.hi + 1:
            raise ValueError('incomplete predictor domain')
        c = self.contract
        for name in ('insert', 'delete', 'edits', 'size_lo', 'size_hi'):
            if integer(getattr(c, name), 'contract.' + name) < 0:
                raise ValueError('negative budget or cardinality')
        if c.size_lo > c.size_hi:
            raise ValueError('reversed cardinality interval')

    @classmethod
    def from_dict(cls, raw: dict) -> 'Instance':
        if type(raw) is not dict or set(raw) != {'lo', 'hi', 'keys', 'segments', 'contract'}:
            raise ValueError('unexpected instance fields')
        obj = cls(raw['lo'], raw['hi'], tuple(raw['keys']),
                  tuple(Segment(**s) for s in raw['segments']), Contract(**raw['contract']))
        obj.validate()
        return obj

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


def overlap_floor(n: int, m: int, c: Contract) -> int:
    """Minimum old-key overlap imposed by all three edit budgets."""
    return max(0, n - c.delete, m - c.insert, (n + m - c.edits + 1) // 2)


def eligible_sizes(inst: Instance, old: bool, contract: Contract | None = None) -> tuple[int, int] | None:
    c = contract or inst.contract
    n = len(inst.keys)
    u = inst.hi - inst.lo + 1
    lo = max(c.size_lo, 1, n - c.delete, n - c.edits)
    hi = min(c.size_hi, u, n + c.insert, n + c.edits)
    if old:
        if not n:
            return None
    else:
        if c.insert < 1 or n == u:
            return None
        lo = max(lo, n - c.delete + 1, n - c.edits + 2)
    return (lo, hi) if lo <= hi else None


def rank_band(inst: Instance, x: int, contract: Contract | None = None) -> tuple[int, int, int, int] | None:
    """Return minimum rank, maximum rank, and their attaining final sizes."""
    if not inst.lo <= x <= inst.hi:
        raise ValueError('query outside the declared universe')
    c = contract or inst.contract
    n = len(inst.keys)
    left = bisect_left(inst.keys, x)
    old = left < n and inst.keys[left] == x
    sizes = eligible_sizes(inst, old, c)
    if sizes is None:
        return None
    ml, mh = sizes
    kl, kh = overlap_floor(n, ml, c), overlap_floor(n, mh, c)
    lower = max(0, ml - 1 - (inst.hi - x), left + kl - n)
    upper = min(mh - 1, x - inst.lo, mh - 1 - kh + left + int(old))
    return lower, upper, ml, mh


def atoms(inst: Instance) -> Iterator[tuple[int, int, int, int, int]]:
    """(segment, left endpoint, right endpoint, old keys below, is-old).

    Streaming merge of singleton old keys, open integer gaps and predictor cells.
    Complexity O(n + number of predictor segments), independent of domain width.
    """
    n = len(inst.keys)
    left = 0
    for j, seg in enumerate(inst.segments):
        x = seg.lo
        while x <= seg.hi:
            while left < n and inst.keys[left] < x:
                left += 1
            if left < n and inst.keys[left] == x:
                yield j, x, x, left, 1
                x += 1
                left += 1
            else:
                end = min(seg.hi, inst.keys[left] - 1 if left < n else seg.hi)
                yield j, x, end, left, 0
                x = end + 1
