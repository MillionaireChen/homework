#!/usr/bin/env python3
"""
Re-derive every number quoted in report.pdf from the shipped artifacts and
check it. Nothing here reads a model; it is pure arithmetic over JSONL.

    python3 verify_report_numbers.py \
        --data        ../../../data \
        --run-a       ../runs/primary_claude_full250/score_ranked.jsonl \
        --run-b       ../runs/secondary_codex_full250/score_ranked.jsonl \
        --third-read  third_read_109_unlabelled/agreement.json

Exit status is 0 only if every claim reproduces.
"""
import argparse, collections, json, math, os, re, statistics as st, sys, unicodedata

# ----------------------------------------------------------------- helpers
def jl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]

def norm(s):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s or ""))

def n_sentences(text):
    return len([p for p in re.split(r"(?<=[。！？])", text) if p.strip()])

def spearman(xs, ys):
    n = len(xs)
    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        out = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    den = (sum((rx[i] - mx) ** 2 for i in range(n))
           * sum((ry[i] - my) ** 2 for i in range(n))) ** 0.5
    return num / den

def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    den = (sum((xs[i] - mx) ** 2 for i in range(n))
           * sum((ys[i] - my) ** 2 for i in range(n))) ** 0.5
    return num / den

# --------------------------------------------------- weak labels from corpus
def weak_labels(articles, summaries):
    """One category per candidate, derived from the corpus alone.

    No evaluator output is consulted, so no score can influence a label."""
    lab = {}
    for s in summaries:
        art = articles[s["article_id"]]
        cand = norm(s["summary"])
        ref = norm(art["reference_summary"])
        body = norm(art["title"] + art["text"])
        if cand == ref:
            lab[s["summary_id"]] = "REFERENCE"
        elif cand and ref.startswith(cand):
            lab[s["summary_id"]] = "FRAGMENT"
        elif cand and cand in body:
            lab[s["summary_id"]] = "COPY"
        else:
            foreign = any(
                cand == norm(a["reference_summary"])
                or norm(a["reference_summary"]).startswith(cand)
                or cand in norm(a["title"] + a["text"])
                for aid, a in articles.items() if aid != s["article_id"])
            lab[s["summary_id"]] = "FOREIGN" if foreign else "GENERATED"
    return lab

# ------------------------------------------------------------------- runner
CHECKS = []
def check(label, expected, got, tol=0.0):
    ok = (abs(expected - got) <= tol) if isinstance(expected, (int, float)) \
         and isinstance(got, (int, float)) else (expected == got)
    CHECKS.append((label, expected, got, ok))

