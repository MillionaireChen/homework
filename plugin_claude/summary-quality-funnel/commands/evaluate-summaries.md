---
description: Score article-summary pairs through the reference-free quality funnel (hard gates → embedding gate → dual-agent scoring)
---

Use the evaluate-summary-quality skill to evaluate the article-summary pair(s) described below. Follow the skill's cascade exactly: run the hard gates first, confirm every early exit with the summary-reviewer agent, run the embedding relevance gate on survivors when a local Ollama server is available, then score eligible candidates with the summary-scorer agent and review every draft with the summary-reviewer agent. Validate with scripts/validate_result.py before delivering, and rank within each article with scripts/rank_results.py when multiple summaries share an article.

Input: $ARGUMENTS
