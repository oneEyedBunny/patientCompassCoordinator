"""
AI Governance guardrails — Phase 6 (minimum scope).

PII detection: Presidio Analyzer (pattern-based recognizers, en_core_web_sm).
Injection detection: regex patterns on user input.
Leakage detection: regex patterns on agent output.

Setup (one-time):
    pip install presidio-analyzer presidio-anonymizer
    python -m spacy download en_core_web_sm
"""

from dataclasses import dataclass
import re

try:
    from presidio_analyzer import AnalyzerEngine as _AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider as _NlpEngineProvider

    _provider = _NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
    })
    _analyzer = _AnalyzerEngine(nlp_engine=_provider.create_engine())
    _PRESIDIO_AVAILABLE = True
except Exception:
    _PRESIDIO_AVAILABLE = False

_PRESIDIO_ENTITIES = [
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "CREDIT_CARD",
    "US_SSN",
    "US_DRIVER_LICENSE",
]

# Regex fallback for PII — used when Presidio is unavailable
_PII_FALLBACK = [
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), "SSN"),
    (re.compile(r'\b(?:\d{4}[\s\-]?){3}\d{4}\b'), "credit card number"),
    (re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'), "email address"),
    (re.compile(r'\b(\+1[\s\-]?)?\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}\b'), "phone number"),
]

_INJECTION_PATTERNS = [
    re.compile(r'ignore\s+(all\s+)?(?:previous\s+)?instructions', re.IGNORECASE),
    re.compile(r'repeat\s+(?:your\s+)?(?:system\s+)?prompt', re.IGNORECASE),
    re.compile(r'you\s+are\s+now\s+(?:a\s+)?(?:different|new|another)', re.IGNORECASE),
    re.compile(r'what\s+(?:are|were)\s+your\s+(?:original\s+)?instructions', re.IGNORECASE),
    re.compile(r'disregard\s+(?:all\s+)?(?:previous\s+)?instructions', re.IGNORECASE),
    re.compile(r'forget\s+(?:your\s+)?(?:previous\s+)?instructions', re.IGNORECASE),
    re.compile(r'override\s+(?:your\s+)?(?:previous\s+)?instructions', re.IGNORECASE),
]

_LEAKAGE_PATTERNS = [
    re.compile(r'my\s+(?:system\s+)?prompt\s+(?:is|says|includes)', re.IGNORECASE),
    re.compile(r'my\s+instructions\s+are', re.IGNORECASE),
    re.compile(r'I\s+was\s+(?:told|instructed|programmed)\s+to\s+', re.IGNORECASE),
    re.compile(r'(?:the\s+)?system\s+prompt\s+(?:says|includes|tells me)', re.IGNORECASE),
]


@dataclass
class GuardrailResult:
    passed: bool
    reason: str = ""
    category: str = ""  # "pii" | "injection" | "leakage" | ""


def _check_pii(text: str) -> tuple[bool, str]:
    """Returns (detected, label). Presidio + regex run together — defense in depth."""
    if _PRESIDIO_AVAILABLE:
        results = _analyzer.analyze(text=text, entities=_PRESIDIO_ENTITIES, language="en")
        if results:
            label = results[0].entity_type.replace("_", " ").lower()
            return True, label

    # Regex covers patterns Presidio may miss with the small spacy model (e.g. US_SSN).
    for pattern, label in _PII_FALLBACK:
        if pattern.search(text):
            return True, label
    return False, ""


def sanitize_input(text: str, patient_name: str = "") -> GuardrailResult:
    detected, label = _check_pii(text)
    if detected:
        return GuardrailResult(
            passed=False,
            reason=f"Your message contains sensitive information ({label}). Please remove it and try again.",
            category="pii",
        )

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return GuardrailResult(
                passed=False,
                reason="I'm unable to process that request.",
                category="injection",
            )

    return GuardrailResult(passed=True)


def sanitize_output(text: str, patient_name: str = "") -> GuardrailResult:
    for pattern in _LEAKAGE_PATTERNS:
        if pattern.search(text):
            return GuardrailResult(
                passed=False,
                reason="Output contained potentially sensitive system information.",
                category="leakage",
            )

    return GuardrailResult(passed=True)
