"""Declared deterministic inputs and simple secants, not a competitive learned index."""
from __future__ import annotations
from pathlib import Path
from bisect import bisect_left
from decimal import Decimal
import csv,json
from driftcert import Instance,Segment,Contract
from driftcert.model import atoms

ROOT=Path(__file__).resolve().parents[1]
FAMILIES=('uniform','alternating','increasing','clustered')


def model(keys:tuple[int,...],lo:int,hi:int,block:int=32)->tuple[Segment,...]:
    if not keys:return (Segment(lo,hi,0,0),)
    segments=[]
    for start in range(0,len(keys),block):
        end=min(len(keys)-1,start+block-1)
        left=lo if start==0 else keys[start]
        right=hi if end==len(keys)-1 else keys[end+1]-1
        if start==end:A,B,Q=0,start,1
        else:
            A=end-start;Q=keys[end]-keys[start];B=start*Q-A*keys[start]
        segments.append(Segment(left,right,A,B,Q))
    return tuple(segments)


def stored_windows(inst:Instance)->list[list[int]]:
    rows=[None]*len(inst.segments);j=0
    for r,x in enumerate(inst.keys):
        while x>inst.segments[j].hi:j+=1
        e=r-inst.segments[j].predict(x)
        if rows[j] is None:rows[j]=[e,e]
        else:rows[j]=[min(rows[j][0],e),max(rows[j][1],e)]
    return [[0,0] if w is None else w for w in rows]


def uniform_transport(inst:Instance)->list[list[int]]:
    """Safe simple baseline: all-universe source-rank residual, then edit caps.

    Unlike stored-only expansion, this covers prediction error on newly inserted
    query coordinates too. It does not reserve their own insertion or condition
    on final cardinality, so is not claimed exact.
    """
    rows=[None]*len(inst.segments)
    for j,a,b,L,_ in atoms(inst):
        for x in (a,b):
            e=L-inst.segments[j].predict(x)
            if rows[j] is None:rows[j]=[e,e]
            else:rows[j]=[min(rows[j][0],e),max(rows[j][1],e)]
    c=inst.contract
    return [[w[0]-min(c.delete,c.edits),w[1]+min(c.insert,c.edits)] for w in rows]


def scale_instance(n:int,family:str)->Instance:
    keys=[];x=-(1<<30) if family=='uniform' else -(1<<62)
    for k in range(n):
        if family=='uniform':gap=7
        elif family=='alternating':gap=1 if k%2==0 else (1<<32)
        elif family=='increasing':gap=(k+1)*(1<<16)
        elif family=='clustered':gap=(1<<36) if k%32==0 else 1+(k%3)
        else:raise ValueError('unknown gap family')
        x+=gap;keys.append(x)
    lo,hi=keys[0]-64,keys[-1]+64
    I=max(2,n//16);D=max(1,n//32);B=I+D-max(1,D//2)
    return Instance(lo,hi,tuple(keys),model(tuple(keys),lo,hi),Contract(I,D,B,n,n))


def exact_fixture(path:Path,obj:object)->None:
    """Materialize once; thereafter verify, never overwrite a reference input."""
    if path.exists():assert json.loads(path.read_text())==obj,('fixture disagreement',path)
    else:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(obj,separators=(',',':'))+'\n')


def wine_keys()->tuple[int,...]:
    with (ROOT/'data/wine_numeric.csv').open(newline='') as f:
        rows=list(csv.reader(f))
    assert rows[0][:2]==['178','13'] and len(rows[1:])==178
    values=[]
    for row in rows[1:]:
        assert len(row)==14
        value=Decimal(row[12]);assert value==value.to_integral_value()
        values.append(int(value))
    selected=tuple(sorted(set(values)))
    exact_fixture(ROOT/'data/wine_proline_keys.json',list(selected))
    return selected
