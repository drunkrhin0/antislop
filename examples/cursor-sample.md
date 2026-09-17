# RC 3.0.0 demo: Cursor structural rules (PR #82)

This file exercises the Cursor-derived structural rules from PR #82.
The numbered-list inflation detector is automated; the colon-overuse
rule is a manual-review (human-check) rule, so it appears in the
manual-review metadata rather than as an automated finding.

    cat examples/cursor-sample.md | python3 score.py --stdin
    cat examples/cursor-sample.md | python3 scan.py

The article gives five reasons:

1. Faster setup for teams.
2. Faster onboarding for teams.
3. Faster reviews for teams.
4. Faster delivery for teams.
5. Faster reporting for teams.

The migration was a success: it created a strong foundation: it
unlocked growth across the board. Ordinary facts remain unchanged to
pad this sample above the scoring minimum.