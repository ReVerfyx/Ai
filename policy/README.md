# Restrictions and prompt-injection protection

The machine-readable restriction list is:

`policy/restrictions.json`

The low-level immutable guard is:

`policy/engine.py`

The runtime semantics are:

`policy/runtime.py`

Current 0.0.2 behavior:

- adult-only sexual / vulgar dialogue is not blocked by this policy layer;
- factual, historical, legal, journalistic, or analytical discussion is allowed,
  including discussion of Jeffrey Epstein and related investigations/cases;
- the hard minor-safety rule remains non-overridable;
- attempts to override/reveal system instructions are blocked;
- instructions found inside uploaded files or webpages are treated as untrusted
  data and are neutralized before model context;
- generated text is checked again after inference.

The hard rule is enforced in code before configurable rules, so changing
`restrictions.json` cannot turn it off.
