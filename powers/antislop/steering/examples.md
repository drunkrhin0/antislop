# Examples

Load this file to see concrete before/after examples of antislop rule applications.

**Paragraph-level redundancy (inter-paragraph):**
❌ "The new pipeline cut deploy time by 40%. Teams went from 20-minute deploys to under 12. This reduction in deploy time means teams ship faster and get feedback sooner."
✅ "The new pipeline cut deploy time by 40%. Teams went from 20-minute deploys to under 12. Engineers stopped context-switching while waiting for builds, and the QA team cleared their backlog in a week."

**Paragraph-level redundancy (intra-paragraph restatement):**
❌ "We migrated to the new API in Q2. The migration took three weeks and involved updating 12 services. Overall, this was a significant migration that required substantial effort."
✅ "We migrated to the new API in Q2. The move took three weeks, touched 12 services, and broke billing twice before we got it right."

**Triplet overlap:**
❌ "The system must be current, documented, and auditable." (all three mean "reliable for attestation")
✅ "The system must be auditable." (or pick the one that matters)

**Negation flip:**
❌ "This isn't a support desk. The goal is to give engineers a self-service debugging toolkit."
✅ "Engineers get a self-service debugging toolkit instead of filing tickets."

**Antithesis (decorative):**
❌ "The API is not philosophical, just functional." (remove "not philosophical" — nothing changes)
✅ "The API is functional." (or better: state what it actually does)

**Antithesis (load-bearing):**
❌ "Not just a linter, but a full audit pipeline." (if the reader would assume "just a linter")
✅ "A full audit pipeline: linting, dependency scanning, and license compliance." (state what it does instead)

**Superficial -ing analyses:**
❌ "Response times dropped 30% last quarter, highlighting the effectiveness of the new caching layer."
✅ "Response times dropped 30% last quarter. The new caching layer was responsible — it moved the 95th percentile from 800ms to 120ms."

**Moralizing tails:**
❌ "We shut down the legacy monolith in March. Two years of planning, six months of migration, one outage. Why it matters: teams now own their own deployments end to end."
✅ "We shut down the legacy monolith in March. Two years of planning, six months of migration, one outage. Teams now own their own deployments end to end."

**Balanced-take hedging:**
❌ "While microservices offer flexibility, we must also consider that monoliths are simpler to operate."
✅ "Microservices solved our scaling problem but gave us a debugging problem. For teams under 10 engineers, a monolith is still the right call."

**Bullet-point crutch:**
❌ "The new onboarding flow improves the experience. • Welcome email with clear CTA. • Guided setup wizard with tooltips. • Personalized dashboard with relevant widgets. • Achievement badges for completing milestones."
✅ "The new onboarding flow drops you into a guided setup wizard. You get a welcome email, sure, but the real work happens in the wizard. Tooltips walk you through each step. By the time you reach the dashboard, it's already populated with your actual data, not placeholder widgets."
