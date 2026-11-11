"""OpenMinion 0.1 SDK Integration for Cortensor Subnet Verification.
==================================================================
Implements a simple, reliable Subnet Task Verification Agent using the official
OpenMinion 0.1 SDK (`openminion.Agent` and `openminion.tool`).
"""

from __future__ import annotations

import time
from typing import Any

from openminion import Agent, tool

from cortensor_validator.attestation import AttestationReceipt, AttestationSigner
from cortensor_validator.verifier import verify_code_safety


# ---------------------------------------------------------------------------
# OpenMinion Tools
# ---------------------------------------------------------------------------


@tool
def audit_code_safety(code: str) -> dict[str, Any]:
    """Inspect Python code for unsafe primitives and syntax errors before execution.

    Parameters
    ----------
    code : str
        Source code submitted by a subnet miner.

    Returns
    -------
    dict[str, Any]
        Audit outcome including valid flag, violations list, and latency.
    """
    res = verify_code_safety(code)
    return {
        "valid": res.valid,
        "violations": list(res.violations),
        "nodes_scanned": res.ast_nodes_scanned,
        "latency_ms": res.latency_ms,
    }


SAFE_BUILTINS = {
    "range": range,
    "len": len,
    "min": min,
    "max": max,
    "abs": abs,
    "sum": sum,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "enumerate": enumerate,
    "zip": zip,
}


@tool
def execute_test_case(code: str, test_input: int, expected_output: int) -> dict[str, Any]:
    """Execute a safe pure function against an input-output test case.

    Parameters
    ----------
    code : str
        Verified Python code defining a function named 'solution'.
    test_input : int
        Input integer to test.
    expected_output : int
        Expected output integer.

    Returns
    -------
    dict[str, Any]
        Test outcome including pass flag, actual output, and latency.
    """
    safety = verify_code_safety(code)
    if not safety.valid:
        return {
            "passed": False,
            "error": "Safety check failed; execution blocked.",
            "violations": list(safety.violations),
        }

    t0 = time.perf_counter()
    namespace: dict[str, Any] = {}
    try:
        exec(code, {"__builtins__": SAFE_BUILTINS}, namespace)  # noqa: S102
        fn = namespace.get("solution")
        if not callable(fn):
            return {"passed": False, "error": "No callable 'solution' defined in code."}
        actual = fn(test_input)
        passed = (actual == expected_output)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "passed": passed,
            "actual_output": actual,
            "expected_output": expected_output,
            "latency_ms": dt_ms,
        }
    except Exception as exc:
        dt_ms = (time.perf_counter() - t0) * 1000.0
        return {"passed": False, "error": str(exc), "latency_ms": dt_ms}


@tool
def create_attestation_receipt(
    task_id: str,
    passed: bool,
    validator_id: str = "val-cortensor-01",
) -> dict[str, Any]:
    """Generate an HMAC-SHA256 cryptographic attestation receipt for a task outcome.

    Parameters
    ----------
    task_id : str
        Subnet task identifier.
    passed : bool
        Whether the task verification passed.
    validator_id : str
        Validator node identifier.

    Returns
    -------
    dict[str, Any]
        Signed attestation receipt data.
    """
    signer = AttestationSigner(validator_id=validator_id)
    receipt = signer.sign(task_id=task_id, passed=passed)
    return {
        "task_id": receipt.task_id,
        "validator_id": receipt.validator_id,
        "epoch": receipt.epoch,
        "passed": receipt.passed,
        "signature": receipt.signature,
        "timestamp_ns": receipt.timestamp_ns,
    }


# ---------------------------------------------------------------------------
# Cortensor Sentinel Facade
# ---------------------------------------------------------------------------


class CortensorSentinel:
    """Manages OpenMinion-powered task verification for Cortensor Subnet nodes."""

    def __init__(self, validator_id: str = "val-cortensor-01", epoch: int = 1) -> None:
        self.validator_id = validator_id
        self.epoch = epoch
        self.signer = AttestationSigner(validator_id=validator_id, current_epoch=epoch)

    def create_agent(self, model: str | None = None) -> Agent:
        """Create an official OpenMinion Agent equipped with verification tools."""
        instructions = (
            "You are a Cortensor Subnet Task Verification Agent built with OpenMinion 0.1. "
            "Use audit_code_safety to inspect code proposals for dangerous primitives. "
            "Use execute_test_case to test verified logic against expected outputs. "
            "Use create_attestation_receipt to produce cryptographic verification receipts."
        )
        return Agent(
            name=f"CortensorSentinel-{self.validator_id}",
            instructions=instructions,
            model=model,
            tools=[audit_code_safety, execute_test_case, create_attestation_receipt],
        )

    def verify_submission(
        self,
        task_id: str,
        code: str,
        test_input: int,
        expected_output: int,
    ) -> tuple[bool, AttestationReceipt]:
        """Perform a complete, deterministic verification cycle on a miner submission."""
        # 1. Audit code safety
        safety = verify_code_safety(code)
        if not safety.valid:
            receipt = self.signer.sign(task_id=task_id, passed=False)
            return False, receipt

        # 2. Test correctness
        test_res = execute_test_case(code, test_input, expected_output)
        passed = bool(test_res.get("passed", False))

        # 3. Sign attestation
        receipt = self.signer.sign(task_id=task_id, passed=passed)
        return passed, receipt
