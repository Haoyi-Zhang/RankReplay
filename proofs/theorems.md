# Exact drift envelopes and minimum edit witnesses

## Scope and proof status

These are mathematical proofs, not proof-assistant certificates. The implementation
and exhaustive finite oracle exercise the formulas but do not establish their
universal validity. All keys and coefficients in the mathematical model are
integers of arbitrary finite size. The implementation separately limits input
integers to 256 bits and certificate integers to 1024 bits. Complexity below
counts exact integer arithmetic/comparison operations, not constant-time machine
instructions. The checker is separately implemented, not independently authored.

## 1. Model and notation

Let U = {a,...,b}, v=b-a+1, and S be a sorted set of n distinct keys from U.
A partition into p nonempty integer intervals is fixed. On interval j the frozen
prediction is p_j(x)=floor((A_j x+B_j)/Q_j), Q_j>0. Slopes may be negative and
predictions need not lie in the current rank range. A final state T is an
arbitrary subset of U satisfying

    i=|T\S| <= I, d=|S\T| <= D, i+d <= B,
    Mlo <= |T| <= Mhi.

All budgets are nonnegative integers. Only queries x in T are covered. Define
r_T(x)=|{y in T:y<x}|. A segment window [wlo_j,whi_j] is safe when
wlo_j <= r_T(x)-p_j(x) <= whi_j for every admissible T and present x in j.
Intersecting [p_j(x)+wlo_j,p_j(x)+whi_j] with [0,|T|-1] does not affect whether
the true rank is included. There is no guarantee for absent queries, physical
addresses with holes, arbitrary intermediate update states, changing routing, or
floating-point evaluation. Net edits have unit cost. An attaining set can be
replayed by deleting S\T in ascending order and then inserting T\S in ascending
order; the cardinality band is a final-state condition, not a condition on each
intermediate prefix of that trace. Section 7 separately certifies the active
prefixes of that declared canonical replay, including its source prefix.

For a fixed x, set s=1[x in S], nu=1-s, L=|S below x| and R=n-s-L. The universe
has A=x-a available positions to the left and C=b-x to the right, with L and R
old keys respectively. Its unused capacities are A-L and C-R.

## 2. Overlap and exact fixed-cardinality ranks

**Lemma 1 (overlap reduction).** At final size m and old-key overlap h=|S cap T|,
the three update inequalities hold exactly when

    h >= K_B(m) = max(0,n-D,m-I,ceil((n+m-B)/2)).

*Proof.* Insertions, deletions and total edits are m-h, n-h, n+m-2h. Rearrange
each upper bound and use integrality. Conversely these rearrangements imply all
three inequalities. The nonnegativity term is harmless because h is a cardinality.
The lemma is used with actual sets, so h<=min(n,m) is supplied by the set model,
not silently omitted as a standalone numeric constraint. QED.

**Lemma 2 (attainable overlap at a prescribed rank).** Suppose x is present,
|T|=m, and r_T(x)=r. Such sets fit in the universe exactly when

    0 <= r <= A,  0 <= m-1-r <= C.

Among those sets the largest old-key overlap is

    H(x,m,r)=s+min(L,r)+min(R,m-1-r).

It is attained by selecting old keys first on each side of x and filling the
remaining positions with non-old keys.

*Proof.* At most min(L,r) of the r selected left keys can be old; the right side
is identical and the query contributes s. This proves the upper bound. If r<=L,
choose any r left old keys. If r>L, choose all L left old keys and r-L left
non-old keys; r<=A implies r-L<=A-L. This constructs the left side. Apply the
same argument to q=m-1-r on the right and include x. The sides and x are
disjoint. Hence the set has exactly m elements, rank r, and the stated overlap.
No assumption on the spacing of old keys or a sampling distribution is used.
QED.

**Lemma 3 (eligible sizes).** Write

    f- = max(Mlo,1,n-D,n-B),
    f+ = min(Mhi,v,n+I,n+B).

For an old query x, all eligible sizes are the integers in [f-,f+], provided
n>0. For a new query x, I>=1 and n<v are necessary; then the eligible sizes are

    [max(f-,n-D+1,n-B+2), f+].

A reversed interval denotes no eligible size. Eligibility depends on whether x
is old, not its coordinate.

