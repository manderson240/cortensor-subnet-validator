# Cortensor Task Sentinel

**A simple, reliable Subnet Task Verification Agent built with OpenMinion 0.1 SDK**  
Submission for **[Cortensor Hackathon #5 on DoraHacks (ID: 2418)](https://dorahacks.io/hackathon/2418/detail)**.

---

## ⚡ Quickstart (1 Command)

Run the deterministic Sentinel task verification demo in $<20\,\text{ms}$:

```bash
# 1. Clone repository
git clone https://github.com/manderson240/cortensor-subnet-validator.git
cd cortensor-subnet-validator

# 2. Sync dependencies
uv sync

# 3. Run the Sentinel agent demo
uv run sentinel

# 4. Or verify a custom code proposal file dynamically
uv run sentinel --code-file path/to/proposal.py --task-id task-custom-01 --input 10 --expected 55
```

### Verified Output
```text
====================================================================
  CORTENSOR TASK SENTINEL (OpenMinion 0.1 SDK)
  DoraHacks Hackathon #5 — Subnet Task Verification Agent
====================================================================

[1] Initialized OpenMinion Agent: 'CortensorSentinel-val-cortensor-node-01'
    - Tools registered: audit_code_safety, execute_test_case, create_attestation_receipt
    - Session ID: 41fd70b9231f41e5b854d9c79e6dc343

[2] Ingesting Subnet Task: 'task-fibonacci-10'
    - Solution Proposal: Pure iterative Fibonacci algorithm
    - Evaluating via OpenMinion verification pipeline...
    ✓ Safety Audit:      PASSED (0 forbidden calls)
    ✓ Correctness Test:  PASSED (solution(10) == 55)
    ✓ Attestation Sig:   d0f41ab9f1c7d2e4...
    ✓ Verified Status:   CERTIFIED

[3] Ingesting Adversarial Task: 'task-exploit-attempt'
    - Solution Proposal: Contains unauthorized 'import os'
    - Evaluating via OpenMinion verification pipeline...
    ✓ Safety Audit:      BLOCKED (Forbidden import 'os' detected)
    ✓ Execution:         PREVENTED (0 compute burned)
    ✓ Attestation Sig:   83e1c6b1a9f029a1...
    ✓ Verified Status:   REJECTED

====================================================================
  SENTINEL COMPLETE — ALL CHECKS PASSED in 14.2ms
  Status: READY FOR CORTENSOR SUBNET PRODUCTION
====================================================================
```

---

## 🎯 What It Does

In decentralized AI subnets (e.g. Cortensor), miners submit compute proposals and code outputs that validators must score. Passing raw submissions directly to large language models burns expensive tokens and exposes validator nodes to prompt injection and malicious execution primitives (`eval`, `exec`, arbitrary shell calls).

**Cortensor Task Sentinel** provides a lightweight, deterministic agent verification pipeline using the official OpenMinion 0.1 SDK:
1. **`audit_code_safety`**: Statically inspects submitted code using Python AST to detect unsafe modules (`os`, `subprocess`, `socket`) and dangerous builtins (`eval`, `exec`, `open`) in $<0.2\,\text{ms}$ with **0 LLM tokens**.
2. **`execute_test_case`**: Evaluates verified pure logic against unit test cases in a bounded namespace.
3. **`create_attestation_receipt`**: Signs an HMAC-SHA256 cryptographic attestation receipt linking the task ID, validator ID, timestamp, and verification outcome.

---

## ⚙️ Dynamic Configuration

All node parameters are configurable via standard environment variables:

| Variable | Description | Default |
|---|---|---|
| `CORTENSOR_VALIDATOR_ID` | Validator node identifier | `val-cortensor-01` |
| `CORTENSOR_EPOCH` | Current consensus epoch | `1` |
| `CORTENSOR_SECRET_KEY` | HMAC signing secret key | `cortensor_subnet_secret_key_2026` |

---

## 🧪 Testing

```bash
uv run pytest
```
All 11 unit tests pass in $<1.5$ seconds with zero network or paid API requirements:
- AST code safety (clean code pass, forbidden import block, forbidden builtin block, syntax errors)
- Cryptographic attestation signing and tamper detection
- OpenMinion `@tool` registration and Agent execution
- Dynamic environment variable configuration overrides
- Dynamic file verification via CLI

---

## 🏆 Hackathon Deliverables

- **Automated 1440p QHD Pitch Video**: [`docs/cortensor_pitch_demo.mp4`](docs/cortensor_pitch_demo.mp4) (Full 165s demonstration with complete, unclipped source code generated headlessly via `python3 scripts/generate_pitch_video.py`)
- **OpenMinion Feedback Report (25% Rubric)**: [`docs/cortensor_openminion_feedback_report.md`](docs/cortensor_openminion_feedback_report.md)
- **Bonus Bug Report**: [OpenMinion Issue #733](https://github.com/openminion/openminion/issues/733) — *Direct import of openminion.modules.tool.executor fails with circular import on ToolExecutionBatch*
- **Bonus Fix PR**: [OpenMinion Pull Request #734](https://github.com/openminion/openminion/pull/734) — *fix(tool): defer ToolSpec resolution in executor to break circular import*
