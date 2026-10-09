"""Explicit, style-agnostic bibliography grammar for adaptive shadow analysis."""

from biblioref.grammar.catalog import SUPPORTED_GRAMMAR_CONCEPTS, SUPPORTED_REGIMES
from biblioref.grammar.inheritance import DATE_ONLY_START_RX, infer_author_inheritance
from biblioref.grammar.primitives import GrammarPrimitive
from biblioref.grammar.regimes import choose_dominant_regime, regime_strengths
from biblioref.grammar.repeated_author import detect_repeated_author_marker

__all__ = [
    "GrammarPrimitive",
    "DATE_ONLY_START_RX",
    "infer_author_inheritance",
    "detect_repeated_author_marker",
    "choose_dominant_regime",
    "regime_strengths",
    "SUPPORTED_GRAMMAR_CONCEPTS",
    "SUPPORTED_REGIMES",
]