*Proof.* For an old query, when m<=n the best overlap m is achieved by retaining
x and any m-1 other old keys; it costs n-m deletions and no insertions. When
m>=n keep all old keys and insert m-n others, possible exactly when m<=v. These
choices minimize both insertions and deletions at size m. Their budget
inequalities, 1<=m<=v, and the declared band give [f-,f+]. For a new query the
maximum overlap is min(n,m-1). If m<=n+1, insert x and retain m-1 old keys,
costing one insertion, n-m+1 deletions, and n-m+2 total edits. If m>=n+1,
retain all old keys and insert m-n keys including x. Combining these two cases
gives I>=1, m>=n-D+1, m>=n-B+2, m<=n+I, m<=n+B, and the size/domain limits.
When these inequalities hold the corresponding construction is possible. The
old set need not be uniformly spaced: only counts and the presence of x matter
because the rank is not yet prescribed. QED.

**Theorem 4 (exact rank interval at fixed size).** Let m be an eligible size for
x, and let K=K_B(m). The attainable ranks are precisely every integer in

    ell_m(x)=max(0,m-1-(b-x),L+K-n),
    u_m(x)=min(m-1,x-a,m-1-K+L+s).

*Proof.* By Lemmas 1 and 2 rank r is feasible exactly when it meets the two
side-capacity inequalities and H(x,m,r)>=K. Use the elementary identity

    min(L,r)+min(R,m-1-r)
      = min(L+R,L+m-1-r,r+R,m-1).

The four inequalities obtained by requiring each term plus s to be at least K
are K<=n, r<=m-1-K+L+s, r>=L+K-n, and K<=m-1+s. The first and last hold because
m is eligible, so at least one set containing x at size m has overlap >=K;
its overlap is at most min(n,m-1+s). The other two, combined with capacities,
are exactly ell_m<=r<=u_m. Necessity follows. Conversely every integer in this
interval satisfies H>=K and the capacities, so the old-first construction in
Lemma 2 is an admissible attaining set. This proves all intermediate ranks,
not merely two bounds. QED.

**Theorem 5 (exact ranks over a cardinality band).** Let [m-,m+] be the eligible
size interval of Lemma 3. The full attainable rank set is

    {ell_m-(x), ell_m-(x)+1, ..., u_m+(x)}.

Its lower and upper endpoints have attaining sets of sizes m- and m+
respectively. If the eligible size interval is empty there is no covered query.

*Proof.* As m increases by one, every term defining K_B(m) is nondecreasing and
increases by at most one. Thus K does too. Each term in ell_m is nondecreasing
with increment zero or one, and each term in u_m has the same property because
m-1-K has increment zero or one. Taking a maximum or minimum preserves these
properties. Hence the global minimum of the lower endpoints occurs at m-, and
the maximum of the upper endpoints at m+. Every fixed-size interval is nonempty
by eligibility. Moreover ell_(m+1)<=ell_m+1<=u_m+1, so consecutive intervals
have no missing integer between them. Their union is the full integer interval
claimed. Endpoint constructions follow from Theorem 4. QED.

## 3. Sparse envelopes for floor-affine predictions

An atom is a maximal intersection of a predictor interval with either an old-key
singleton or an integer gap between consecutive old keys (including edge gaps).
There are at most 2n+p nonempty atoms: the boundaries are the union of predictor
boundaries and old-key/successor boundaries, and coincident boundaries only
reduce their number. A streaming merge constructs them in O(n+p) operations.
On an atom [alpha,beta], L and s are constant.

Let m-,m+ be eligible and put

    C0=max(0,L+K_B(m-)-n), c=m--1-b,
    H0=min(m+-1,m+-1-K_B(m+)+L+s).

By Theorem 5 the rank endpoints on the atom are

    ell(x)=max(C0,x+c),  u(x)=min(H0,x-a).

Each is continuous as a real piecewise-linear function with an integer hinge:
t_ell=C0-c and t_u=a+H0. On each branch its slope is zero or one.

**Lemma 6 (branch monotonicity).** For integer x and any rational alpha,
beta, the function d*x+e-floor(alpha*x+beta), where d is either zero or one,
is monotone on consecutive integers.

