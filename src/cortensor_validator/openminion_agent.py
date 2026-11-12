"""OpenMinion 0.1 SDK Integration for Cortensor Subnet Verification.
==================================================================
Implements a simple, reliable Subnet Task Verification Agent using the official
OpenMinion 0.1 SDK (`openminion.Agent` and `openminion.tool`).
"""

from __future__ import annotations

import json
import os
import signal
import time
import urllib.error
import urllib.request
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


class ExecutionTimeoutError(Exception):
    """Raised when miner code execution exceeds the allocated CPU budget."""


def _timeout_handler(signum: int, frame: Any) -> None:
    raise ExecutionTimeoutError("Execution timed out (CPU budget exceeded).")


@tool
def execute_test_case(
    code: str,
    test_input: int,
    expected_output: int,
    timeout_seconds: float = 1.0,
) -> dict[str, Any]:
    """Execute a safe pure function against an input-output test case with timeout defense.

    Parameters
    ----------
    code : str
        Verified Python code defining a function named 'solution'.
    test_input : int
        Input integer to test.
    expected_output : int
        Expected output integer.
    timeout_seconds : float, optional
        Maximum CPU execution time allowed in seconds (default: 1.0).

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

    # Set up signal-based alarm if available in current thread
    has_alarm = hasattr(signal, "SIGALRM")
    prev_handler = None
    if has_alarm:
        try:
            prev_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
        except ValueError:
            has_alarm = False

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
    finally:
        if has_alarm and prev_handler is not None:
            try:
                signal.setitimer(signal.ITIMER_REAL, 0.0)
                signal.signal(signal.SIGALRM, prev_handler)
            except ValueError:
                pass


@tool
def create_attestation_receipt(
    task_id: str,
    passed: bool,
    validator_id: str | None = None,
) -> dict[str, Any]:
    """Generate an HMAC-SHA256 cryptographic attestation receipt for a task outcome.

    Parameters
    ----------
    task_id : str
        Subnet task identifier.
    passed : bool
        Whether the task verification passed.
    validator_id : str, optional
        Validator node identifier (defaults to CORTENSOR_VALIDATOR_ID env var).

    Returns
    -------
    dict[str, Any]
        Signed attestation receipt data.
    """
    effective_id = validator_id or os.getenv("CORTENSOR_VALIDATOR_ID", "val-cortensor-01")
    signer = AttestationSigner(validator_id=effective_id)
    receipt = signer.sign(task_id=task_id, passed=passed)
    return {
        "task_id": receipt.task_id,
        "validator_id": receipt.validator_id,
        "epoch": receipt.epoch,
        "passed": receipt.passed,
        "signature": receipt.signature,
        "timestamp_ns": receipt.timestamp_ns,
    }


def query_hosted_portal(
    code: str,
    test_input: int,
    expected_output: int,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 3.0,
) -> dict[str, Any]:
    """Query the hosted Cortensor Subnet verification API if credentials are provided.

    Falls back cleanly to local verification if offline, unauthenticated, or unreachable.
    """
    key = api_key or os.getenv("CORTENSOR_API_KEY")
    if not key:
        return {"mode": "local", "connected": False, "reason": "No CORTENSOR_API_KEY provided"}

    endpoint = (base_url or os.getenv("CORTENSOR_BASE_URL", "https://api.cortensor.network/v1")).rstrip("/") + "/verify"
    payload = json.dumps({
        "code": code,
        "input": test_input,
        "expected": expected_output,
    }).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "CortensorSentinel-OpenMinion/0.1",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            if response.status == 200:
                body = json.loads(response.read().decode("utf-8"))
                return {"mode": "hosted", "connected": True, "data": body}
            return {"mode": "fallback_local", "connected": False, "status_code": response.status}
    except Exception as exc:
        return {"mode": "fallback_local", "connected": False, "error": str(exc)}


@tool
def verify_via_hosted_portal(
    code: str,
    test_input: int,
    expected_output: int,
) -> dict[str, Any]:
    """Verify miner code using the Cortensor Hosted Portal API with automatic local fallback.

    Parameters
    ----------
    code : str
        Source code to verify.
    test_input : int
        Test input integer.
    expected_output : int
        Expected output integer.

    Returns
    -------
    dict[str, Any]
        Verification outcome from hosted portal or local fallback.
    """
    res = query_hosted_portal(code, test_input, expected_output)
    if res.get("connected"):
        return res
    # Fallback to local execution
    local_test = execute_test_case(code, test_input, expected_output)
    return {"mode": "fallback_local", "result": local_test}


# ---------------------------------------------------------------------------
# Cortensor Sentinel Facade
# ---------------------------------------------------------------------------


class CortensorSentinel:
    """Manages OpenMinion-powered task verification for Cortensor Subnet nodes."""

    def __init__(
        self,
        validator_id: str | None = None,
        epoch: int | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.validator_id = validator_id or os.getenv("CORTENSOR_VALIDATOR_ID", "val-cortensor-01")
        self.epoch = epoch if epoch is not None else int(os.getenv("CORTENSOR_EPOCH", "1"))
        self.signer = AttestationSigner(validator_id=self.validator_id, current_epoch=self.epoch)
        self.api_key = api_key or os.getenv("CORTENSOR_API_KEY")
        self.base_url = base_url or os.getenv("CORTENSOR_BASE_URL", "https://api.cortensor.network/v1")
        self.last_mode: str = "local"

    def create_agent(self, model: str | None = None) -> Agent:
        """Create an official OpenMinion Agent equipped with verification tools."""
        instructions = (
            "You are a Cortensor Subnet Task Verification Agent built with OpenMinion 0.1. "
            "Use audit_code_safety to inspect code proposals for dangerous primitives. "
            "Use execute_test_case to test verified logic against expected outputs. "
            "Use verify_via_hosted_portal to verify tasks via Cortensor hosted portal. "
            "Use create_attestation_receipt to produce cryptographic verification receipts."
        )
        return Agent(
            name=f"CortensorSentinel-{self.validator_id}",
            instructions=instructions,
            model=model,
            tools=[
                audit_code_safety,
                execute_test_case,
                verify_via_hosted_portal,
                create_attestation_receipt,
            ],
        )

    def verify_submission(
        self,
        task_id: str,
        code: str,
        test_input: int,
        expected_output: int,
        use_hosted: bool = False,
    ) -> tuple[bool, AttestationReceipt]:
        """Perform a complete, deterministic verification cycle on a miner submission."""
        # 1. Audit code safety locally first (defense-in-depth)
        safety = verify_code_safety(code)
        if not safety.valid:
            self.last_mode = "local_rejected"
            receipt = self.signer.sign(task_id=task_id, passed=False)
            return False, receipt

        # 2. Check hosted portal if requested or API key present
        if use_hosted or self.api_key:
            portal_res = query_hosted_portal(
                code=code,
                test_input=test_input,
                expected_output=expected_output,
                api_key=self.api_key,
                base_url=self.base_url,
            )
            if portal_res.get("connected"):
                self.last_mode = "hosted"
                passed = bool(portal_res.get("data", {}).get("passed", False))
                receipt = self.signer.sign(task_id=task_id, passed=passed)
                return passed, receipt
            self.last_mode = "fallback_local"
        else:
            self.last_mode = "local"

        # 3. Test correctness locally
        test_res = execute_test_case(code, test_input, expected_output)
        passed = bool(test_res.get("passed", False))

        # 4. Sign attestation
        receipt = self.signer.sign(task_id=task_id, passed=passed)
        return passed, receipt
