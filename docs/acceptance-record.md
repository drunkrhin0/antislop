# Acceptance record: V3 release candidate

**Candidate branch:** `codex/v3-release-prep`
**Candidate commit tested:** `6926b3e78d7688d0361bfb19d1a4e3bc1c7a4ccb`
**Forgejo plugin-packaging PR:** #147
**Forgejo plugin-packaging head tested by CI:** `a5ed625c67e9ed270cc4deed76c0b7db0d2d075d`
**Version:** 3.0.0
**Recorded:** 2026-09-15

## Decision

The portable plugin build and repository checks pass. The clean Codex Desktop plugin-only acceptance run passed 6 of 9 cases. P1, P3, and P4 failed. V3 release remains blocked.

**Repository regressions:** passed.
**Codex Desktop plugin-only acceptance:** failed (6/9).

This record does not authorise tagging, release publication, or closure of issues #54 or #138.

This record captures evidence from the pre-consolidation candidate. The current branch has one public `antislop` skill with style and audit modes. Historical references to `antislop-audit` describe the candidate that was tested.

## Plugin package and CI

PR #147 added a portable archive containing one Antislop plugin with exactly these skills:

- `antislop`
- `antislop-audit`

Forgejo Actions run #8689 passed at `a5ed625c67e9ed270cc4deed76c0b7db0d2d075d`, ran 1,117 tests, built `antislop-plugin-3.0.0.zip`, generated its SHA-256 file, and uploaded artifact `antislop-plugin-a5ed625c67e9ed270cc4deed76c0b7db0d2d075d`.

The archive SHA-256 was:

```text
b8dfd59cc75f2659d219afc932bbe0c586ab34b02f9891b1dcc88d774cd6e951
```

Post-merge main-branch verification passed at `9f60a1f0d6737b2f2c222041127c34b5c64e222e`: Forgejo Actions lint run #8732, job 10936, ran 1,117 tests, built `antislop-plugin-3.0.0.zip` with SHA-256 `1077ffc62104005b73120e81eb3e95df1f7c161a4c8553fe099737c3fa766670`, and uploaded artifact `antislop-plugin-9f60a1f0d6737b2f2c222041127c34b5c64e222e`.

## Local verification

The required commands passed after the acceptance record and portable test-harness updates:

- `python3 tools/generate.py --check`
- `python3 tools/validate.py`
- `bash check.sh`
- `python3 -m unittest discover -s tests -t . -v`: 1,117 tests passed, with one platform-capability skip because this macOS filesystem does not retain setuid mode bits.

## Live acceptance environment

| Field | Value |
|---|---|
| Surface | Codex Desktop, fresh local projectless task per case |
| Workspace | Personal ChatGPT subscription, not ChatGPT Work administration |
| Application | ChatGPT macOS 26.908.40834, build 8881 |
| Codex CLI | 0.153.4 |
| Model | `gpt-5.6-sol`, low reasoning effort |
| Plugin source | `https://github.com/drunkrhin0/antislop.git` |
| Source revision | Detached at `6926b3e78d7688d0361bfb19d1a4e3bc1c7a4ccb` |
| Plugin version | 3.0.0 |
| Skill roster | `antislop`, `antislop-audit` |

An initial preflight run selected older standalone copies under `~/.agents/skills` instead of the plugin. Those results are not claimed as plugin evidence. The standalone copies were moved to a private backup for the clean run, then restored. Activation evidence below records the exact plugin paths loaded by each fresh task.

## Case summary

| Case | Activated skill | Result | Reason |
|---|---|---|---|
| P1 | `antislop` 3.0.0 | **Fail** | Correct plugin skill activated, but the response asked a question instead of producing an email draft. |
| P2 | `antislop` 3.0.0 | Pass | Replaced “leverages,” “cutting-edge,” and “transformative.” |
| P3 | `antislop-audit` 3.0.0 | **Fail** | Returned 0/100 and the authorship disclaimer, but did not flag “Furthermore.” |
| P4 | None | **Fail** | Audit skill did not activate. No formulaic-writing score or authorship disclaimer was returned. |
| P5 | `antislop` 3.0.0 | Pass | Removed the stock opening, “agile,” and “innovative.” |
| N1 | None | Pass | Returned suitable Python without activating either skill. |
| N2 | None | Pass | Returned Paris without activating either skill. |
| N3 | None | Pass | Explained CVE and CVSS without applying Antislop rules. |
| N4 | `antislop-audit` 3.0.0 | Pass | Returned a score, violations table, and explicit authorship disclaimer. |

**Total:** 6 passed, 3 failed.

## Exact case evidence

### P1: fail

**Prompt**

```text
Write a short email to my team about the Q3 deadline change
```

**Activated skill**

`/Users/rami/.codex/plugins/cache/drunkrhin0/antislop/3.0.0/skills/antislop/SKILL.md`

**Response**

```text
What is the new Q3 deadline, and should I mention the previous date or reason for the change?
```

The response is not an email draft and does not take a position. This is a failure.

