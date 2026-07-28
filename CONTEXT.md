# Antislop

Antislop defines an opinionated writing standard and a companion assessment for formulaic writing patterns.

## Language

**Writing rule**:
A named instruction that identifies or corrects a formulaic writing pattern.
_Avoid_: Detector, heuristic

**Finding**:
One observed match between text and a writing rule.
_Avoid_: Detection, hit

**Primary finding**:
The single scored finding assigned to a text span when several writing rules overlap.
_Avoid_: Main violation

**Related finding**:
An overlapping finding reported for context without another score deduction.
_Avoid_: Duplicate violation

**Document-level finding**:
A finding based on a pattern across a document or materially independent section rather than one phrase.
_Avoid_: Global violation

**Formulaic Writing Risk Score**:
A score measuring conformance to the Antislop standard. It does not identify the author or prove AI use.
_Avoid_: AI detector score, authorship score

**Writing profile**:
A named set of writing rules selected for a medium or register.
_Avoid_: Mode, preset

**Rule registry**:
The canonical machine-readable source for writing rule definitions and generation metadata.
_Avoid_: Rules database, config

**Generated artifact**:
A skill or reference file rendered deterministically from the rule registry.
_Avoid_: Derivative copy

**Evaluation fixture**:
An input and observable expectation used to assess skill behavior.
_Avoid_: Unit test
