# Pattern reference for audit scoring

Use this reference when running antislop-audit to look up severity levels and rule descriptions for each pattern.

## Banned vocabulary — High severity each
delve, leverage, tapestry, testament, vibrant, pivotal, utilize, synergy, holistic, seamless, groundbreaking, cutting-edge, innovative, dynamic, embark, foster, revolutionize, transformative, empower, unlock, supercharge, commence, obtain, facilitate, subsequently, discontinue, dispatch, ascertain, navigate, unpack, enhance, showcase, interplay

## Banned phrases — High severity each
- "It's worth noting that"
- "In today's fast-paced world" / "in today's landscape" / "ever-evolving landscape"
- "At its core" / "at the end of the day" / "the real question is" / "what really matters" / "fundamentally" / "in reality" / "the deeper issue is"
- "Let's dive in" / "let's delve deeper"
- "Not just X, but Y"
- "Game-changer" (without specific metrics)
- "Treasure trove" / "uncharted waters" / "embark on a journey"
- "It cannot be denied that"
- "This underscores the importance of"
- "As of my knowledge cutoff"
- "Research shows" / "experts believe" (without named source)
- "Despite challenges, continues to thrive"
- "The future looks bright" / "exciting times ahead"
- "In the realm of" / "dynamic world of"
- "Let that sink in" — emphasis crutch
- "Full stop." / "Period." — emphasis crutch (standalone as sentence)
- "Make no mistake" — emphasis crutch
- "Let me be clear" — throat-clearing opener
- "I want to explore..." — meta-commentary
- "This is what X actually looks like" — telling instead of showing
- "creeps in" — performative emphasis (e.g. "mediocrity creeps in")
- "Here's the thing:" / "Here's what [X]" / "Here's why [X]" / "Here's the problem though:" — "here's what/this/that/why" throat-clearing
- "Hint:" / "Plot twist:" / "Spoiler:" — self-referential asides
- "Let me walk you through..." — announcing structure
- "Think about it:" — condescending prompt
- "And that's okay." — unnecessary permission-granting
- "With that in mind" / "Against this backdrop" / "Taken together" / "Zooming out" / "Building on this" — transition glue
- "This is more complex than it appears" / "The reality is more nuanced" / "It's complicated" — performing nuance instead of demonstrating it
- "As I explored this further" / "What I found surprised me" / "The more I looked" — narrating the learning process instead of delivering what was learned

## Banned openers and closers — Medium severity each
- "In conclusion" / "To summarize" / "To wrap up"
- "Certainly" / "Absolutely" / "Great question"
- "You're absolutely right" / "That's a great point"
- "I hope this helps!" / "Let me know if you have questions!"
- "Moreover" / "Furthermore" / "Additionally" (flag each instance as medium severity)
- "So" as paragraph opener

## Em-dash rules
- Any em-dash → **High severity**. No exceptions.
- Flag every instance separately.

## Scare quotes — High severity each
Any word in quotes where the quotes signal ironic distance rather than a direct quotation. E.g. you know the "type", "innovative" solution.

## Bolding rules
- Random bolding (word bolded with no clear reason) → **Medium severity** per instance
- Ambiguous bolded bullet (bold claim not supported by following text) → **Medium severity** per instance

