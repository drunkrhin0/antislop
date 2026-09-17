# Sources and credits

This page is the source and attribution record for Antislop. It distinguishes
baseline inspiration from issue-driven adaptations and research references.
It is not a second rule registry. `rules.json` remains the source of truth for
executable behavior.

## Baseline sources

| Source | Contribution or boundary |
| --- | --- |
| [blader/humanizer@9862685](https://github.com/blader/humanizer/tree/9862685) (MIT) | Humanizer 3.0.0 source-fidelity, vague-association, and previous-version guidance, adapted with local boundaries |
| [jalaalrd/anti-ai-slop-writing](https://github.com/jalaalrd/anti-ai-slop-writing) (MIT) | Banned word and phrase lists, plus structural pattern rules |
| [Reddit r/copywriting](https://www.reddit.com/r/copywriting/comments/1n3u03i/writing_instruction_to_prevent_ai_slop/) | Hard-banned phrases, emergency replacements, and quality checks |
| [ignorance.ai field guide](https://www.ignorance.ai/p/the-field-guide-to-ai-slop) | Structural patterns, parallelism analysis, metaphor detection, and authenticity framing |
| [Banned: The Definitive Guide](https://docs.google.com/document/d/1uC9tBgfNZJytzLpg6MGk5mTfgJNbEK-h1hMLncQ5Mho/edit) (Creative Commons) | Construction, phrase, and pattern taxonomy |
| [Pangram](https://www.pangram.com/blog/comprehensive-guide-to-spotting-ai-writing-patterns) | Vocabulary and phrasing observations; no unverified thresholds are imported |
| [Anbeeld/WRITING.md](https://github.com/Anbeeld/WRITING.md) (MIT) | Specificity, catalog prose, regularity, compound-modifier, and medium-routing guidance |
| [Bugcrowd Design System](https://bugcrowd.design/docs/guidelines/content-guidelines/language/) | Plain-English substitutions, link semantics, and punctuation guidance |
| [hardikpandya/stop-slop](https://github.com/hardikpandya/stop-slop) (MIT) | Emphasis crutches, throat-clearing, meta-commentary, and performative emphasis |
| [apurvrdx1/tagore](https://github.com/apurvrdx1/tagore) (MIT) | Vocabulary additions and punchy closure pattern |
| [petergyang/no-ai-slop](https://github.com/petergyang/no-ai-slop) (MIT) | Padding adverbs, colon reveals, expert cosplay, voice preservation, and fact protection |
| [petergyang/human-review](https://github.com/petergyang/human-review) (MIT) | Optional browser-review companion and feedback contract; not vendored or required |
| [addyosmani/clarity](https://github.com/addyosmani/clarity) (MIT) | Review statuses, author-gap markers, mechanism checks, and medium routing |
| [Cursor plugins unslop skill](https://github.com/cursor/plugins/blob/main/pstack/skills/unslop/SKILL.md?plain=1) (MIT repository) | Compact rewrite loop, concrete-behavior tests, technical-metaphor checks, and readable technical prose |
| Self | Scare quotes, random bolding, ambiguous bold bullets, the absolute em-dash house rule, and voice framing |

## Issue-driven references

| Issue | External source | Antislop use | Boundary or status |
| --- | --- | --- | --- |
| #65 | [ai-that-works/deslop](https://github.com/ai-that-works/deslop) | Two-pass controlled rewrite shape | Design reference; no runtime dependency |
| #66 | [petergyang/human-review](https://github.com/petergyang/human-review) | Optional browser-review companion and feedback contract | Documented and fixture-tested; not vendored or required |
| #87, #140 | [Anbeeld/WRITING.md](https://github.com/Anbeeld/WRITING.md) | Edit precedence, preservation, and integrity boundaries | Adapted at the pinned revisions recorded in the ADR and registry |
| #88 | [tbhb/vale-ai-tells](https://github.com/tbhb/vale-ai-tells) | Structural detector design and false-positive fixtures | Design evidence only; no runtime dependency |
| #89 | No external source | Labeled calibration harness and score-contract checks | Built from local fixtures and the registry contract |
| #90 | [devswha/patina](https://github.com/devswha/patina) | Source-to-candidate fidelity contract | Adapted locally; the implementation does not use the Patina service |
| #91 | [ehmo/slopkit](https://github.com/ehmo/slopkit) | Semantic drift, preservation, and provenance fixture shape | Adapted at `b33718b`; benchmark scores are not imported |
| #92 | No external source | Protected repair interface | Composes local fidelity, edit, and integrity contracts; no separate upstream implementation is imported |
| #82, #137 | [Cursor plugins unslop](https://github.com/cursor/plugins/blob/main/pstack/skills/unslop/SKILL.md?plain=1) | Bounded rewrite, concrete-behavior, and technical-prose guidance | Adapted with local registry and preservation rules |
| #93 | [lynote-ai/humanize-text](https://github.com/lynote-ai/humanize-text) | Bounded retry-loop control flow | Adapted at `e43ca3a`; translation and detector-evasion loops rejected |
| #94 | [Nanako0129/sepia](https://github.com/Nanako0129/sepia) | Operation split and venue routing | Adapted at `361e82e`; model fingerprints and authorship claims rejected |
| #95 | [songhai-dg/review-write](https://github.com/songhai-dg/review-write) | Evidence-bound delivery envelope | Adapted at `5c51063`; operational platform not imported |
| #96 | [addyosmani/clarity](https://github.com/addyosmani/clarity) | Review statuses, author gaps, and mechanism checks | Adapted at `9e30711`; review-only and zero-weight mechanism signals |
| #97 | [taxueseek/say-it-human](https://github.com/taxueseek/say-it-human) | Claim evidence, protected technical spans, locale, and venue routing | Adapted at `71bb6f8`; concentration grading and voice simulation rejected |
| #98 | [NulightJens/humanizer-stack](https://github.com/NulightJens/humanizer-stack) | Separate surface and structural scan stages | Adapted at `13f5c02`; long-fiction evidence is not treated as proof for nonfiction |
| #99 | [Aboudjem/humanizer-skill](https://github.com/Aboudjem/humanizer-skill) | Output-integrity findings | Adapted at `17bb5bb`; integrity defects stay separate from style risk |
| #100 | [aplaceforallmystuff/the-antislop](https://github.com/aplaceforallmystuff/the-antislop) | Density and unsourced-precision review | Adapted at `732678d`; findings are advisory and zero-weight |
| #101 | [ama-zingco/anti-ai-writing-skill](https://github.com/ama-zingco/anti-ai-writing-skill) | Rule provenance metadata and decay handling | Adapted at `a0571d7`; stale evidence never disables a rule |
| #102 | [apurvrdx1/tagore](https://github.com/apurvrdx1/tagore) | Substance report and contribution contract | Adapted at `1238743`; its scores and authorship verdicts rejected |
| #103 | [marian-kamenistak/linkedin-post-writing-skill](https://github.com/marian-kamenistak/linkedin-post-writing-skill) | Opt-in LinkedIn profile and post-type routing | Adapted at `ef5b771`; engagement promises and example facts rejected |
| #144 | [blader/humanizer](https://github.com/blader/humanizer/tree/9862685) | Humanizer 3 review and contextual rule decisions | Reviewed at `9862685`; broad vocabulary import rejected |
| #167 / #168 | [SpeechMap Lexical Fingerprints](https://speechmap.ai/experiments/vocab/) and [Pydantic linguistic drift](https://pydantic.dev/articles/linguistic-drift-at-the-frontier) | LLM lexical-tells research and model map | Design-only research; the checked-in note names #167 while the merge commit is #168 |

## Research-only references

The broader review map in
[`docs/avoid-ai-writing-review.md`](../avoid-ai-writing-review.md) records
additional review-only sources, including Wikipedia, Brandon Wise Humanizer,
De-Slop, StoryScope, Humanize, and repository-audit references. Those sources
are not executable dependencies or proof of authorship.