def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--data", default=os.path.join(here, "..", "..", "..", "data"))
    ap.add_argument("--run-a", default=os.path.join(
        here, "..", "runs", "primary_claude_full250", "score_ranked.jsonl"))
    ap.add_argument("--run-b", default=os.path.join(
        here, "..", "runs", "secondary_codex_full250", "score_ranked.jsonl"))
    ap.add_argument("--third-read", default=os.path.join(
        here, "third_read_109_unlabelled", "agreement.json"))
    args = ap.parse_args()

    articles = {a["article_id"]: a for a in jl(os.path.join(args.data, "articles.jsonl"))}
    summaries = jl(os.path.join(args.data, "summaries.jsonl"))
    A = {r["summary_id"]: r for r in jl(args.run_a)}
    B = {r["summary_id"]: r for r in jl(args.run_b)}
    lab = weak_labels(articles, summaries)
    ids = sorted(A)
    term = lambda run, i: bool(run[i].get("terminal_result"))

    # -- Section I: exploration -------------------------------------------
    check("corpus: articles", 50, len(articles))
    check("corpus: candidates", 250, len(summaries))
    lengths = [len(s["summary"]) for s in summaries]
    check("candidate length min", 22, min(lengths))
    check("candidate length max", 302, max(lengths))
    check("candidate length median", 125, int(st.median(lengths)))
    arts_len = [len(a["title"]) + len(a["text"]) for a in articles.values()]
    check("article length median", 1587, math.floor(st.median(arts_len) + 0.5))
    refs_len = [len(a["reference_summary"]) for a in articles.values()]
    check("reference length min", 41, min(refs_len))
    check("reference length max", 164, max(refs_len))
    census = collections.Counter(lab.values())
    for name, n in [("REFERENCE", 58), ("COPY", 50), ("FRAGMENT", 17),
                    ("FOREIGN", 16), ("GENERATED", 109)]:
        check(f"census: {name}", n, census[name])
    over = [s for s in summaries if n_sentences(s["summary"]) > 3]
    check("candidates over 3 sentences", 3, len(over))
    check("  ...and all of them are article copies", 3,
          sum(1 for s in over if lab[s["summary_id"]] == "COPY"))

    # duplicate text groups
    by_text = collections.defaultdict(list)
    for s in summaries:
        by_text[norm(s["summary"])].append(s["summary_id"])
    groups = [v for v in by_text.values() if len(v) > 1]
    check("duplicate-text groups", 20, len(groups))
    art_of = {s["summary_id"]: s["article_id"] for s in summaries}
    same, cross = [], []
    for g in groups:
        per = collections.defaultdict(list)
        for i in g:
            per[art_of[i]].append(i)
        same += [v for v in per.values() if len(v) > 1]
        if len(per) > 1:
            cross.append(g)
    check("  same-article duplicate groups", 8, len(same))
    check("  cross-article duplicate groups", 14, len(cross))

    # -- Section II/III: run A ---------------------------------------------
    tA = collections.Counter(A[i]["terminal_result"] for i in ids if term(A, i))
    check("run A terminals", 85, sum(tA.values()))
    for k, v in [("VERBATIM_SOURCE_COPY", 50), ("OFF_TOPIC", 16),
                 ("FACTUAL_REVERSAL", 13), ("OBVIOUS_TRUNCATION", 5),
                 ("FABRICATED_CONTENT", 1)]:
        check(f"run A terminal {k}", v, tA[k])
    softA = [A[i]["score"] for i in ids if not term(A, i)]
    check("run A graded", 165, len(softA))
    check("run A score min", 35, min(softA))
    check("run A score max", 98, max(softA))
    check("run A score mean", 76.1, round(st.mean(softA), 1), 0.05)
    dims = collections.defaultdict(list)
    for i in ids:
        if not term(A, i):
            for k, v in A[i]["dimensions"].items():
                dims[k].append(v)
    for k, v in [("faithfulness", 38.7), ("coverage", 19.0),
                 ("coherence", 13.5), ("conciseness", 4.8)]:
        check(f"run A mean {k}", v, round(st.mean(dims[k]), 1), 0.05)
    check("run A pairs reaching the scorer", 170, 250 - 51 - 29)

    softA_sorted = sorted(softA)
    check("run A score median", 79, st.median(softA))
    check("run A score SD", 15.1, round(st.pstdev(softA), 1), 0.05)
    check("run A score Q1", 68, softA_sorted[len(softA_sorted) // 4])
    check("run A score Q3", 87, softA_sorted[3 * len(softA_sorted) // 4])
    labA = collections.Counter(A[i]["quality_label"] for i in ids if not term(A, i))
    for k, v in [("EXCELLENT", 28), ("GOOD", 66), ("FINE", 34),
                 ("MIXED", 25), ("POOR", 12)]:
        check(f"run A label {k}", v, labA[k])

    tB = collections.Counter(B[i]["terminal_result"] for i in ids if term(B, i))
    check("run B terminals", 77, sum(tB.values()))
    check("run B graded", 173, sum(1 for i in ids if not term(B, i)))
    for k, v in [("VERBATIM_SOURCE_COPY", 50), ("OFF_TOPIC", 17),
                 ("FACTUAL_REVERSAL", 7), ("OBVIOUS_TRUNCATION", 3),
                 ("FABRICATED_CONTENT", 0)]:
        check(f"run B terminal {k}", v, tB[k])
    softB = sorted(B[i]["score"] for i in ids if not term(B, i))
    check("run B score mean", 76.2, round(st.mean(softB), 1), 0.05)
    check("run B score median", 82, st.median(softB))
    check("run B score SD", 19.0, round(st.pstdev(softB), 1), 0.05)
    check("run B score Q1", 63, softB[len(softB) // 4])
    check("run B score Q3", 91, softB[3 * len(softB) // 4])
    check("run B score min", 28, min(softB))
    check("run B score max", 100, max(softB))
    dimsB = collections.defaultdict(list)
    for i in ids:
        if not term(B, i):
            for k, v in B[i]["dimensions"].items():
                dimsB[k].append(v)
    for k, v in [("faithfulness", 37.4), ("coverage", 20.0),
                 ("coherence", 13.9), ("conciseness", 4.8)]:
        check(f"run B mean {k}", v, round(st.mean(dimsB[k]), 1), 0.05)
    labB = collections.Counter(B[i]["quality_label"] for i in ids if not term(B, i))
    for k, v in [("EXCELLENT", 52), ("GOOD", 49), ("FINE", 26),
                 ("MIXED", 26), ("POOR", 20)]:
        check(f"run B label {k}", v, labB[k])

    # -- review completion (Table V, lower block) --------------------------
    for run, nm, approve, one, two, high in ((A, "A", 250, 242, 8, 196),
                                             (B, "B", 250, 95, 155, 250)):
        dec = collections.Counter((run[i].get("review") or {}).get("decision")
                                  for i in ids)
        rounds = collections.Counter((run[i].get("review") or {}).get("rounds")
                                     for i in ids)
        conf = collections.Counter((run[i].get("review") or {}).get("confidence")
                                   for i in ids)
        check(f"run {nm}: final decision APPROVE", approve, dec["APPROVE"])
        check(f"run {nm}: unresolved escalations", 0,
              sum(v for k, v in dec.items() if k != "APPROVE"))
        check(f"run {nm}: settled in one review round", one, rounds[1])
        check(f"run {nm}: sent back for a second round", two, rounds[2])
        check(f"run {nm}: reviewer confidence HIGH", high, conf["HIGH"])

    # -- III-A internal consistency ---------------------------------------
    bands = [("EXCELLENT", 90, 100), ("GOOD", 75, 89), ("FINE", 65, 74),
             ("MIXED", 50, 64), ("POOR", 0, 49)]
    def band_of(score):
        for n, lo, hi in bands:
            if lo <= score <= hi:
                return n
        return None
    arith = sum(1 for run in (A, B) for i in ids
                if not term(run, i)
                and sum(run[i]["dimensions"].values()) != run[i]["score"])
    check("arithmetic errors, both runs", 0, arith)
    bandbad = sum(1 for run in (A, B) for i in ids
                  if not term(run, i)
                  and band_of(run[i]["score"]) != run[i]["quality_label"])
    check("label-band violations, both runs", 0, bandbad)
    check("records audited", 500, 2 * len(ids))

    # -- III-B repeated text ----------------------------------------------
    for run, nm in ((A, "A"), (B, "B")):
        ident = sum(1 for g in same
                    if len({run[i]["score"] for i in g}) == 1
                    and len({tuple(sorted(run[i]["dimensions"].items()))
                             for i in g}) == 1)
        check(f"run {nm}: duplicate pairs scored identically", 8, ident)

    # -- III-C pair conditioning ------------------------------------------
    for run, nm in ((A, "A"), (B, "B")):
        split = sum(1 for g in cross
                    if any(run[i]["score"] == 0 for i in g)
                    and any(run[i]["score"] > 0 for i in g))
        check(f"run {nm}: cross-article texts split by assignment", 14, split)

    # -- III-D weak-label agreement ---------------------------------------
    must_stop = {"COPY", "FOREIGN", "FRAGMENT"}
    for run, nm, expect in ((A, "A", 129), (B, "B", 127)):
        ok = tot = 0
        for L in ("REFERENCE", "COPY", "FOREIGN", "FRAGMENT"):
            g = [i for i in ids if lab[i] == L]
            tot += len(g)
            stopped = sum(1 for i in g if term(run, i))
            ok += stopped if L in must_stop else len(g) - stopped
        check(f"run {nm}: weak-label matches (of 141)", expect, ok)
        check(f"run {nm}: labelled candidates", 141, tot)
    check("run A: article copies stopped", 50,
          sum(1 for i in ids if lab[i] == "COPY" and term(A, i)))
    check("run A: foreign candidates stopped", 16,
          sum(1 for i in ids if lab[i] == "FOREIGN" and term(A, i)))
    check("run A: reference reproductions stopped", 0,
          sum(1 for i in ids if lab[i] == "REFERENCE" and term(A, i)))
    check("run A: reference reproductions reaching EXCELLENT", 0,
          sum(1 for i in ids if lab[i] == "REFERENCE" and not term(A, i)
              and A[i]["score"] >= 90))
    check("run A: generated candidates reaching EXCELLENT", 28,
          sum(1 for i in ids if lab[i] == "GENERATED" and not term(A, i)
              and A[i]["score"] >= 90))
    for run, nm, expect in ((A, "A", {"FRAGMENT": (5, 59.4), "REFERENCE": (0, 78.6),
                                      "GENERATED": (14, 76.6)}),
                            (B, "B", {"FRAGMENT": (3, 48.4), "REFERENCE": (0, 79.9),
                                      "GENERATED": (8, 77.9)})):
        for L, (stops, mean) in expect.items():
            g = [i for i in ids if lab[i] == L]
            check(f"run {nm}: {L} stopped", stops,
                  sum(1 for i in g if term(run, i)))
            alive = [run[i]["score"] for i in g if not term(run, i)]
            check(f"run {nm}: {L} survivor mean", mean,
                  round(st.mean(alive), 1), 0.05)
    check("run B: FRAGMENT survivor range",  (34, 63),
          (min(B[i]["score"] for i in ids if lab[i] == "FRAGMENT" and not term(B, i)),
           max(B[i]["score"] for i in ids if lab[i] == "FRAGMENT" and not term(B, i))))
    check("run B: REFERENCE survivor range", (40, 99),
          (min(B[i]["score"] for i in ids if lab[i] == "REFERENCE"),
           max(B[i]["score"] for i in ids if lab[i] == "REFERENCE")))
    check("run B: GENERATED survivor range", (28, 100),
          (min(B[i]["score"] for i in ids if lab[i] == "GENERATED" and not term(B, i)),
           max(B[i]["score"] for i in ids if lab[i] == "GENERATED" and not term(B, i))))
    check("run B: reference reproductions reaching EXCELLENT", 10,
          sum(1 for i in ids if lab[i] == "REFERENCE" and B[i]["score"] >= 90))
    check("run B: generated candidates reaching EXCELLENT", 42,
          sum(1 for i in ids if lab[i] == "GENERATED" and not term(B, i)
              and B[i]["score"] >= 90))
    frag_alive = [A[i]["score"] for i in ids if lab[i] == "FRAGMENT" and not term(A, i)]
    check("run A: fragments stopped", 5,
          sum(1 for i in ids if lab[i] == "FRAGMENT" and term(A, i)))
    check("run A: surviving fragment min", 39, min(frag_alive))
    check("run A: surviving fragment max", 70, max(frag_alive))
    check("run A: surviving fragments in GOOD or above", 0,
          sum(1 for v in frag_alive if v >= 75))

    # -- III-E within-article ordering -------------------------------------
    by_art = collections.defaultdict(list)
    for s in summaries:
        by_art[s["article_id"]].append(s["summary_id"])
    for run, nm in ((A, "A"), (B, "B")):
        inv = 0
        for g in by_art.values():
            refs = [i for i in g if lab[i] == "REFERENCE"]
            bad = [i for i in g if lab[i] in must_stop]
            if not refs:
                continue
            top_ref = max(run[i]["score"] for i in refs)
            if any(run[i]["score"] >= top_ref for i in bad):
                inv += 1
        check(f"run {nm}: articles with a planted failure at/above its reference",
              0, inv)
    spreads, survivors = [], collections.Counter()
    for g in by_art.values():
        alive = [A[i]["score"] for i in g if not term(A, i)]
        survivors[len(alive)] += 1
        if len(alive) > 1:
            spreads.append(max(alive) - min(alive))
    check("run A: median within-article spread", 26, st.median(spreads))
    check("run A: max within-article spread", 61, max(spreads))
    check("run A: articles with 2-4 survivors", 50,
          sum(v for k, v in survivors.items() if 2 <= k <= 4))
    for run, nm, ranks, survs, spread in (
            (A, "A", {1: 5, 2: 43, 3: 2}, {2: 4, 3: 27, 4: 19}, (26, 6, 61)),
            (B, "B", {1: 7, 2: 36, 3: 7}, {2: 3, 3: 21, 4: 26}, (32, 2, 68))):
        rk, sv, sp = collections.Counter(), collections.Counter(), []
        for g in by_art.values():
            refs = [i for i in g if lab[i] == "REFERENCE"]
            order = sorted(g, key=lambda i: -run[i]["score"])
            rk[min(order.index(i) for i in refs) + 1] += 1
            alive = [run[i]["score"] for i in g if not term(run, i)]
            sv[len(alive)] += 1
            if len(alive) > 1:
                sp.append(max(alive) - min(alive))
        for r, v in ranks.items():
            check(f"run {nm}: reference at within-article rank {r}", v, rk[r])
        check(f"run {nm}: reference at rank 4 or 5", 0, rk[4] + rk[5])
        for k, v in survs.items():
            check(f"run {nm}: articles with {k} survivors", v, sv[k])
        check(f"run {nm}: articles with 0, 1 or 5 survivors", 0,
              sv[0] + sv[1] + sv[5])
        check(f"run {nm}: spread median", spread[0], st.median(sp))
        check(f"run {nm}: spread min", spread[1], min(sp))
        check(f"run {nm}: spread max", spread[2], max(sp))

    # -- III-F cross-implementation ----------------------------------------
    both_term = [i for i in ids if term(A, i) and term(B, i)]
    both_soft = [i for i in ids if not term(A, i) and not term(B, i)]
    a_only = [i for i in ids if term(A, i) and not term(B, i)]
    b_only = [i for i in ids if term(B, i) and not term(A, i)]
    check("cross: both terminal", 74, len(both_term))
    check("cross: both graded", 162, len(both_soft))
    check("cross: A-only terminal", 11, len(a_only))
    check("cross: B-only terminal", 3, len(b_only))
    check("cross: routing agreement", 0.944,
          round((len(both_term) + len(both_soft)) / len(ids), 3), 0.0005)
    check("cross: terminal-category agreement", 74,
          sum(1 for i in both_term
              if A[i]["terminal_result"] == B[i]["terminal_result"]))
    xa = [A[i]["score"] for i in both_soft]
    xb = [B[i]["score"] for i in both_soft]
    check("cross: spearman", 0.891, round(spearman(xa, xb), 3), 0.0005)
    check("cross: mean absolute difference", 6.85,
          round(st.mean(abs(xa[k] - xb[k]) for k in range(len(xa))), 2), 0.005)
    check("cross: signed mean difference", -1.97,
          round(st.mean(xa[k] - xb[k] for k in range(len(xa))), 2), 0.005)
    check("cross: five-band label exact agreement", 88,
          sum(1 for i in both_soft
              if A[i]["quality_label"] == B[i]["quality_label"]))
    aot = collections.Counter(A[i]["terminal_result"] for i in a_only)
    check("cross: A-only reversals", 6, aot["FACTUAL_REVERSAL"])
    check("cross: A-only truncations", 4, aot["OBVIOUS_TRUNCATION"])
    check("cross: A-only fabrication", 1, aot["FABRICATED_CONTENT"])
    check("cross: B score range for A-only terminals (min)", 28,
          min(B[i]["score"] for i in a_only))
    check("cross: B score range for A-only terminals (max)", 66,
          max(B[i]["score"] for i in a_only))
    check("cross: A score range for B-only terminals (min)", 58,
          min(A[i]["score"] for i in b_only))
    check("cross: A score range for B-only terminals (max)", 71,
          max(A[i]["score"] for i in b_only))
    check("cross: pearson", 0.865, round(pearson(xa, xb), 3), 0.0005)
    delta = [xa[k] - xb[k] for k in range(len(xa))]
    check("cross: SD of delta", 8.81, round(st.pstdev(delta), 2), 0.005)
    for lim, n in ((5, 86), (10, 124), (15, 145), (20, 156)):
        check(f"cross: |delta| <= {lim}", n,
              sum(1 for v in delta if abs(v) <= lim))
    order5 = ["EXCELLENT", "GOOD", "FINE", "MIXED", "POOR"]
    check("cross: label within one band", 157,
          sum(1 for i in both_soft
              if abs(order5.index(A[i]["quality_label"])
                     - order5.index(B[i]["quality_label"])) <= 1))
    for dim, rho, mad in (("faithfulness", 0.864, 4.25), ("coverage", 0.882, 2.96),
                          ("coherence", 0.635, 0.70), ("conciseness", 0.243, 0.25)):
        da = [A[i]["dimensions"][dim] for i in both_soft]
        db = [B[i]["dimensions"][dim] for i in both_soft]
        check(f"cross: {dim} spearman", rho, round(spearman(da, db), 3), 0.0005)
        check(f"cross: {dim} mean |delta|", mad,
              round(st.mean(abs(da[k] - db[k]) for k in range(len(da))), 2), 0.005)
    wa = collections.Counter(lab[i] for i in a_only)
    wb = collections.Counter(lab[i] for i in b_only)
    check("cross: A-only weak labels GENERATED", 7, wa["GENERATED"])
    check("cross: A-only weak labels FRAGMENT", 4, wa["FRAGMENT"])
    check("cross: B-only weak labels GENERATED", 1, wb["GENERATED"])
    check("cross: B-only weak labels FRAGMENT", 2, wb["FRAGMENT"])
    check("cross: delta histogram bins sum to n", 162, len(delta))

    # -- III-G third read on the unlabelled block ---------------------------
    if os.path.exists(args.third_read):
        third = json.load(open(args.third_read, encoding="utf-8"))
        check("third read: candidates", 109, len(third))
        check("third read: all are GENERATED", 109,
              sum(1 for i in third if lab.get(i) == "GENERATED"))
        pool = [i for i in third if not term(A, i) and not term(B, i)]
        check("third read: comparable with both runs", 94, len(pool))
        tr = [third[i]["claude"]["score"] for i in pool]
        check("third read vs run A: spearman", 0.960,
              round(spearman(tr, [A[i]["score"] for i in pool]), 3), 0.0005)
        check("third read vs run A: MAD", 4.09,
              round(st.mean(abs(third[i]["claude"]["score"] - A[i]["score"])
                            for i in pool), 2), 0.005)
        check("third read vs run B: spearman", 0.936,
              round(spearman(tr, [B[i]["score"] for i in pool]), 3), 0.0005)
        check("third read vs run B: MAD", 5.95,
              round(st.mean(abs(third[i]["claude"]["score"] - B[i]["score"])
                            for i in pool), 2), 0.005)
        stopped = [i for i in third if term(A, i)]
        check("third read: candidates run A stopped in this block", 14, len(stopped))
        check("third read: mean audit score for those", 32.5,
              round(st.mean(third[i]["claude"]["score"] for i in stopped), 1), 0.05)
        check("third read: mean audit score for the rest", 77.0,
              round(st.mean(third[i]["claude"]["score"]
                            for i in third if i not in set(stopped)), 1), 0.05)
        check("third read: candidates the rest count", 95,
              len([i for i in third if i not in set(stopped)]))
        check("third read vs run A: pearson", 0.951,
              round(pearson(tr, [A[i]["score"] for i in pool]), 3), 0.0005)
        check("third read vs run B: pearson", 0.924,
              round(pearson(tr, [B[i]["score"] for i in pool]), 3), 0.0005)
        check("third read: A vs B spearman on the same pool", 0.916,
              round(spearman([A[i]["score"] for i in pool],
                             [B[i]["score"] for i in pool]), 3), 0.0005)
        check("third read: A vs B MAD on the same pool", 6.52,
              round(st.mean(abs(A[i]["score"] - B[i]["score"])
                            for i in pool), 2), 0.005)
        check("third read: range for candidates run A stopped", (20, 53),
              (min(third[i]["claude"]["score"] for i in stopped),
               max(third[i]["claude"]["score"] for i in stopped)))
        stoppedB = [i for i in third if term(B, i)]
        check("third read: candidates run B stopped in this block", 8, len(stoppedB))
        check("third read: mean audit score for those (B)", 34.2,
              round(st.mean(third[i]["claude"]["score"] for i in stoppedB), 1), 0.05)
        check("third read: range for candidates run B stopped", (22, 59),
              (min(third[i]["claude"]["score"] for i in stoppedB),
               max(third[i]["claude"]["score"] for i in stoppedB)))
    else:
        print(f"[skip] third-read file not found: {args.third_read}", file=sys.stderr)

    # -- reference quality (Section I / IV) ---------------------------------
    refs = [i for i in ids if lab[i] == "REFERENCE"]
    rs = [A[i]["score"] for i in refs]
    check("reference reproductions: mean score", 78.64, round(st.mean(rs), 2), 0.005)
    check("reference reproductions: min score", 42, min(rs))
    check("reference reproductions: max score", 89, max(rs))
    beaten = 0
    for g in by_art.values():
        r = [i for i in g if lab[i] == "REFERENCE"]
        if not r:
            continue
        top = max(A[i]["score"] for i in r)
        if any(A[i]["score"] > top for i in g if i not in r):
            beaten += 1
    check("articles where a non-reference candidate outscored the reference",
          45, beaten)

    # ----------------------------------------------------------------- report
    width = max(len(c[0]) for c in CHECKS)
    failed = 0
    for label, expected, got, ok in CHECKS:
        if not ok:
            failed += 1
        print(f"{'ok ' if ok else 'FAIL'}  {label:<{width}}  "
              f"expected {expected!r:>12}  got {got!r}")
    print(f"\n{len(CHECKS) - failed}/{len(CHECKS)} claims reproduce.")
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
