# Method: FandomWatch

## Outputs
| Output | Definition | Caveat |
|---|---|---|
| sentiment | Lexicon score per comment with negation (3-token window) and intensifiers; label = sign | Unvalidated until you run `fandom-eval` on your own labelled CSV. Sarcasm and slang defeat it |
| aspect sentiment | Each *sentence* is attributed to the aspects it mentions and scored on its own | Keyword aspects only |
| narratives | Greedy single-pass TF-IDF clustering (cosine >= 0.25, min size 3) | Recurring themes, not a topic-model claim |
| backlash | Day's negative share is a robust-z outlier (>= 3.5, MAD floored), share >= 35%, >= 10 negatives, >= 20 comments that day; consecutive days merge | Returns nothing with fewer than 6 usable days |
| conversation share | Title's comments / all tracked comments | Mention-based; sensitive to what you ingest |

## Limits you should state in any write-up
- The default classifier is a lexicon: transparent and dependency-free, weak on sarcasm, slang and negation beyond three tokens. Measure it on your own labels (`fandomwatch fandom-eval labels.csv --save`) before trusting any number, or compare it with an LLM (`--llm`).
- Narrative clusters are recurring themes, not a topic-model claim. Aspect sentiment is keyword-based.
- Backlash detection needs enough volume per day and returns nothing with fewer than 6 usable days; it flags *when and about what*, not *why*.
- Conversation share is mention-based and depends on what you ingested.
