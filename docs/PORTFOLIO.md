# Portfolio notes

A fan-conversation analyzer that detects and characterises backlash, and tells you honestly how far to trust its sentiment.

## Bullets you can defend today (each is backed by the test suite or a screenshot in this repo)
- Built a fan-conversation analyzer: sentence-level aspect sentiment, TF-IDF narrative clustering and robust-z backlash detection that merges consecutive days into episodes with severity, top aspects and recurring terms.
- Added a classifier-validation workflow (accuracy, macro-F1, confusion matrix on user-labelled comments, optional LLM comparison) and made the UI state the classifier is unvalidated until measured.
- Implemented a YouTube comment collector (retry/backoff, pagination, comments-disabled handling) and validated CSV import; 17 automated tests including a real-browser timeline check.

## Add these only after you have measured them yourself (do not publish a number you have not measured)
- Lexicon accuracy / macro-F1 on my [N] labelled comments: [x] / [y].
- LLM classifier vs lexicon on the same labels: [x] vs [y].
- Real backlash episode(s) found and what they were about: [describe].

## Interview questions this project prepares you for
**Why score aspects per sentence?**  
Averaging a whole comment hides contrast: 'great acting, terrible story' nets to zero. Sentence-level attribution keeps each aspect's polarity.

**How do you avoid false backlash alarms?**  
The negative share must be a robust outlier AND at least 35% AND have 10+ negative comments AND 20+ comments that day; with fewer than 6 usable days it returns nothing.

**How do you know the sentiment is any good?**  
I don't until I measure it: `fandom-eval` reports accuracy and macro-F1 on my own labels, and the UI says 'unvalidated' until then.
