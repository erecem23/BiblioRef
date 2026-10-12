"""Version metadata for the BiblioRef v0.9.10-rc2 integration candidate.

Algorithm 0.6.11 keeps the whole 0.6.8 structural stack. On top of the four
0.6.10 conditions it fixes the three rules that opened a record without looking
at the start margin, the one that refused a legitimate start because the
surname begins with a lowercase particle, and the licence the hanging-indent
repair needs before it can remove a boundary. Everything is declared in
``EXTRACTION_CORE_NONREGRESSION_V0611_SHA256.json``. Historical 0.6.7
structural identifiers remain unchanged.

The validated historical base remains v0.6.1. The adaptive v0.8.10
stable-conflict layer remains diagnostic-only and never mutates effective
records or zones.
"""

SOFTWARE_VERSION = "0.9.10-rc2"
BASE_VERSION = "0.6.1"
ALGORITHM_VERSION = "0.6.21"
ADAPTIVE_ANALYSIS_VERSION = "0.8.10-shadow23"
STABLE_ENGINE_VERSION = "0.4.5"
AUDIT_APP_VERSION = "0.9.3-audit"

TWO_PASS_ANALYSIS_VERSION = "0.9.0-two-pass-shadow1"

RESCUE_ROUTER_VERSION = "0.9.4-selective-router3-plausibility"
