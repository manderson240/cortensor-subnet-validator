# Cortensor Hackathon #5: OpenMinion 0.1 SDK Developer Report
## What worked, what broke, and what I would change

**Hackathon**: [Cortensor Hackathon #5 on DoraHacks (ID: 2418)](https://dorahacks.io/hackathon/2418/detail)  
**Project**: Cortensor Task Sentinel  
**SDK evaluated**: `openminion` v0.1.20 (Python 3.13, Ubuntu Linux)  
**Author**: Mike Anderson (`github.com/manderson240`), solo builder  

---

## 1. Summary

For Cortensor Hackathon #5 I built Cortensor Task Sentinel on the OpenMinion 0.1 Python SDK. It checks code that miners submit to a Cortensor subnet: a static AST safety check, a time-limited test run, and an HMAC-SHA256 signed receipt.

The hackathon asked for feedback on what worked, what broke, and what could be improved. This report covers what I ran into while building the project.

---

## 2. What worked

### A. Tool registration with `@tool`
- Decorating plain Python functions with `@tool` produced usable schemas from type hints and docstrings. My three main tools (`audit_code_safety`, `execute_test_case`, `create_attestation_receipt`) registered without any hand-written JSON schema.
- Import and startup were fast. Agent creation took well under 100 ms on my machine, which matters for a validator daemon that may restart often.

### B. Agent configuration
- `Agent(name=..., instructions=..., tools=[...], model=...)` was easy to read and set up. I could give the validator agent (`CortensorSentinel-<validator_id>`) a fixed instruction set and a fixed list of tools.

### C. Model endpoint flexibility
- Model routing is separate from tool execution, so I could point the agent at a local endpoint or a hosted provider without changing tool code.

---

## 3. What broke

### A. Dataclass return values from tools
- **Issue**: When a tool returns a `@dataclass(slots=True)` instance, a tuple, or a Pydantic model, the tool dispatcher fails during coercion instead of converting it to a dict.
- **Impact**: I had to wrap my domain objects (`SafetyCheckResult`, `AttestationReceipt`) in adapters that return `dict[str, Any]`.

### B. Desktop dependencies on headless nodes
- **Issue**: Installing `openminion==0.1.20` pulls in terminal UI and desktop packages: `prompt-toolkit`, `send2trash`, `wcwidth`, and `sophiagraph`.
- **Impact**: Validators usually run in headless containers or systemd services. Extra packages there mean a larger install and more dependencies to keep patched.

### C. No hook for a pre-model check
- **Issue**: Miners can submit malformed payloads, prompt injections, or code calling `eval`, `exec`, or raw sockets. OpenMinion passes the user turn straight to the model.
- **Impact**: If a model call is needed to catch an obvious syntax or security problem, the validator spends 1,000 to 2,000 ms and inference cost on a request that should have been rejected up front.

### D. Circular import between `modules.tool.executor` and `modules.tool.registry`
- **Issue**: Importing `openminion.modules.tool.executor` directly (for example `from openminion.modules.tool.executor import ToolExecutionBatch`) fails with:
  ```
  ImportError: cannot import name 'ToolExecutionBatch' from partially initialized module 'openminion.modules.tool.executor' (most likely due to a circular import)
  ```
  `executor.py:19` imports `from openminion.modules.tool.registry.catalog import ToolSpec` at module level. That runs `registry/__init__.py`, which at line 12 imports `ToolExecutionBatch` and six other names back from `executor.py` before `executor.py` has finished loading.
- **Impact**: Code that imports `ToolExecutionBatch` from the module that defines it cannot load.
- **Bug report**: [openminion/openminion#733](https://github.com/openminion/openminion/issues/733)
- **Fix PR**: [openminion/openminion#734](https://github.com/openminion/openminion/pull/734). It defers the `ToolSpec` import in `executor.py` and adds a regression test that imports the module in isolation. The full upstream test suite (559 tests) and type checks pass with the change.

---

## 4. Recommendations

### 1. Optional `pre_turn_verifier` hook on `Agent`
```python
agent = Agent(
    name="SubnetValidator",
    instructions="...",
    tools=[...],
    pre_turn_verifier=my_ast_safety_checker,  # runs before any model call
)
```
If the verifier returns `valid=False`, the agent would return a rejection without calling the model. In my project the AST check takes under 0.2 ms, compared with 1,000 ms or more for a model round trip.

### 2. Convert dataclasses and Pydantic models in tool returns
Let `@tool` functions return Pydantic models or `@dataclass` instances directly. The dispatcher could call `model_dump()` or `dataclasses.asdict()` automatically.

### 3. Optional signed tool receipts
Add an optional hook to sign tool execution results with HMAC-SHA256 or Ed25519, including a validator ID and epoch. That would let downstream services check which validator produced a result and when.

### 4. Split `openminion-core` from `openminion-cli`
Publish a headless `openminion-core` package with only `Agent`, `tool`, and the runtime, and keep the terminal dependencies (`prompt-toolkit`, `send2trash`) in a separate CLI package.

---

## 5. Code

- Demo command: `uv run sentinel` (one honest and one malicious submission, about 0.4 ms total on my machine)
- Agent and tools: [`src/cortensor_validator/openminion_agent.py`](../src/cortensor_validator/openminion_agent.py)
- CLI: [`src/cortensor_validator/sentinel.py`](../src/cortensor_validator/sentinel.py)
- Tests: [`tests/test_validator.py`](../tests/test_validator.py) (17 tests, all passing in under 2 seconds)
- Upstream bug report: [openminion/openminion#733](https://github.com/openminion/openminion/issues/733)
- Upstream fix PR: [openminion/openminion#734](https://github.com/openminion/openminion/pull/734)