*Proof.* For d=0 its direction is opposite to the sign of alpha. For d=1,
if alpha<=1 then floor(z+alpha)-floor(z)<=1 for every real z, making the
consecutive difference nonnegative. If alpha>=1 the floor difference is at
least one, making it nonpositive. At alpha=1 it is constant. Negative slopes
and alpha=0 are included. QED.

**Theorem 7 (tight segment envelopes).** On each nonvacuous atom evaluate the
lower and upper residuals at its endpoints and at its two hinges clipped to the
atom. There are at most four distinct candidates. Taking their minima and
maxima over each predictor segment yields the exact tight residual enclosure
[Elo_j,Ehi_j] for all admissible final sets and present queries. It is
constructible in O(n+p) exact-integer operations, independent of v, B, and the
number of eligible final sizes in the operation count.

*Proof.* On either side of its hinge, each residual is monotone by Lemma 6,
so extrema lie at branch endpoints. The integer hinge itself belongs to both
real branches, and is an integer coordinate: the transition from hinge-1 to
hinge and hinge to hinge+1 cannot create a more extreme value than an endpoint
of one of the two monotone branches. Thus atom endpoints and hinge suffice;
clipping handles hinges outside the atom. Taking extrema over the partition
is exact. Every candidate endpoint is an attainable rank by Theorem 5, so
there is no gap between the enclosure and a realizing final state. Maintaining
left old-key counts during the streaming merge avoids a binary search per
candidate. Candidate work per atom and count-witness construction are constant.
The two extrema can be attained by different sets and different sizes; no claim
of their simultaneous attainment is made. Nor need all residual integers between
them be attainable. QED.

The requested window is universally safe if and only if it contains this exact
enclosure in every nonvacuous segment. Necessity follows from attainment;
sufficiency follows from enclosure. An entirely vacuous segment is explicitly
marked empty, not assigned a numeric interval containing invented queries.

**Counterexample 8 (gap endpoints are insufficient).** Take U={0,...,10},
S={0,10}, p(x)=floor(x/2), I=3,D=1,B=4, Mlo=Mhi=4. The exact residual interval
is [-3,2]. At x=7 choose T={7,8,9,10}, giving residual -3. At x=3 choose
T={0,1,2,3}, giving residual 2. Testing only old keys and gap endpoints
{0,1,9,10} instead returns [-2,1]. The rank-envelope hinges are therefore
necessary candidates for this endpoint-based approach.

## 4. Count witnesses and checker soundness

A witness stores x,m,r and four counts (old_left,new_left,old_right,new_right).
The verifier separately checks all four nonnegative category capacities:

    old_left <= L,          new_left <= x-a-L,
    old_right <= R,         new_right <= b-x-R.

It also checks left sum r, total sum m-1, and query membership s from the
trusted old set.
Then h=old_left+old_right+s determines i=m-h,d=n-h; it checks every budget and
the cardinality band. The old-first witness uses

    old_left=min(L,r), old_right=min(R,m-1-r),
    new_left=r-old_left, new_right=m-1-r-old_right.

**Lemma 9 (count-witness realizability).** Every accepted count witness denotes
at least one actual admissible set containing x at rank r. Its exact net edit
cost is i+d. Conversely every admissible set induces an accepted count witness.

All four capacity premises are necessary.  In particular, take U=S={0,1},
x=0,m=2,r=1, counts (old_left,new_left,old_right,new_right)=(1,0,0,0), and a
zero-edit contract.  The rank and cardinality sums hold, and the derived budget
is zero, but old_left=1 exceeds L=0.  No set can place the least universe key at
compact rank one, so the checker must reject this tuple.

*Proof.* Each of the four categories consists of known distinct universe
positions, and the categories and query are disjoint. A bounded nonnegative
count can be realized by choosing that many positions in its category. The sum
checks establish size and rank; the budget checks establish admissibility.
Conversely count a real set by category. QED.

The certificate contains two endpoints and two attaining count witnesses per
nonvacuous segment. The checker independently decomposes the domain at each
old key and successor, determines the eligible sizes, and reconstructs the two
rank bounds from the update constraints. It checks enclosures by integer linear
inequalities rather than the producer's extremum-candidate list. On a rank-bound
branch v(x)=d*x+e:

    v(x)-floor((A_j*x+B_j)/Q_j) >= Elo
      iff A_j*x+B_j <= Q_j*(v(x)-Elo+1)-1;
    v(x)-floor((A_j*x+B_j)/Q_j) <= Ehi
      iff A_j*x+B_j >= Q_j*(v(x)-Ehi).

