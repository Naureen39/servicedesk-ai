# Security review

This document records the results of the security scans run against the backend and
frontend as part of Phase 9 hardening: static analysis (bandit), dependency vulnerability
scanning (pip-audit, npm audit), and an assessment of dynamic scanning feasibility (OWASP
ZAP). It also records the engineering decisions made in response to each finding.

## Static analysis: bandit (backend)

Scanned: `backend/app`, 6,133 lines of code.

```
Total issues (by severity):
    Undefined: 0
    Low: 4
    Medium: 28
    High: 0
```

No high-severity findings. All 32 findings were reviewed individually; none required a code
change. They fall into four categories.

### B608, hardcoded SQL expressions (27 findings, Medium severity, Low confidence)

All 27 are in `app/api/v1/analytics.py`, where each analytics query builds its SQL as an
f-string. Bandit flags any f-string handed to a SQL execution call, but every one of these
follows the same safe pattern used throughout this module:

- The f-string only ever splices in a small, fixed set of literal string fragments defined in
  the same file (for example an optional `loc_clause` of `"AND location_id = :location_id"` or
  `""`, chosen from a closed set of hardcoded options, never built from request input).
- Every actual value from the request (dates, location IDs, etc.) is passed through a
  SQLAlchemy bind parameter (`:from_date`, `:to_date`, `:location_id`, ...) and never
  concatenated into the string itself.

Because the interpolated fragments are drawn from a fixed set of hardcoded literals rather
than from user input, there is no injection vector here. Reviewed and accepted as false
positives; no change made.

### B106, hardcoded password funcarg (1 finding, Low severity)

`app/api/v1/auth.py:123`, `LoginResponse(access_token="", expires_in=0, mfa_required=True, ...)`.
This is the response returned when a login succeeds but MFA is still required: there is no
access token yet by design, so the field is an empty string, not a password. Reviewed and
accepted as a false positive.

### B105, hardcoded password string (2 findings, Low severity)

- `app/schemas/auth.py:11`, an OpenAPI example value (`"correct horse battery staple"`) shown
  in the login endpoint's Swagger docs. Not a real credential.
- `app/services/dialog/templates.py:37`, a canned chat message
  (`TOKEN_BUDGET_EXCEEDED = "This conversation has covered a lot of ground..."`). Bandit's
  heuristic matches any string assigned to a variable with certain naming patterns; this is
  user-facing copy, not a credential.

Both reviewed and accepted as false positives.

### B615, unsafe Hugging Face download (1 finding, Medium severity)

`app/services/nlu/sentiment.py:46`, `AutoTokenizer.from_pretrained(...)` without a pinned
revision. The model name is a hardcoded constant
(`distilbert-base-uncased-finetuned-sst-2-english`), not attacker-controlled, and the model is
downloaded once at first run and then served from a local `models/` volume thereafter, so the
unpinned-revision risk (upstream repo content changing between deploys) is real but low.
Accepted as a reviewed risk rather than pinning a revision hash, to avoid the model silently
going stale; revisit if this becomes a compliance requirement.

### B311, weak PRNG (1 finding, Low severity)

`app/services/scheduling/booking.py:41`, `generate_reference_code()` uses `random.choices` to
build a 6-digit confirmation reference code (e.g. `MRD-482913`). This code is a
customer-facing lookup convenience, not a security credential: it is never used for
authentication, authorization, or as a secret, and booking mutations still require the
authenticated staff session (see the RBAC matrix in `backend/tests/test_rbac_matrix.py`) or,
for the public self-service endpoints, the reference code plus the customer's own contact
details. Reviewed and accepted; `secrets`-based generation is not warranted here.

## Dependency scanning: pip-audit (backend)

`transformers==4.57.6` is the only package with known vulnerabilities, all in code paths this
project does not exercise:

| ID | Summary | Vulnerable path |
| --- | --- | --- |
| PYSEC-2025-217 | X-CLIP checkpoint conversion deserializes untrusted data | Checkpoint conversion scripts (not used) |
| PYSEC-2026-2288 | `Trainer._load_rng_state()` calls `torch.load` on an untrusted checkpoint | `Trainer` class (not used; this project only runs inference) |
| PYSEC-2026-2289 | Malicious `config.json` from an attacker-controlled repo can achieve RCE | Loading arbitrary/attacker-supplied HF repos (this project loads exactly one hardcoded model name, `distilbert-base-uncased-finetuned-sst-2-english`) |
| PYSEC-2026-2290 | LightGlue model loading path allows RCE from an attacker-controlled repo | LightGlue models (not used; this is a text sentiment classifier) |
| PYSEC-2026-3929 | Path traversal in `save_pretrained()` via a crafted `chat_template` | Requires an attacker-controlled `chat_template` value passed to `save_pretrained`; this project only calls `save_pretrained` on its own locally-exported ONNX model, never with external input |

**Decision:** do not force-upgrade `transformers`. An upgrade to a fixed version
(`>=5.0.0rc3`/`5.3.0`/`5.10.0` depending on the CVE) was attempted and installs cleanly on its
own, but breaks a real, load-bearing constraint: `optimum-onnx==0.1.0`, which powers the
sentiment classifier's ONNX export/inference path, requires `transformers<4.58.0,>=4.36`.
Verified with `pip install --upgrade "transformers>=5.10"` followed by
`pip install "transformers==4.57.6" "huggingface-hub<1" "tokenizers<0.23"` to revert; both the
embeddings pipeline (`embed_query()`) and the sentiment classifier (`score_sentiment()`) were
smoke-tested directly after the revert and confirmed still working.

Each vulnerability's exploit path requires either the `Trainer` class, loading an
attacker-chosen/arbitrary HF repo, or an attacker-controlled `chat_template` argument. This
codebase only ever loads one fixed, hardcoded, well-known model name and never runs training,
so none of these code paths are reachable through this application. Accepted as a reviewed
risk; revisit when `optimum-onnx` publishes a release compatible with a patched
`transformers`.

## Dependency scanning: npm audit (frontend)

```
info: 0, low: 0, moderate: 0, high: 0, critical: 0, total: 0
```

No findings.

## Dynamic scanning: OWASP ZAP

Not run. A ZAP baseline scan needs a running instance of the full stack (API, worker,
Postgres) reachable over HTTP and a Java runtime for the ZAP container, neither of which is
available in this development environment. This is the same kind of environment gap already
noted for Lighthouse (Phase 7) and physical microphone hardware testing (Phase 6): documented
honestly as not run here, rather than simulated. It is straightforward to run once the
production `docker-compose.yml` stack (Phase 10) is deployed, for example:

```
docker run -t zaproxy/zap-stable zap-baseline.py -t https://<deployed-host> -r zap-report.html
```

## Summary

| Scan | Result |
| --- | --- |
| bandit (backend) | 0 High, 28 Medium (all reviewed, false positive or accepted risk), 4 Low (all reviewed, false positive) |
| pip-audit (backend) | 1 package with known CVEs (`transformers`), all in unreachable code paths, accepted as reviewed risk |
| npm audit (frontend) | 0 findings |
| OWASP ZAP | Not run; infeasible in this environment, documented as a gap |
