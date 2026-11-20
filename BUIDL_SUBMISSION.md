# DoraHacks BUIDL Submission: Cortensor Task Sentinel

**Hackathon**: [Cortensor Hackathon #5 (DoraHacks ID: 2418)](https://dorahacks.io/hackathon/2418/detail)  
**Track**: Subnet Task Verification Agent  
**Deadline**: December 18, 2026, 23:59 UTC-8  
**Repository**: https://github.com/manderson240/cortensor-subnet-validator  

This file mirrors what I entered in the DoraHacks form.

---

## Form fields

### Name
```text
Cortensor Task Sentinel
```

### Brief description (120 characters max)
```text
Autonomous Subnet Task Verification Agent built with OpenMinion 0.1 SDK and zero-token deterministic AST safety defense.
```

### Tags
```text
AI > AI Agents
```

### Team
```text
Mike Anderson (Solo builder, github.com/manderson240)
```

### Links
- GitHub: https://github.com/manderson240/cortensor-subnet-validator
- Demo video: https://github.com/manderson240/cortensor-subnet-validator/raw/main/docs/cortensor_pitch_demo.mp4
- SDK feedback report: https://github.com/manderson240/cortensor-subnet-validator/blob/main/docs/cortensor_openminion_feedback_report.md
- Logo (1024x1024 PNG): `docs/cortensor_task_sentinel_logo.png`

### Contact
- Telegram: `manderson240`
- Discord: `miked238725`

---

## Description

# Cortensor Task Sentinel

### Why I built this
In Cortensor subnets, miners submit code and task outputs that validators have to check before recording results. Sending raw miner code straight to an LLM is slow, costs tokens on submissions that are obviously broken, and exposes the validator node to unsafe calls (`eval`, `exec`, `os.system`, `subprocess`, sockets) or infinite loops.

### How it works
I built Cortensor Task Sentinel with the OpenMinion 0.1 Python SDK (`openminion.Agent` and `@tool`). It runs fast, deterministic checks before or alongside any model call:

1. `audit_code_safety`: walks the Python AST in under 0.2 ms with no LLM tokens and blocks forbidden modules (`os`, `sys`, `subprocess`, `socket`), dangerous builtins (`eval`, `exec`, `open`, `__import__`, `getattr`), and dunder sandbox escapes (`__class__`, `__subclasses__`, `__globals__`).
2. `execute_test_case`: runs code that passed the audit against test inputs in a restricted builtins namespace with a `signal.setitimer` timeout.
3. `verify_via_hosted_portal`: uses the hosted Cortensor API when `CORTENSOR_API_KEY` is set and falls back to local verification otherwise.
4. `create_attestation_receipt`: signs each outcome with an epoch-fenced HMAC-SHA256 signature and can print it as JSON (`--json`).

### OpenMinion 0.1 SDK building blocks I tested
- `@tool` registration from type hints and docstrings (worked well): no hand-written JSON schemas, and agent startup stayed under 100 ms.
- `Agent` configuration and custom endpoints (worked well): instructions, tools, and local or hosted model endpoints were simple to wire up.
- Tool return serialization (rough edge): returning `@dataclass(slots=True)` objects (`SafetyCheckResult`, `AttestationReceipt`) from `@tool` functions failed coercion, so I added `dict[str, Any]` adapters.
- Headless dependencies (rough edge): `openminion==0.1.20` installs terminal and desktop packages (`prompt-toolkit`, `send2trash`, `wcwidth`, `sophiagraph`) on headless Linux nodes.
- Circular import in `openminion.modules.tool.executor` (bug I found and fixed upstream): importing `ToolExecutionBatch` from `openminion.modules.tool.executor` failed with an `ImportError` because of a module-level circular import with `openminion.modules.tool.registry`.

### SDK feedback and recommendations
Full report: `docs/cortensor_openminion_feedback_report.md`

- Add an optional `pre_turn_verifier` hook on `Agent` so a deterministic check can reject bad input before any model call.
- Convert `@dataclass` (`asdict()`) and Pydantic (`model_dump()`) return values automatically in the `@tool` dispatcher.
- Offer optional HMAC-SHA256 or Ed25519 signing hooks for tool execution receipts.
- Split `openminion-core` (headless agent and tool runtime) from `openminion-cli` (terminal dependencies).

### Upstream OpenMinion contributions
- Bug report: [openminion/openminion#733](https://github.com/openminion/openminion/issues/733), a circular import between `openminion.modules.tool.executor` and `modules.tool.registry`.
- Fix PR: [openminion/openminion#734](https://github.com/openminion/openminion/pull/734), which defers the `ToolSpec` import in `executor.py` and adds an isolated-import regression test. All 559 upstream tests and type checks pass.

### Verification
- The AST safety check runs in under 0.2 ms with no LLM tokens. The full CLI demo cycle takes about 0.4 ms on my machine.
- 17 of 17 unit tests pass in under 2 seconds (`tests/test_validator.py`). They cover clean code, blocked imports and builtins, `getattr` evasion, dunder attribute escapes, timeout enforcement, HMAC tamper detection, `--json` CLI receipts, and hosted portal fallback.

```bash
git clone https://github.com/manderson240/cortensor-subnet-validator.git
cd cortensor-subnet-validator
uv run pytest
uv run sentinel
```

---

## Architecture diagrams

See [README.md](README.md#architecture) for the flowchart, sequence diagram, and state diagram.