Both are linear inequalities in x, hence hold on an integer interval if they
hold at its endpoints. The strictness correction -1 in the first inequality is
essential. The checker also requires each asserted endpoint to have an attaining
witness in the correct segment, and it rejects an empty marker if any eligible
query exists, or a nonempty marker for a vacuous segment.

**Theorem 10 (checker soundness and completeness).** Acceptance implies that
the supplied endpoints are exactly the tight segment residual endpoints. Every
certificate produced by Theorem 7 is accepted.

*Proof.* The branch checks and Theorem 5 prove universal enclosure. Lemma 9 and
the checked residual equalities prove attainment at each endpoint. Enclosure
and attainment together imply exactness. Empty-marker checks establish vacuity
correctly. For a produced certificate, Theorem 7 supplies a valid enclosure and
attaining witnesses, so all these checks succeed. QED.

This theorem trusts the input model, arithmetic semantics, the proven rank
lemmas, and correct execution of the checker. It does not claim protection
against a changed input instance, compromised runtime, arbitrary code, or an
incorrect operational mapping from physical positions to compact ranks.
The implementation shares typed parsing with the producer but not its atom
iterator, rank-bound function, eligible-size routine, or extremum algorithm.
Its sorting and binary searches give O((n+p) log(n+p+1)) operations conservatively,
not the producer's streaming linear bound. Output uses O(p) integer words.

## 5. Exact minimum cost at a fixed query and rank

Temporarily remove the total-edit cap B while retaining I,D and [Mlo,Mhi]. This
is equivalent to setting B=I+D. Theorems 3--5 give an interval [ell(x),u(x)] of
all feasible ranks in that relaxed family.

**Lemma 11 (cost decomposition).** For fixed x,m,r, the minimum net edit cost
is

    nu+|r-L|+|m-1-r-R|.

An old-first count witness attains it whenever that rank and size are feasible.

*Proof.* Lemma 2 maximizes overlap, hence minimizes n+m-2h. Algebra gives the
stated sum. Equivalently, with z=r-L and t=m-1-r-R, the minimal insertions and
deletions are nu+max(z,0)+max(t,0) and max(-z,0)+max(-t,0), respectively.
Choosing fewer old keys increases both edit counts, so cannot improve either a
cap or total cost. QED.

**Lemma 12 (projection across the size band).** Let r be a feasible rank in the
relaxed family and define

    z=r-L, m0=n+nu+z=1+r+R,
    m*=clip(m0,[Mlo,Mhi]).

Then m* is feasible for that query and rank, and its old-first witness minimizes
cost over all eligible sizes. The minimum is

    g_x(r)=nu+|r-L|+dist(n+nu+r-L,[Mlo,Mhi]).

*Proof.* Feasibility of r implies that the mandatory left-side/query insertion
and deletion costs fit their caps: I'=I-nu-max(z,0)>=0 and
D'=D-max(-z,0)>=0. Put t=q-R=m-m0. The right-side capacity requires
-R<=t<=C-R; the remaining insertion/deletion caps require -D'<=t<=I'. Their
intersection J is an integer interval containing zero, because all four
nonnegative capacities are valid. The cardinality condition is another integer
interval H=[Mlo-m0,Mhi-m0]. Some size is feasible by the premise on r, so J cap H
is nonempty. The nearest point of H to zero belongs to J: if zero is in H this
is immediate; if H is positive and intersects J, its left endpoint is between
zero and an intersection point; if H is negative the symmetric statement holds.
This nearest point is m*-m0. Hence the clipped size is feasible and minimizes
|t| over feasible sizes. Apply Lemma 11. This argument is why clipping to the
original cardinality band, rather than enumerating all eligible sizes or
ignoring I,D, is sound. QED.

**Lemma 13 (best violating rank).** The function g_x(r) is nonincreasing for
r<=L and nondecreasing for r>=L. Its minimum on any nonempty integer interval
[l,h] is attained at clip(L,[l,h]). In particular, for a below-window violation
use [ell(x),min(u(x),p_j(x)+wlo_j-1)]; for an above-window violation use
[max(ell(x),p_j(x)+whi_j+1),u(x)].