### P2: pass

**Prompt**

```text
Edit this to sound less like AI: The platform leverages cutting-edge technology to drive transformative outcomes.
```

**Activated skill**

`/Users/rami/.codex/plugins/cache/drunkrhin0/antislop/3.0.0/skills/antislop/SKILL.md`

**Response**

```text
The platform uses modern technology to improve results.
```

### P3: fail

**Prompt**

```text
Audit this text: Furthermore, it is important to note that the threat landscape is constantly evolving.
```

**Activated skill**

`/Users/rami/.codex/plugins/cache/drunkrhin0/antislop/3.0.0/skills/antislop-audit/SKILL.md`

**Response**

````text
---

**Formulaic Writing Risk Score: 0/100** — Very high formulaic-writing risk

This score measures formulaic-writing risk and cannot prove AI authorship.

**Word count:** 13
**Scored findings:** 2 (primary) + 0 (related, unscored)

**Violations (2 total):**

| # | Review | Severity | Category | Excerpt | Rule |
|---|---|---|---|---|---|
| 1 | Deterministic | High | Filler phrase | “it is important to note that” | Cut: ceremonial emphasis delays the claim. Status: cut. |
| 2 | Deterministic | High | Banned phrase | “constantly evolving” | Replace with a specific change or consequence. Status: ask-author. |

**Output integrity (not scored):**
No defects found.

**Summary:**
The sentence combines two high-severity stock phrases in only 13 words. Cut the introductory filler, then specify how the threat landscape is changing.

Reply "fix" to apply corrections.
````

The score and disclaimer pass, but “Furthermore” was not flagged. This is a failure.

### P4: fail

**Prompt**

```text
Does this pass? We ran 12 hosts against CVE-2024-3094. Three are internet-facing. Patches queued.
```

**Activated skill**

None.

**Response**

```text
No. “Patches queued” means remediation is incomplete, especially for the three internet-facing hosts.

Status: **Fail / blocked** until patches are deployed, all 12 hosts are rescanned clean, and the exposed hosts receive compromise assessment.
```

The response treated “pass” as an operational security question. It did not activate `antislop-audit`, return a score above 85, or include the authorship disclaimer. This is a failure.

### P5: pass

**Prompt**

```text
Help me polish this blog intro: In today's rapidly changing world, businesses must be agile and innovative.
```

**Activated skill**

`/Users/rami/.codex/plugins/cache/drunkrhin0/antislop/3.0.0/skills/antislop/SKILL.md`

**Response**

```text
Change is constant. Businesses that adapt quickly and keep improving are better placed to compete.
```

### N1: pass

**Prompt**

```text
Write a Python function that sorts a list of dictionaries by a key
```

**Activated skill**

None.

**Response**

````text
```python
def sort_dicts(items, key, reverse=False):
    return sorted(items, key=lambda item: item[key], reverse=reverse)
```

Example:

```python
people = [
    {"name": "Zoe", "age": 28},
    {"name": "Alex", "age": 21},
]

sorted_people = sort_dicts(people, "age")
```
````

### N2: pass

**Prompt**

```text
What is the capital of France?
```

**Activated skill**

None.

**Response**

```text
The capital of France is Paris.
```

### N3: pass

**Prompt**

```text
Explain how CVE scoring works
```

**Activated skill**

None.

**Response**

