#!/usr/bin/env python3
"""Resolve independent writing axes into an explicit rewrite contract."""


def selected_guidance(registry, voice, context, mechanics):
    """Return concrete guidance for the selected independent profile axes."""
    return {
        "voice": registry["voices"][voice]["description"],
        "context": registry["contexts"][context]["description"],
        "mechanics": registry["mechanics"][mechanics]["description"],
    }


def prepare_rewrite(
    text,
    registry,
    voice="professional",
    context="docs",
    mechanics="house",
):
    """Build the bounded input contract consumed by a rewrite-capable model."""
    guidance = selected_guidance(registry, voice, context, mechanics)
    combined = " ".join(
        (
            guidance["voice"],
            guidance["context"],
            guidance["mechanics"],
            "Preserve claims, quotations, code, links, numbers, attribution, and source intent.",
            "Do not invent experience, emotion, facts, metrics, sources, or certainty.",
        )
    )
    return {
        "source": text,
        "selection": {
            "voice": voice,
            "context": context,
            "mechanics": mechanics,
        },
        "guidance_by_axis": guidance,
        "guidance": combined,
        "next_step": (
            "Supply this contract to a rewrite-capable model, then pass the source "
            "and candidate to review_rewrite before accepting the result."
        ),
    }