*Proof.* The distance to an interval changes by at most one under a unit step.
For r<L the |r-L| term falls by one, so g cannot increase; for r>=L it rises by
one, so g cannot decrease. Projection onto an interval therefore minimizes g;
flat minima are allowed. Integrality makes the strict residual violations
exactly the two stated closed rank intervals. QED.

## 6. One-sweep global minimum

On an atom let C0,c,H0 describe the relaxed rank endpoints as in Section 3.
The relevant integer lines in x are

    C0, x+c, H0, x-a, L,
    L+Mlo-n-nu, L+Mhi-n-nu.

For a below or above violation add the single floor-affine threshold
f(x)=floor((A_j*x+B_j)/Q_j)+w, with w=wlo_j-1 or whi_j+1.
The first four lines decide rank feasibility; the fifth decides projection
onto the violating interval; the last two decide the distance-to-band branch
in Lemma 12. There are seven integer lines and one floor-affine function.

**Lemma 14 (finite weak-order arrangement).** An integer atom can be partitioned
into at most 57 consecutive cells on which the truth of every weak comparison
between these functions is constant. Their cell endpoints are computed using
integer divisions without enumerating the atom's width.

*Proof.* Each of the 21 pairs of integer lines contributes two directed <=
comparisons. Each of the seven integer lines and f contributes two. Thus there
are 56 comparisons. For integer lines sx+t and vx+w, the comparison is
(s-v)x<=w-t. For f(x)<=sx+t, exact floor semantics give

    (A_j-Q_j*s)x <= Q_j*(t-w+1)-1-B_j;

for sx+t<=f(x), they give

    (Q_j*s-A_j)x <= B_j-Q_j*(t-w).

Here the w in these last two displays is the threshold shift, not the second
integer-line intercept. Each inequality d*x<=e is either constant or changes
truth once along the integers. If d>0, the cut is floor(e/d)+1. If d<0,
the first true integer is ceil(e/d). Discard cuts outside the atom, combine
coincident cuts, and include the two boundary cuts. At most 56 internal cuts
yield at most 57 cells. Including both orientations separates equality
plateaus, which would not be represented correctly by only a strict ordering.
The two endpoints of each cell yield at most 114 candidate points. QED.

**Theorem 15 (direct minimum witness).** On each atom and each violation side,
evaluate the endpoints of the cells in Lemma 14. For a nonempty violating-rank
interval use Lemmas 12--13 to choose rank, size and a count witness. The cheapest
candidate over all atoms is the exact minimum edit cost b* of any violating
state under I,D and the cardinality band. If there is no candidate, the family
is safe. Comparing b* with the original total cap B answers its safety query.
The producer uses O(n+p) exact-integer operations, at most 228 minimum-cost
candidate evaluations per atom, without a factor log(B+2).

*Proof.* Fix a comparison cell. Whether a violation interval is empty is fixed
because all comparisons that form its lower and upper endpoints are fixed.
When nonempty, the projected rank from Lemma 13 is one fixed member of the
seven integer lines or the floor-affine threshold. Which absolute-value and
distance branch defines its cost is fixed by its comparisons with L and the
two translated cardinality endpoints. Consequently the cost is a fixed affine
function of this selected rank on the entire cell. An integer line is monotone,
and a floor-affine function is monotone for any slope. Applying a fixed affine
function preserves monotonicity (possibly reverses it or makes it constant).
Hence a minimum occurs at a cell endpoint. Lemmas 12--13 show that no other
rank or size at that query has lower violating cost. Taking endpoints, both
sides and all atoms therefore covers a global optimum. Each candidate produces
a feasible old-first count witness with exactly the calculated cost. At most
57 cells times two endpoints times two sides is 228 candidates per atom;
fixed-size sorting of its cuts is constant work in the stated arithmetic model.
The final comparison with B is valid because only the total cap was relaxed.
QED.

**Theorem 16 (replayable minimum certificate).** A violation output consists of
an attaining violating count witness of cost b*<=B and, when b*>0, a tight
certificate at total cap b*-1 whose endpoints fit the requested windows. For
b*=0 the predecessor certificate is absent. The checker accepts only true
minimum costs. Every result of Theorem 15 can be accompanied by such a packet.

