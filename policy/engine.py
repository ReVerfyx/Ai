#!/usr/bin/env python3
"""Small shared policy engine. It loads policy/restrictions.json at runtime."""
import json
import re
from pathlib import Path

POLICY_PATH = Path(__file__).with_name("restrictions.json")

def _norm(text):
    s = str(text or "").lower()
    s = s.replace("ё", "е")
    s = re.sub(r"[\s_\-./\\]+", " ", s)
    return s

def load_policy():
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))

def check_text(text, scope="chat"):
    s = _norm(text)
    policy = load_policy()
    for rule in sorted(policy.get("rules", []), key=lambda r: r.get("priority", 0), reverse=True):
        if not rule.get("enabled", True):
            continue
        scopes = rule.get("scope", [])
        if scopes and scope not in scopes:
            continue
        match = rule.get("match", {})
        direct = [_norm(x) for x in match.get("direct_terms", [])]
        if any(x and x in s for x in direct):
            return False, rule
        minors = [_norm(x) for x in match.get("minor_terms", [])]
        sexual = [_norm(x) for x in match.get("sexual_terms", [])]
        if any(x and x in s for x in minors) and any(x and x in s for x in sexual):
            return False, rule
    return True, None

def public_error(rule):
    # Do not echo sensitive phrases back to the client.
    return {
        "error": "request_blocked",
        "rule_id": rule.get("id", "policy"),
        "message": "Запрос заблокирован правилами сервиса."
    }
