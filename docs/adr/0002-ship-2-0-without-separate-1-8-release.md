# Ship 2.0.0 without a separate 1.8 release

Decision 0001 planned two releases: 1.8 to correct contradictions and score reporting, then 2.0 to introduce the rule registry. Both sets of work landed on the same branch and no 1.8.0 tag was ever cut. The last release tag is `antislop-v1.7.0`.

Version 2.0.0 ships directly from 1.7. Every shipped artifact, both CI version gates, and the production version assertion sit at 2.0.0.

Getting there took three passes that contradicted each other. `1fc71bc` set eight files to 1.8.0 but missed `.github/workflows/lint-skills.yml` and the production version test, so the two CI systems expected different versions and the test suite failed on a clean tree. `d234f06` repeated the same downgrade across all ten sites on a separate branch. Both are reverted.

Keep 0001 for the registry rationale, which still holds. Its closing argument for keeping 1.8 separate does not describe what shipped.