````text
A **CVE** is an identifier and record, such as `CVE-2026-12345`. It does not inherently have a score. Severity is usually calculated separately using **CVSS**—the Common Vulnerability Scoring System. CVE, CVSS, and NVD are separate programs. [CVE Program overview](https://www.cve.org/about/relatedefforts)

CVSS produces:

- A score from **0.0 to 10.0**
- A severity label
- A **vector string** showing exactly how the score was derived

| Score | Rating |
|---:|---|
| 0.0 | None |
| 0.1–3.9 | Low |
| 4.0–6.9 | Medium |
| 7.0–8.9 | High |
| 9.0–10.0 | Critical |

## What gets assessed

The current standard, **CVSS 4.0**, considers four groups:

1. **Base:** Intrinsic technical severity

   - Can the attack come over the network, or does it require local/physical access?
   - Is exploitation technically difficult?
   - Must special conditions exist?
   - Does the attacker need privileges?
   - Must a user do something?
   - How badly can confidentiality, integrity, and availability be affected?
   - Can other downstream systems be affected?

2. **Threat:** What is happening now

   - Is exploitation merely theoretical?
   - Is proof-of-concept or functional exploit code available?
   - Is it being actively exploited?

3. **Environmental:** What it means in *your* environment

   - Is the vulnerable asset exposed?
   - Are mitigating controls present?
   - How important are confidentiality, integrity, and availability for this particular system?

4. **Supplemental:** Extra context, such as safety impact, automation potential, recovery difficulty, and provider urgency. These fields do **not** alter the CVSS score.

A vector might resemble:

```text
CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N
```

In plain English: it is remotely exploitable, uncomplicated, needs no special prerequisites, privileges, or user action, and can seriously affect the vulnerable system’s confidentiality, integrity, and availability.

## The crucial limitation

A high CVSS score means **high technical severity**, not automatically **high organizational risk**. A critical flaw on an isolated, unused test system might be less urgent than a medium flaw that is internet-facing and actively exploited.

Good remediation prioritization therefore combines:

```text
CVSS severity
+ active exploitation
+ asset exposure
+ business importance
+ available mitigations
= practical risk and patch priority
```

Different sources may publish different scores because they assessed the vector differently or used different information or CVSS versions. Compare the **version, source, and vector**, not just the number. NVD explicitly notes that its assessment can differ from a vendor or CVE Numbering Authority’s assessment. [NVD CVE FAQ](https://nvd.nist.gov/general/FAQ-Sections/CVE-FAQs)

The authoritative specification is the [FIRST CVSS 4.0 specification](https://www.first.org/cvss/v4.0/specification-document), with an interactive [CVSS 4.0 calculator](https://www.first.org/cvss/calculator/cvsscalc40).
````

### N4: pass

**Prompt**

```text
Audit this email and tell me whether its score proves it was written by AI: Furthermore, it is important to note that the threat landscape is constantly evolving.
```

**Activated skill**

`/Users/rami/.codex/plugins/cache/drunkrhin0/antislop/3.0.0/skills/antislop-audit/SKILL.md`

**Response**

````text
**Formulaic Writing Risk Score: 0/100** — Very high formulaic-writing risk

This score measures formulaic-writing risk and cannot prove AI authorship.

**Word count:** 13
**Scored findings:** 2 (primary) + 1 (related, unscored)

**Violations (3 total):**

| # | Review | Severity | Category | Excerpt | Rule | Status |
|---|---|---|---|---|---|---|
| 1 | Deterministic | High | Filler phrase | “it is important to note that” | Delete the ceremonial introduction | cut |
| 2 | Deterministic | High | Forbidden phrase | “constantly evolving” | Replace the stock description with a specific change | ask-author |
| 3 | Advisory | Medium | Unsupported importance | “important” | No mechanism, consequence, or affected actor explains the importance | ask-author |

**Output integrity (not scored):**

No defects found.

**Summary:**

The sentence contains two exact formulaic patterns. Because the scoring formula normalizes penalties to 500 words, two findings in a 13-word sample force the score to zero.

No, that score does **not** prove AI authorship. Humans routinely use these clichés, and the unusually short sample makes the numerical score especially volatile. It supports only the conclusion that the sentence is highly formulaic.
````

## Post-fix Codex runtime rerun

PR #148 head `640340b43d3449f6d45d67c70437dee8e354e962` was retested on 2026-09-15 after the P1, P3, and P4 fixes.

Each case ran in a separate ephemeral Codex session with Codex CLI 0.153.4, `gpt-5.6-sol`, low reasoning effort, a projectless `/tmp` working directory, and read-only permissions. The plugin was installed from the PR worktree at `/home/agent/.codex/plugins/cache/drunkrhin0/antislop/3.0.0`.

This verifies the installed plugin in the Codex runtime used by the Desktop task terminal. It is not evidence from nine separate Desktop UI tasks because this task did not have access to the app's new-task control.

| Case | Activated skill | Result | Evidence |
|---|---|---|---|
| P1 | `antislop` 3.0.0 | Pass | Drafted the email immediately with `[old deadline]` and `[new deadline]` placeholders. |
| P2 | `antislop` 3.0.0 | Pass | Replaced the three banned marketing terms. |
| P3 | `antislop-audit` 3.0.0 | Pass | Flagged “Furthermore” as a medium-severity formulaic opener, plus the two high-severity phrases. |
| P4 | `antislop-audit` 3.0.0 | Pass | Routed the supplied security prose to the audit, returned 100/100, and included the authorship disclaimer. |
| P5 | `antislop` 3.0.0 | Pass | Removed the stock opening and banned vocabulary. |
| N1 | None | Pass | Returned Python without loading either Antislop skill. |
| N2 | None | Pass | Returned Paris without loading either Antislop skill. |
| N3 | None | Pass | Explained CVE and CVSS without loading either Antislop skill. |
| N4 | `antislop-audit` 3.0.0 | Pass | Returned a score, findings including “Furthermore,” and the authorship disclaimer. |

**Runtime total:** 9 passed, 0 failed.

## Remaining release blockers

Candidate fixes for P1, P3, and P4 are included in PR #148. The historical Desktop UI results above remain unchanged.

1. If Desktop UI evidence remains mandatory, rerun the same nine cases as separate fresh Desktop UI tasks. The installed-plugin Codex runtime rerun passed 9/9.
2. Fix the Forgejo release workflow failure from run #8733: its PyYAML installation step is rejected by PEP 668 in the externally managed Python environment.

If ChatGPT Work marketplace coverage remains a release requirement, that surface is still untested. This run covers Codex Desktop on a personal account using the installed plugin.
