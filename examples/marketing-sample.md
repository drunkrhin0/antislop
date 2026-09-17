# RC 3.0.0 demo: marketing profile overlay

This file exercises the PR #83 marketing profile. The marketing rules
only fire under `--profile marketing` and never under general.

    cat examples/marketing-sample.md | python3 tools/score.py --stdin --profile marketing
    cat examples/marketing-sample.md | python3 tools/score.py --stdin --profile general

A beacon of progress, nestled within a plethora of options, our
product can unleash a myriad of results and boasts a simple setup.
Ordinary facts remain unchanged to pad this sample above the scoring
minimum so the comparison is visible.