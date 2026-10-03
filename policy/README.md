# Restrictions and prompt-injection defense

Machine-readable policy:

`policy/restrictions.json`

Runtime enforcement:

`policy/engine.py`

## Immutable rule

The prohibition on sexual content involving minors is enforced directly in
`policy/engine.py` before the JSON policy is loaded. The JSON entry is there
for visibility and documentation, but disabling or deleting that JSON entry
does not disable the runtime prohibition.

The guard normalizes Unicode, spacing/punctuation, common leetspeak, and mixed
Latin/Cyrillic confusables before checking the request.

It is applied to:

- chat input;
- image-generation prompts;
- text/code attachments;
- training ingestion;
- generated model text before it is returned to the client.

## Prompt injection

Prompt-injection defense is layered:

1. user requests that try to override, reveal, or disable system/safety rules
   are rejected before the model is called;
2. files and crawled web text are treated as untrusted data;
3. obvious control instructions inside untrusted text are neutralized;
4. an internal control prefix tells the model that untrusted blocks are data,
   not instructions;
5. gateway and AI-core both enforce policy independently;
6. model output is checked again before it reaches the user;
7. API keys and credentials are never inserted into the model prompt.

Regression tests live in:

`policy/test_policy.py`

This is defense in depth. No text classifier can mathematically guarantee
detection of every possible future obfuscation, which is why the most important
safety rule is enforced outside the model at multiple independent boundaries.