*Proof.* Lemma 9 and the checked residual violation show a real admissible
failure at cost b*. All smaller integer costs are at most b*-1. Their states
form exactly the same I,D,size-constrained family with this lower total cap,
which the checked certificate proves safe by Theorem 10. Thus a cheaper failure
is impossible. At zero there is no smaller nonnegative edit cost. Conversely
an exact global minimum has a safe predecessor family, for which Theorem 7
constructs a certificate. If the whole B-bounded family is safe, a single
ordinary certificate suffices. This verifier does not need to trust the
comparison-arrangement optimization. QED.

For comparison, safety is monotone in B because the feasible sets are nested.
Binary search on B plus the same tight-envelope routine also finds b* in
O((n+p) log(B+2)) operations (with the B=0 case interpreted separately). This
is a transparent baseline, not a claimed novel algorithm. The direct method's
constant 228 is a worst-case bound, so it need not be faster at small budgets.

## 7. Ordered replay rather than only the final state

The endpoint contract treats the replacement from `S` to `T` atomically.  This
section fixes one concrete non-atomic schedule and certifies every active key at
every prefix.  For a final set `T`, the **canonical replay** first deletes the
keys of `S \\ T` in increasing key order and then inserts the keys of `T \\ S`
in increasing key order.  The active set initially is `S` and finally is `T`.
A query is eligible at a prefix exactly when its key is active at that prefix.
No cardinality or budget constraint is imposed separately on a prefix; the
trusted contract constrains the chosen final set and the replay order is fixed.

For an old key `x in S`, write `L(x)=|{s in S:s<x}|`.  For a fixed final set
`T`, write `H_x(T)=|{s in S intersection T:s<x}|` and, when `x in T`, write
`q_T(x)=rank_T(x)`.  A new key means a key in `U \\ S`.

**Lemma 17 (trace of one fixed final set).** Under the canonical replay:

1. A new key is inactive until its insertion; from that insertion onward its
   rank is exactly its final rank.
2. An old key is active initially.  While active, its attained ranks form the
   entire integer interval

       [H_x(T), max(L(x), q_T(x))]

   if it is retained, and `[H_x(T), L(x)]` if it is deleted.

*Proof.* All deletions smaller than an old query occur before that query is
deleted, and each such deletion lowers its rank by one.  Deletions larger than
the query do not change its rank.  Thus the deletion phase moves from `L(x)`
down one unit at a time to `H_x(T)` while the key is active.  If the key is
retained, insertions smaller than it then occur in increasing order and move
its rank one unit at a time from `H_x(T)` to `q_T(x)`; larger insertions do not
change it.  If the key is deleted, it ceases to be eligible immediately after
its own deletion.  For a new key, every final new key smaller than it has
already been inserted when it becomes active and every later insertion is
larger, so its active-prefix rank equals its final rank. QED.

Let `u=|U|`, `n=|S|`, and let the final-size band in the trusted contract be
`[Mlo,Mhi]`.  The set of feasible final cardinalities is the integer interval

    mlo = max(Mlo, 0, n-D, n-B),
    mhi = min(Mhi, u, n+I, n+B).

It is empty exactly when `mlo>mhi`.  At a fixed feasible size `m`, the minimum
possible old-key overlap is

    H(m)=max(0, n-D, m-I, ceil((n+m-B)/2), m-(u-n)).

These are the same overlap inequalities used for final-state ranks.

**Lemma 18 (minimum overlap across the replay family).** If the final-set family
is nonempty, its minimum old-key overlap is

    h* = H(mlo).

For an old query with `L=L(x)`, the minimum number of surviving old keys smaller
than `x` over the family is

    rmin(x)=max(0, h*-(n-L)).

Both bounds are attained by a final set satisfying the trusted contract.

*Proof.* Every term in `H(m)` is nondecreasing in `m`, so the minimum over the
feasible size interval occurs at `mlo`.  Given total overlap `h*`, at most
`n-L` old keys can be chosen from `x` and the keys to its right.  Therefore at
least `max(0,h*-(n-L))` chosen old keys must lie to the left.  Choose exactly
that many left old keys, then choose `x` and right old keys until the overlap is
filled, and fill the remaining `mlo-h*` positions from holes in the finite
universe.  The overlap inequalities guarantee all category capacities and the
insert, delete and total-edit caps.  If no old key outside the left side is
retained, `x` may be one of the deleted keys and is still active immediately
before its deletion.  Hence the lower rank is attained at a replay prefix. QED.

