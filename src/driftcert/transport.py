"""Ordinary conservative rank transport, not an exact-envelope algorithm."""
from bisect import bisect_left
from .model import Instance

def transport_windows(inst: Instance) -> list[list[int]]:
    """Source rank over every integer coordinate, expanded by edit caps.

    Covers active queries in any order of the minimal net edits to an admitted
    endpoint. Does not promise attainment, exactness, or minimum failure cost.
    No envelope/rank/atom helpers from the exact producer are imported.
    """
    inst.validate(); n=len(inst.keys); rows=[]; c=inst.contract
    for seg in inst.segments:
        left=bisect_left(inst.keys,seg.lo);x=seg.lo;low=high=None
        while x<=seg.hi:
            if left<n and inst.keys[left]==x:
                end=x;after=left+1
            else:
                end=min(seg.hi,inst.keys[left]-1 if left<n else seg.hi);after=left
            for point in (x,end):
                value=left-seg.predict(point)
                low=value if low is None else min(low,value)
                high=value if high is None else max(high,value)
            x=end+1;left=after
        rows.append([low-min(c.delete,c.edits),high+min(c.insert,c.edits)])
    return rows
