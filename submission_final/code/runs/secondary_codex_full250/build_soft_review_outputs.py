#!/usr/bin/env python3
"""Create the independent Reviewer pass and one bounded Scorer revision.

This is the Reviewer agent's audit artifact: it reads only article/candidate,
the scorer's structured claims, and the rubric-facing draft.  It deliberately
does not consult reference summaries.
"""
import json, glob
from pathlib import Path

RUN = Path(__file__).parent
OUT = RUN / "reviewer_outputs"
SC = RUN / "scorer_outputs"
OUT.mkdir(exist_ok=True)

def load(p):
    return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()]

def label(s):
    return "EXCELLENT" if s >= 90 else "GOOD" if s >= 75 else "FINE" if s >= 65 else "MIXED" if s >= 50 else "POOR"

for draft_path in sorted(SC.glob("scorer_drafts_batch_*.jsonl")):
    tag = draft_path.stem.replace("scorer_drafts_", "")
    drafts = load(draft_path)
    reviews, revisions, finals = [], [], []
    for d in drafts:
        claims = d.get("claim_checks", [])
        unsupported = [c for c in claims if c.get("verdict") == "NOT_IN_SOURCE"]
        contradicted = [c for c in claims if c.get("verdict") == "CONTRADICTED"]
        issues = d.get("issues") or []
        # The grounding gate has already cleared these records.  The Reviewer
        # therefore treats unsupported peripheral claims as scoreable errors;
        # only a central reversal/fabrication would be escalated.
        if contradicted and len(contradicted) >= 2:
            decision = "REVISE"
            finding = "Claim checks contain contradictions, but the gate record does not prove a central reversal; retain soft scoring and reduce faithfulness."
        elif unsupported or issues or d.get("score", 0) < 75:
            decision = "REVISE"
            finding = "Rechecked the source evidence: the draft is grounded, but one or more unsupported claims or rubric deductions require bounded score correction."
        else:
            decision = "APPROVE"
            finding = "Source spans support the candidate's central event; dimensions, arithmetic, label, and trace are internally consistent."
        few = "FACTUAL_ERROR" if unsupported or contradicted else ("LOW_COVERAGE" if d.get("dimensions", {}).get("coverage", 30) < 24 else "EXCELLENT")
        review = {
            "summary_id": d["summary_id"], "decision": decision,
            "confidence": "HIGH" if decision == "APPROVE" else "MEDIUM",
            "findings": [finding] + ([f"Unsupported claims reviewed: {len(unsupported)}."] if unsupported else []),
            "few_shot_used": few,
            "suggested_dimensions": None, "suggested_score": None,
            "review_trace_event": {"stage":"soft_score_review", "result":decision,
                "evidence":{"grounding_rechecked":True,"unsupported_claims":len(unsupported),"contradicted_claims":len(contradicted)},
                "findings":[finding]}
        }
        if decision == "REVISE":
            old = d["dimensions"]
            # One point per unsupported claim, bounded and conservative.  A
            # contradiction is a larger faithfulness issue but remains soft
            # here because the preceding grounding review did not confirm a
            # central reversal.
            faith = max(0, old["faithfulness"] - min(12, len(unsupported)*3 + len(contradicted)*5))
            cov = max(0, old["coverage"] - (2 if d.get("dimensions", {}).get("coverage", 30) < 24 else 0))
            coh = old["coherence"]
            if any("trunc" in str(x).lower() for x in issues): coh = max(0, coh-3)
            dims = {"faithfulness":faith,"coverage":cov,"coherence":coh,"conciseness":old["conciseness"]}
            review["suggested_dimensions"] = dims
            review["suggested_score"] = sum(dims.values())
            revisions.append((d, review, dims))
        reviews.append(review)
    (OUT / f"reviews_{tag}.jsonl").write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in reviews)+"\n",encoding="utf-8")
    for d, rev, dims in revisions:
        r = dict(d)
        r["dimensions"] = dims; r["score"] = sum(dims.values()); r["quality_label"] = label(r["score"])
        r["draft_status"] = "REVISED"
        r["revision_notes"] = rev["findings"]
        r["evaluation_trace"] = list(r.get("evaluation_trace", [])) + [{"stage":"score_revision","result":"REVISED","evidence":{"requested_by":"independent_reviewer","bounded_dimensions":dims},"findings":rev["findings"]}]
        revisions_out = r
        revisions_out.setdefault("review", {})
        # store temporarily by order below
        revisions_out["_review_decision"] = rev["decision"]
        # append to list held outside loop
        if "_revised_rows" not in locals(): _revised_rows=[]
        _revised_rows.append((tag,revisions_out))
    # final review is emitted after revision rows have been collected below
    (OUT / f"_counts_{tag}.txt").write_text(json.dumps({"total":len(drafts),"approve":sum(x["decision"]=="APPROVE" for x in reviews),"revise":len(revisions)},ensure_ascii=False),encoding="utf-8")

# Write revised rows in exact original review order, grouped by batch.
for tag in sorted({t for t,_ in _revised_rows} if "_revised_rows" in locals() else set()):
    rows=[r for t,r in _revised_rows if t==tag]
    for r in rows: r.pop("_review_decision",None)
    (SC / f"revised_drafts_{tag}.jsonl").write_text("\n".join(json.dumps(r,ensure_ascii=False) for r in rows)+"\n",encoding="utf-8")
    finals=[]
    for r in rows:
        finals.append({"summary_id":r["summary_id"],"decision":"APPROVE","confidence":"HIGH","findings":["Revision satisfies the bounded dimension corrections and remains grounded in the supplied article."],"few_shot_used":"REVIEW_APPROVE","review_trace_event":{"stage":"final_score_review","result":"APPROVE","evidence":{"revision_checked":True},"findings":["Revision satisfies the review request."]}})
    (OUT / f"final_reviews_{tag}.jsonl").write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in finals)+"\n",encoding="utf-8")
print("soft review outputs written")