For segment `j`, let `[E_j^-,E_j^+]` be the exact final-state residual envelope
from Theorem 10.  Let `S_j` be the old keys routed to the segment.

**Theorem 19 (exact ordered-replay envelope).** If the final-set family is
nonempty, the exact residual envelope over every active key at every canonical
replay prefix is

    R_j^- = min(E_j^-, min_{x in S_j}(rmin(x)-pi(x))),
    R_j^+ = max(E_j^+, max_{x in S_j}(L(x)-pi(x))).

An empty final-state envelope contributes no E_j^- or E_j^+ term; empty
old-key minima or maxima are also omitted. If neither contributes, the replay
segment is vacuous. A family containing only the empty final set can still have
active old queries in its source and deletion prefixes. If the final-set family
itself is empty, no source prefix is included and every replay segment is vacuous.
The envelope and attaining count
witnesses are produced in `O(n+p)` exact-integer operations after the endpoint
certificate, without scanning the coordinate universe or replaying a batch.
The source scan carries `L(x)` and all old/self/new category counts into each
strict endpoint update, so compact witness construction is constant time and
does not perform a new binary search.  Operation accounting includes every such
witness construction, even when a later endpoint replaces it.

*Proof.* Lemma 17 says that a new query contributes only a final-state rank,
which is already covered exactly by the endpoint envelope.  For an old query,
all final ranks when retained are also covered there.  The only additional
extrema are the initial rank `L(x)` and the minimum deletion-prefix rank.
Lemma 18 identifies the latter exactly as `rmin(x)` and gives an attaining
final set and prefix.  Thus the displayed union is both universally enclosing
and pointwise attained.  Source keys are sorted and segments form a partition,
so one simultaneous scan evaluates each old key once and advances across each
segment once. QED.

**Proposition 20 (endpoint safety does not imply replay safety).** There are
contracts for which every admissible final state satisfies a window but the
canonical replay violates it.  Let `U={0,1,2}`, `S={0,2}`, use segments
`[0,1]` and `[2,2]`, and require one insertion, one deletion, total cap two and
final size two.  For the old query `x=2`, every admissible final state has rank
one.  The replay to `{1,2}` has ranks `1,0,1`; hence the endpoint window `[1,1]`
is safe and the replay window is not.

*Proof.* The only way to preserve size two while changing the left member uses
one deletion and one insertion.  Deleting zero precedes insertion of one, so
`x=2` is temporarily the first key.  Theorem 19 gives the same lower endpoint.
QED.

Replay safety remains monotone in the total cap because increasing `B` only
adds admissible final sets and their fixed replays.

**Theorem 21 (minimum ordered-replay failure and checker packet).** Binary
search over integer budgets `0,...,B`, using Theorem 19 as the exact predicate,
returns the smallest replay-violating total-edit budget in
`O((n+p) log(B+2))` exact-integer operations.  A safe or violating packet binds
the literal canonical schedule identifier.  A violation packet contains an
exactly shaped active-prefix or final-state witness wrapper at that budget and,
unless the budget is zero, an exact safe replay certificate at the predecessor
budget.  Missing or changed schedules and extra wrapper fields are rejected. A
checker that independently reconstructs the overlap and old-key obligations
accepts only a true minimum.

*Proof.* Nested feasible families make safety monotone.  Exactness of Theorem 19
therefore makes ordinary lower-bound binary search exact, including a separate
zero-budget check.  The witness realizes a violation at the reported budget.
The predecessor certificate encloses every active-prefix residual at all
smaller budgets, since each such family is contained in the predecessor family.
Conversely, the true minimum has a safe predecessor and Theorem 19 supplies its
certificate.  The checker need not trust the producer's scan or binary-search
control flow: it recomputes the feasible size interval, `h*`, every old-key
obligation, endpoint-certificate validity, witness cost, and predecessor
containment. QED.

This schedule is a declared protocol, not a concurrency theorem.  Other orders,
interleavings, atomic multi-key operations, prefix cardinality constraints, and
physical address movement require different certificates.

## 8. Width lower bound and semantic exclusions

