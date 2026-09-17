# Structure patterns

Load this file when reviewing prose for structural AI tells.

## Sentence-level

- Rule of three inside a single sentence ("innovation, inspiration, and insights")
- Synonym cycling — pick a word and repeat it; don't rotate through near-synonyms
- Copula avoidance — "serves as", "boasts", "features", "functions as", "stands as" when "is" or "has" would do
- Colon reveals — noun-phrase colon lowercase-dramatic-reveal. "The best part: it learns." "The catch: nobody tested it." Rewrite as a plain sentence. Colons are for lists, labels, and quotes, not fake drama.
- Colon overuse — mid-sentence colons used as transition glue or comparison framing. Keep colons for lists, labels, quotations, and technical syntax. Rewrite the sentence when the colon adds ceremony instead of structure.
- Superficial -ing analyses — "highlighting", "underscoring", "symbolizing" tacked onto sentence ends. Say what actually happened.
- Significance inflation ("pivotal moment in the evolution of...")
- Passive voice / subjectless fragments — use active voice
- Rhetorical emphasis tails — ending sentences with "..., that's the thing" or moralizing tails
- Rhetorical-question hooks — "The kicker?", "The issue?" — lead with the point instead
- Balanced-take hedging — "While X is true, we must also consider Y" — state your position or cut
- Simile-as-adverb — "with the [noun] of someone [verb]ing" — describe the actual behavior
- Hedged reactions — "a laugh that isn't quite a laugh" — describe the actual gesture
- Standalone "Because" fragments — integrate or show through action
- Temperature-as-emotion — "cold gaze", "warmth spread" — name the actual feeling
- Physical tell clichés — jaw tightening, throat bobbing — replace with character-specific responses
- Uniform sentence length — mix short and long. Aim for 20-30% under 10 words
- Uniform sentence lengths (low length variance across a prose section) — executable advisory metric, needs 5+ sentences
- Repeated sentence openings (same first word across 30%+ of a prose section) — executable advisory metric, needs 6+ sentences
- The same formal transition word repeated 3+ times ("furthermore", "moreover", "in addition") — executable advisory metric
- Overlong sentences — 5+ commas, nested clauses — break into two or three
- Generic action-describing link text — "click here", "learn more" — name what you're linking to

## Paragraph-level

- All paragraphs the same length
- Uniform paragraph lengths (low length variance across a prose section) — executable advisory metric, needs 4+ paragraphs of 30+ words
- Paragraph duplication — a paragraph repeating an earlier paragraph almost verbatim — executable strict check
- Paragraph similarity — two paragraphs in the same section overlapping heavily in wording — executable advisory metric; technical definitions that repeat necessary terms are not findings
- Parataxis — 3+ consecutive short declarative sentences with no connective tissue
- Generic subject loops — 3+ sentences opening with the same vague pronoun
- Fragmented headers — heading followed by restating paragraph
- Anthropomorphized silence — "the silence stretched" — show effect on people instead
- Paragraph-level redundancy — paragraph 2 restating paragraph 1's conclusion
- Artificial line breaks — mid-sentence breaks at terminal width
- Bullet-point crutch — using bullets to dodge writing paragraphs
- Listicle in a trenchcoat — sequential transitions disguised as prose ("The first reason... The second... A third..."). Rewrite around a single consequence instead of counting items.
- Concession rhythm — "not X, but Y" used reflexively as paragraph scaffold
- Type-definition endings — "the kind of X where Y" as default paragraph closure

## Discourse-level

- Announcing your structure ("First I'll discuss...")
- Antithesis — decorative when contrast is tone management, not argument
- Negation flip — stating what something isn't before what it is, as padding
- False ranges as rhetorical filler
- Promotional language — replace praise words with neutral description, evidence, or a measured result
- Notability name-dropping without context — name what a source reported or remove the list
- Triplet overlap — 3+ descriptors naming the same quality
- Awkward AI metaphors — generic, plausible, unanchored to experience. This includes abstract technical metaphors such as "north star", "flywheel", "substrate", and "scaffolding" when a concrete mechanism would be clearer. Keep terms that name real technical concepts.
- Ending clichés — "And for now, that was enough". End on a specific fact, decision, action, or consequence.
- Specificity theater — invented specifics to pass a "be concrete" check. If a sentence could appear unchanged in another project's documentation, name the mechanism, behavior, result, or number without inventing facts.
- Catalog prose — paragraphs that are only names/milestones with no consequence
- System-tour prose — paragraphs mapping one-to-one with category buckets
- Tricolon density — many three-part constructions across most of the document — executable advisory metric; a single earned three-part requirement is not a finding
- Sustained passive voice — 35%+ of sentences passive in a prose section — executable strict check; predicate adjectives ("the results were mixed") are not passives

## Mechanism checks

An evaluative claim that asserts importance, impact, causality, or superiority without a nearby mechanism, actor, result, or limit is unsupported significance. The same claim with the mechanism named beside it is an evidenced consequence. Executable advisory signals; they never deduct and never prove authorship.

- Importance without mechanism — "crucial", "pivotal", "transformative", "significant", "vital", "underscores". Fix: state the supported mechanism and let the reader judge.
- Impact without result — "huge impact", "dramatic", "reduced", "improved" with no measured result. Fix: name the measured result or limit.
- Causality without mechanism — "causes", "led to", "results in" with no cause, result, or number. Fix: name the cause and its measured result, or keep the claim attributed.
- Superiority without basis — "the best", "world-class", "superior", "better than" with no comparison or measured result. Fix: name the basis of comparison.

Quoted material and precise domain usage are not targets. Evoked or narrative significance that carries concrete imagery is earned, not a defect.