## Structural patterns — Medium severity each
- Generic action-describing link text ("click here", "learn more", etc. as standalone anchor text — context matters: product UI buttons and marketing CTAs are not AI tells)
- Rule of three in a single sentence
- Overlong sentence (3+ ideas, or 2+ qualifiers/disclaimers crammed in)
- Antithesis ("not just X, but Y", "not X, but Y") — decorative contrast that fails the remove-the-clause test
- Negative parallelism / trailing negation ("it's not about X, it's about Y", Reframe-without-adding, trailing fragments like "..., no guessing")
- Copula avoidance ("serves as", "boasts", "features", "functions as", "stands as" when "is"/"has" would do)
- Parataxis — 3+ consecutive short declarative sentences with no conjunctions or subordination
- Passive voice / subjectless fragments ("No configuration file needed", "Results are preserved automatically")
- Excessive hedging ("could potentially possibly", "it might have some effect", "it could be argued that")
- Rhetorical emphasis tail ("..., that's the thing", "..., that's the hard truth", "..., and that's what matters")
- Moralizing tails — "Why it matters:", "Here's what I learned:", "This shows that..." tacked on without earning the takeaway
- Bullet-point crutch — bullet lists used to dodge writing full paragraphs when prose communicates more clearly
- Awkward AI metaphors — analogies that gesture toward meaning without achieving it. Generic, plausible, unanchored to specific experience.
- Generic subject loops (3+ sentences opening with the same vague pronoun or impersonal construction)
- Synonym cycling (protagonist / main character / central figure)
- False range ("from X to Y" as rhetorical filler)
- Superficial -ing analysis ("highlighting", "underscoring", "symbolizing", "reflecting" tacked onto sentence ends to add fake depth)
- Promotional language ("nestled within the breathtaking...")
- Formulaic challenge framing ("despite challenges, continues to thrive")
- Announcing structure ("First I'll discuss... then I'll cover...")
- Generic conclusions ("The future looks bright")
- Notability name-dropping — listing media outlets without what any said
- Fragmented headers — heading followed by one-line restatement
- Negation flip — stating what something isn't before what it is, as padding
- Paragraph-level redundancy — same concept restated across paragraphs or concluding sentence restating the paragraph
- Triplet overlap — 3+ descriptors naming the same quality
- Artificial line breaks — prose broken mid-sentence at terminal width (~80 chars)
- All paragraphs the same length — uniform paragraph length with no variation
- Simile-as-adverb — "with the [noun] of someone [verb]ing"
- Hedged reactions — "a laugh that isn't quite a laugh"
- Temperature-as-emotion — hot/cold replacing specific emotional description
- Physical tell clichés — jaw/throat/breath/hands as interchangeable emotion props
- Anthropomorphized silence — "the silence stretched" treats silence as an actor
- Ending clichés — "And for now, that was enough" summary posing as closure
- Catalog prose — paragraphs that are only names, milestones, feature labels with no material consequence
- System-tour prose — paragraphs mapping one-to-one with predictable category buckets
- Concession rhythm — "not X, but Y" or "may sound X, but Y" used reflexively across paragraphs
- Type-definition endings — "the kind of X where Y" as default paragraph closure appearing multiple times
- Uniform sentence length — monotonous sentences in a narrow length band with no variation
- Weak verb constructions — "work to ensure", "seek to address", "begin to understand"
- Empty declaratives — sentences performing significance without substance: "This matters", "Everything is connected"
- Transformation chains — three or more sequential sentences claiming a change: "X became Y. Y became Z."
- Transition glue — "With that in mind", "Against this backdrop", "Zooming out"
- Complexity signalling — "This is more complex than it appears", "It's complicated"
- Discovery narration — "As I explored this further", "What I found surprised me"
- Wisdom sandwich — paragraph framed by bookend aphorisms with the framing doing the work the middle should do
- Corrective reveals — "You've been told X. Here's the truth: Y"
- Punchy one-liner closure — every paragraph ending with a short dramatic standalone sentence
- "It turns out" as throat-clearing opener
- Standalone "Because" fragments — "Because she can't bear to look."

## Structural patterns — High severity each
- Rhetorical-question hooks — "The kicker?", "The issue?", "The twist?", "Do you know what I realized?" as openers
- Balanced-take hedging — "While X is true, we must also consider Y" as sentence scaffold
- Specificity theater — unverifiable specifics deployed to pass a "be concrete" check
- Significance inflation ("pivotal moment in the evolution of...")

## Formatting — Low severity each
- Title Case Headings
- Inline-header lists (**Term:** description)
- Compound-modifier over-hyphenation (before-noun vs. after-noun, -ly adverb compounds, ever- compounds)
- Curly quotes — should be straight quotes
- Filler phrases ("in order to", "due to the fact that", "at this point in time", "the system has the ability to")
- Emojis in prose
- Exclamation mark overuse (any in technical/factual prose, or more than one in conversational)
- Semicolon overuse (2+ per paragraph — sophistication signal; exceptions: formal or academic register)

## Chatbot artifacts — High severity each
- "I hope this helps!"
- "Let me know if you have questions!"
- "Great question!"
- "Certainly!" / "Absolutely!"
- Cutoff disclaimers ("While details are limited based on available information...")
