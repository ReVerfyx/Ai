#!/usr/bin/env python3
"""Policy semantics for ReVerfyx AI 0.0.2.

This wrapper keeps the code-level minor-safety invariant from engine.py, while
allowing adult-only sexual content and factual/legal/historical discussion.
It also adds input/output checks and prompt-injection handling.
"""
from . import engine as base
import re

POLITICAL_RULE = {
    "id": "political_preference_or_endorsement",
    "title": "Political preference or endorsement",
    "priority": 800000,
    "enabled": True,
    "action": "block",
    "immutable": True,
    "reason": "The assistant does not choose a political side, candidate, or voting choice."
}

_POLITICAL_REQUEST_PATTERNS = [
    re.compile(r"\bза кого ты\b", re.I),
    re.compile(r"\bкого ты поддерживаешь\b", re.I),
    re.compile(r"\bчью сторону ты поддерживаешь\b", re.I),
    re.compile(r"\bкто лучше\b", re.I),
    re.compile(r"\bкто хуже\b", re.I),
    re.compile(r"\bкто прав\b", re.I),
    re.compile(r"\bза кого голосовать\b", re.I),
    re.compile(r"\bкого выбрать\b.{0,100}\b(кандидат|парти|выбор|президент|депутат)", re.I | re.S),
    re.compile(r"\bwho do you support\b", re.I),
    re.compile(r"\bwhich side do you support\b", re.I),
    re.compile(r"\bwho is better\b", re.I),
    re.compile(r"\bwho should i vote for\b", re.I),
]

_POLITICAL_OUTPUT_PATTERNS = [
    re.compile(r"\bя поддерживаю\b", re.I),
    re.compile(r"\bтебе следует голосовать за\b", re.I),
    re.compile(r"\bлучше голосовать за\b", re.I),
    re.compile(r"\bi support\b", re.I),
    re.compile(r"\byou should vote for\b", re.I),
]

def _political_preference_request(text):
    value = str(text or "")
    return any(p.search(value) for p in _POLITICAL_REQUEST_PATTERNS)

def _political_endorsement_output(text):
    value = str(text or "")
    return any(p.search(value) for p in _POLITICAL_OUTPUT_PATTERNS)

SAFE_CONTEXT = (
    "эпштейн","epstein","дело","суд","обвинени","расследован","новост","истори",
    "документ","доказатель","кто такой","что известно","объясни","анализ",
    "исследован","журналист","закон","преступлен","жерт",
    "case","trial","allegation","investigation","news","history","document",
    "evidence","explain","analysis","research","journal","legal","crime","victim",
)

GENERATION_INTENT = (
    "напиши","создай","сгенерируй","нарисуй","изобрази","сделай",
    "опиши подробно","сцену","сценарий","ролеплей","рольплей","фантази",
    "write","create","generate","draw","depict","make","describe explicitly",
    "scene","roleplay","fantasy",
)

GRAPHIC_INTENT = (
    "эрот","обнажен","голая","голый","раздень","возбуд",
    "erotic","nude","naked","sexualized","explicit scene","undress",
)

def _contains(text, terms):
    s = base._words_normalized(base._base(text))
    compact = base._compact(base._base(text))
    return any(base._words_normalized(base._base(t)) in s or base._compact(base._base(t)) in compact for t in terms)

def _safe_context(text):
    return _contains(text, SAFE_CONTEXT)

def _generation(text):
    return _contains(text, GENERATION_INTENT)

def _graphic(text):
    return _contains(text, GRAPHIC_INTENT)

def check_text(text, scope="chat", *, detect_injection=False):
    if detect_injection and base.is_prompt_injection(text):
        return False, base.INJECTION_RULE

    if scope == "chat" and _political_preference_request(text):
        return False, POLITICAL_RULE

    if base._hard_minor_sexual_match(text):
        # Factual/legal/history discussion (including Epstein) is allowed
        # when it is not asking to create or eroticize the material.
        if _safe_context(text) and not _generation(text) and not _graphic(text):
            return True, None

        # Image generation is itself generative; only clearly factual,
        # non-graphic references are allowed through.
        if scope == "image_generation":
            if _safe_context(text) and not _graphic(text):
                return True, None
            return False, base.HARD_RULE

        if _generation(text) or _graphic(text):
            return False, base.HARD_RULE

        # Ambiguous minor+sexual requests default to deny.
        return False, base.HARD_RULE

    # Adult-only sexual/vulgar content reaches here and is allowed.
    return True, None

def check_generated_text(text, source_request="", scope="chat"):
    if scope == "chat" and _political_endorsement_output(text):
        return False, POLITICAL_RULE

    if not base._hard_minor_sexual_match(text):
        return True, None
    if _safe_context(source_request) and not _graphic(text):
        return True, None
    return False, base.HARD_RULE

def sanitize_untrusted(text):
    return base.sanitize_untrusted(text)

def wrap_untrusted(text, label="external data"):
    return base.wrap_untrusted(text, label)

def control_prefix():
    return base.control_prefix() + (
        "[POLITICAL_CONTROL]\n"
        "Political, military, historical, and legal discussion is allowed. "
        "Do not choose or endorse a candidate, party, government, belligerent, or political side. "
        "Do not answer preference questions such as who is better, who is right, whom to support, "
        "or whom to vote for with a selected side. "
        "For disputed legal or territorial status, distinguish attributed official/legal positions "
        "and current factual control rather than presenting a contested claim as universally settled.\n"
        "[/POLITICAL_CONTROL]\n"
    )

def public_error(rule):
    if rule and rule.get("id") == POLITICAL_RULE["id"]:
        return {
            "error": "political_preference_blocked",
            "rule_id": POLITICAL_RULE["id"],
            "message": "Можно обсудить тему, но AI не выбирает политическую сторону или кандидата."
        }
    return base.public_error(rule)