**Corollary 22 (unavoidable width at a query).** Any integer lookup interval
that covers every admissible rank at x has at least u(x)-ell(x)+1 positions.
For an integer center unconstrained by a predictor family, the minimum
symmetric radius is ceil((u(x)-ell(x))/2).

*Proof.* Both extreme ranks are attained, and an interval containing them
contains every integer between them. A centered interval of radius e has at
most 2e+1 positions, giving the lower bound. A floor or ceiling midpoint attains
it. This is a pointwise statement, not an optimal piecewise-affine predictor or
minimum-cost resegmentation theorem. QED.

An example of a necessary insertion reservation is U={0,...,4}, S={1,3}, I=D=1,
Mlo=Mhi=2 and new query x=2. At B=1 the query cannot occur in an admissible state;
at B=2 ranks 0 and 1 are attainable. Retaining the final cardinality forces a
deletion as well as the query insertion. A rule that assigns a free insertion
to x is unsound here.

The canonical replay certificate constrains ranks at active prefixes, but it
does not impose a separate cardinality invariant at each prefix.  If the
cardinality must remain exactly n after every single insertion or deletion, no
nontrivial single-key first operation is legal even though an atomic one-in/one-out
replacement has a legal final state.  Similarly, an unknown or unbounded key
universe removes the finite side capacities that make inserted-query extrema
finite for a nonconstant frozen predictor.  No extension to those models is
asserted.

## Evidence map

The finite oracle enumerates actual subsets and never imports these closed-form
bounds. The integration checks compare tight segment endpoints, direct and
bisection minimum witnesses, literal replay, and certificate mutation rejection.
The public numeric input and generated scaling families assess implementation
cost and precision only; they are not database workload or deployment evidence.


## 9. Fixed-cardinality specialization and edit parity

**Corollary 23 (replacement envelope).** Suppose Mlo=Mhi=n>0, and define
q=min(I,D,floor(B/2)). For an old query the exact rank interval is

    [max(0,n-1-(b-x),L-q), min(n-1,x-a,L+q)].

For a new query it is empty when q=0. When q>=1 and a new coordinate exists,
it is

    [max(0,n-1-(b-x),L-q), min(n-1,x-a,L+q-1)].

*Proof.* At fixed size, insertions equal deletions, and K_B(n)=max(0,n-q).
Substitute in Theorem 4. If q>n the extra difference is redundant with the
zero and n-1 capacity terms: L<=n for a new query and L<=n-1 for an old query.
The query's own insertion is the difference between s=0 and s=1 in the upper
endpoint. A new query needs at least one insertion and one deletion, hence
q>=1; because n>0, its fixed size is then eligible. QED.

**Corollary 24 (parity and fixed-size minimum costs).** For any two sets S,T,
net cost |S\T|+|T\S| has the parity of n+|T|. Therefore, under fixed size n,
all costs are even, the feasible families at total caps 2k and 2k+1 agree,
and every finite minimum violating cost is even. At a fixed feasible query
and rank r, write z=r-L. The minimum fixed-size cost is 2|z| for an old query,
and 1+|z|+|z+1|=2*max(-z,z+1) for a new query.

*Proof.* The cost equals n+|T|-2|S cap T|. The cost expressions follow from
Lemma 12 with the singleton size band {n}: its distance term is |nu+z|.
For integer z the new-query expression is 2(z+1) when z>=0 and -2z when z<=-1.
All conclusions concern net atomic edits; a delete-insert pair is counted as
two edits, not one operation. QED.

These corollaries explain a deliberately retained null in the scaling campaign.
There I=2D (except the smallest boundary case), size is fixed, and B is at
least 2D. The total cap is therefore redundant with the insertion/deletion
caps: removing it cannot widen the exact envelope. An exploratory all-budget
sensitivity grid is explicitly distinguished from the frozen scaling protocol.

## 10. Unbounded-domain obstruction

Finite edit caps do not alone imply finite universal residual bounds on an
unbounded coordinate universe. Let U=Z, S={0}, pi(x)=x, I=B=1, D=0 and
Mlo=Mhi=2. For every positive integer N, T={0,N} is admissible and its query
N has rank one and residual 1-N. These residuals are unbounded below. This
is one counterexample to a general guarantee, not a claim that all predictors
on an unbounded universe fail. It requires no computational experiment.
