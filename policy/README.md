# Restrictions

The machine-readable restriction list is:

`policy/restrictions.json`

The runtime checker is:

`policy/engine.py`

The list is intentionally separate from the model code so rules can be reviewed
and changed without retraining model weights. Version 0.0.2 starts with the
highest-priority prohibition requested for the service. Gateway/API endpoints
apply it before sending prompts to the model.

Add future restrictions as additional objects in the JSON `rules` array.
