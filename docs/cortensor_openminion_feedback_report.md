# Cortensor Hackathon #5: OpenMinion 0.1 SDK Developer Report
## What Worked, What Broke, and What Can Be Improved

**Hackathon**: [Cortensor Hackathon #5 on DoraHacks (ID: 2418)](https://dorahacks.io/hackathon/2418/detail)  
**Project**: Cortensor Task Sentinel (Subnet Validator)  
**SDK Evaluated**: `openminion` v0.1.20 (Python 3.13 / Ubuntu Linux)  
**Author / Team**: Mike Anderson (`github.com/manderson240`)  

---

## 1. Executive Summary

As part of our submission to **Cortensor Hackathon #5 (DoraHacks #2418)**, we built the **Cortensor Task Sentinel** using the **OpenMinion 0.1 Python SDK** to validate computational tasks submitted by miners across Cortensor subnets. Our validator architecture implements deterministic zero-token AST code safety checking, sandboxed test case execution, and sub-millisecond HMAC-SHA256 attestation receipts.

Per the official hackathon guidelines, this report provides transparent, production-tested feedback on **what worked**, **what broke**, and **actionable improvements** to assist the Cortensor team in refining OpenMinion prior to broader mainnet rollouts.

---

## 2. What Worked (Strengths & Production Wins)

### A. Minimal Tool Registration Friction with `@tool`
- **Docstring Schema Parsing**: Wrapping native Python functions with the `@tool` decorator seamlessly exported typed schemas. Our safety check tool `audit_code_safety`, test runner `execute_test_case`, and attestation generator `create_attestation_receipt` integrated without requiring verbose JSON-schema boilerplate.
- **Fast Startup & Import Overhead**: Unlike heavy enterprise frameworks (LangChain, AutoGen, CrewAI) that load hundreds of unused modules, OpenMinion 0.1 initializes in $<100\,\text{ms}$, making it viable for rapid daemon restarts and cold-boot recovery on edge silicon.

### B. Declarative Agent Scoping
- The `Agent(name=..., instructions=..., tools=[...], model=...)` interface provided clear role encapsulation. We were able to configure dedicated validator personas (`CortensorTaskSentinel-01`) with explicit instruction fences and tool access boundaries.

### C. Clean Model Provider & Runtime Extensibility
- The SDK cleanly separates model routing from execution logic, allowing us to point OpenMinion agents directly to custom endpoints (local Ollama or cloud providers) without vendor lock-in.

---

## 3. What Broke (Edge Cases & Bottlenecks Discovered)

### A. Non-JSON Dataclass Serialization in Tool Return Values
- **The Issue**: When tools return complex domain objects (e.g. standard Python `@dataclass(slots=True)`, tuples, or Pydantic models), OpenMinion's internal tool dispatcher fails with serialization/coercion errors rather than gracefully converting them to standard dictionaries.
- **Impact**: We had to write explicit wrapper adapters converting dataclasses (`SafetyCheckResult`, `AttestationReceipt`) into primitive `dict[str, Any]` before returning from tool functions.

### B. Dependency Bloat in Headless Validator Environments
- **The Issue**: Installing `openminion==0.1.20` pulls in interactive terminal UI and desktop packages: `prompt-toolkit`, `send2trash`, `wcwidth`, and `sophiagraph`.
- **Impact**: In headless Linux containers, daemonized systemd services, and edge environments where minimal attack surfaces and dependency footprints are critical, desktop and terminal styling libraries create unnecessary package surface and potential CVE exposure.

### C. Absence of a Zero-Token Pre-Execution Verifier Hook
- **The Issue**: In a decentralized subnet, miners frequently submit malformed payloads, prompt injections, or malicious code primitives (`eval`, `exec`, arbitrary network sockets). Currently, OpenMinion passes the raw user turn directly to the LLM.
- **Impact**: If an LLM call is required to detect an obvious syntax or security violation, the validator burns 1,000–2,000ms and inference compute on a doomed request.

### D. Circular Import between `modules.tool.executor` and `modules.tool.registry` (Bonus Bug Report & Fix PR)
- **The Issue**: Direct import of `openminion.modules.tool.executor` (e.g. `from openminion.modules.tool.executor import ToolExecutionBatch`, `execute_calls`, or standalone tool execution harnesses) crashes with:
  ```
  ImportError: cannot import name 'ToolExecutionBatch' from partially initialized module 'openminion.modules.tool.executor' (most likely due to a circular import)
  ```
  `executor.py:19` imports `from openminion.modules.tool.registry.catalog import ToolSpec` at top level. This executes `registry/__init__.py`, which at line 12 imports `ToolExecutionBatch` (and six other symbols) from `executor.py` before `executor.py` has finished loading.
- **Impact**: Prevents downstream tooling, test harnesses, and modular validator nodes from importing `ToolExecutionBatch` from its canonical defining module.
- **Official Bug Report**: [OpenMinion Issue #733](https://github.com/openminion/openminion/issues/733)
- **Substantive Fix PR**: [OpenMinion PR #734](https://github.com/openminion/openminion/pull/734) (defers `ToolSpec` resolution in `executor.py` and provides a dedicated isolated-import regression test).

---

## 4. What Can Be Improved (Actionable Recommendations for Cortensor)

### Recommendation 1: Native `pre_turn_verifier` Hook (Deterministic AST Gate)
Introduce an optional deterministic verification gate on the `Agent` definition:
```python
agent = Agent(
    name="SubnetValidator",
    instructions="...",
    tools=[...],
    pre_turn_verifier=my_ast_safety_checker,  # Evaluates before LLM call
)
```
If `pre_turn_verifier` returns `valid=False`, OpenMinion should immediately return a fail-closed rejection without making an LLM API call, saving 100% of compute and cutting latency from 1,500ms to $<0.15\,\text{ms}$.

### Recommendation 2: Pydantic & Dataclass Native Serialization in Tool Returns
Allow tools decorated with `@tool` to return Pydantic models or standard `@dataclass` instances without manual dict conversion. The OpenMinion dispatcher should automatically call `model_dump()` or `asdict()`.

### Recommendation 3: Cryptographic Attestation Receipts
Add built-in support for signing tool execution receipts with an epoch-fenced HMAC-SHA256 or Ed25519 signature. Every tool output should be verifiable as having been executed by an authorized validator ID within a specific block epoch window.

### Recommendation 4: Split into `openminion-core` and `openminion-cli`
Publish a lightweight, headless `openminion-core` package containing only the `Agent`, `tool`, and `Runtime` primitives without terminal or filesystem trash dependencies (`prompt-toolkit`, `send2trash`), reserving the full `openminion` package for interactive developer CLIs.

---

## 5. Verification & Code Artifacts

The working OpenMinion 0.1 implementation is fully verified in our open-source repository:
- **1-Command Entrypoint**: `uv run sentinel` (completes in <20ms, verifying valid and malicious miner code tasks).
- **Validator Agent**: [`src/cortensor_validator/openminion_agent.py`](../src/cortensor_validator/openminion_agent.py)
- **Sentinel Runner**: [`src/cortensor_validator/sentinel.py`](../src/cortensor_validator/sentinel.py)
- **Unit Test Suite**: [`tests/test_validator.py`](../tests/test_validator.py) (11/11 tests passing in <1.5s)
- **Hackathon Bonus Bug Report**: [OpenMinion Issue #733](https://github.com/openminion/openminion/issues/733)
- **Hackathon Bonus Fix PR**: [OpenMinion PR #734](https://github.com/openminion/openminion/pull/734)
