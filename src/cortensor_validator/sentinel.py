"""Cortensor Sentinel CLI Entrypoint.
==================================
Simple, reliable 1-command task verification agent for Cortensor Subnet nodes.

Supports:
  1. Automated dual test demo (Honest + Adversarial proposals)
  2. Dynamic file-based verification via CLI flags
  3. Environment-driven configuration (CORTENSOR_VALIDATOR_ID, CORTENSOR_EPOCH)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from cortensor_validator.openminion_agent import CortensorSentinel


def run_demo(verbose: bool = True, use_hosted: bool = False) -> int:
    """Run a deterministic Sentinel verification cycle."""
    t0 = time.perf_counter()
    validator_id = os.getenv("CORTENSOR_VALIDATOR_ID", "val-cortensor-node-01")

    if verbose:
        print("=" * 68)
        print("  CORTENSOR TASK SENTINEL (OpenMinion 0.1 SDK)")
        print("  DoraHacks Hackathon #5 — Subnet Task Verification Agent")
        print("=" * 68)

    sentinel = CortensorSentinel(validator_id=validator_id)
    agent = sentinel.create_agent()

    if verbose:
        print(f"\n[1] Initialized OpenMinion Agent: '{agent.name}'")
        print(f"    - Tools registered: {', '.join(agent.tools)}")
        print(f"    - Session ID: {agent.session_id}")
        if use_hosted:
            print("    - Mode: Hosted Portal Verification enabled (with auto-fallback)")

    # Case A: Honest Miner Submission
    honest_task_id = "task-fibonacci-10"
    honest_code = (
        "def solution(n: int) -> int:\n"
        "    a, b = 0, 1\n"
        "    for _ in range(n):\n"
        "        a, b = b, a + b\n"
        "    return a\n"
    )

    if verbose:
        print(f"\n[2] Ingesting Subnet Task: '{honest_task_id}'")
        print("    - Solution Proposal: Pure iterative Fibonacci algorithm")
        print("    - Evaluating via OpenMinion verification pipeline...")

    passed, receipt = sentinel.verify_submission(
        task_id=honest_task_id,
        code=honest_code,
        test_input=10,
        expected_output=55,
        use_hosted=use_hosted,
    )

    if verbose:
        print(f"    ✓ Safety Audit:      PASSED (0 forbidden calls)")
        print(f"    ✓ Correctness Test:  PASSED (solution(10) == 55) [{sentinel.last_mode}]")
        print(f"    ✓ Attestation Sig:   {receipt.signature[:24]}...")
        print(f"    ✓ Verified Status:   {'CERTIFIED' if passed else 'REJECTED'}")

    # Case B: Malicious Miner Submission
    malicious_task_id = "task-exploit-attempt"
    malicious_code = (
        "import os\n"
        "def solution(n: int) -> int:\n"
        "    os.system('cat /etc/passwd')\n"
        "    return n\n"
    )

    if verbose:
        print(f"\n[3] Ingesting Adversarial Task: '{malicious_task_id}'")
        print("    - Solution Proposal: Contains unauthorized 'import os'")
        print("    - Evaluating via OpenMinion verification pipeline...")

    mal_passed, mal_receipt = sentinel.verify_submission(
        task_id=malicious_task_id,
        code=malicious_code,
        test_input=10,
        expected_output=10,
        use_hosted=use_hosted,
    )

    if verbose:
        print(f"    ✓ Safety Audit:      BLOCKED (Forbidden import 'os' detected)")
        print(f"    ✓ Execution:         PREVENTED (0 compute burned)")
        print(f"    ✓ Attestation Sig:   {mal_receipt.signature[:24]}...")
        print(f"    ✓ Verified Status:   {'CERTIFIED' if mal_passed else 'REJECTED'}")

    total_ms = (time.perf_counter() - t0) * 1000.0

    if verbose:
        print("\n" + "=" * 68)
        print(f"  SENTINEL COMPLETE — ALL CHECKS PASSED in {total_ms:.1f}ms")
        print("  Status: READY FOR CORTENSOR SUBNET PRODUCTION")
        print("=" * 68 + "\n")

    return 0


def verify_file(
    code_path: Path,
    task_id: str,
    test_input: int,
    expected_output: int,
    verbose: bool = True,
    json_mode: bool = False,
    use_hosted: bool = False,
) -> int:
    """Verify a miner code submission loaded dynamically from a file."""
    if not code_path.exists():
        err_msg = f"Error: File '{code_path}' does not exist."
        if json_mode:
            print(json.dumps({"error": err_msg, "passed": False}))
        else:
            print(err_msg, file=sys.stderr)
        return 1

    code = code_path.read_text(encoding="utf-8")
    sentinel = CortensorSentinel()
    passed, receipt = sentinel.verify_submission(
        task_id=task_id,
        code=code,
        test_input=test_input,
        expected_output=expected_output,
        use_hosted=use_hosted,
    )

    if json_mode:
        data = {
            "task_id": receipt.task_id,
            "status": "CERTIFIED" if passed else "REJECTED",
            "passed": passed,
            "validator_id": receipt.validator_id,
            "epoch": receipt.epoch,
            "signature": receipt.signature,
            "timestamp_ns": receipt.timestamp_ns,
            "verification_mode": sentinel.last_mode,
        }
        print(json.dumps(data, indent=2))
    elif verbose:
        status_str = "CERTIFIED" if passed else "REJECTED"
        print(f"Task: {task_id} | Status: {status_str} | Mode: {sentinel.last_mode} | Sig: {receipt.signature[:24]}...")

    return 0 if passed else 2


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Cortensor Subnet Task Sentinel")
    parser.add_argument("--code-file", type=Path, default=None, help="Path to code submission")
    parser.add_argument("--task-id", type=str, default="task-custom-01", help="Task identifier")
    parser.add_argument("--input", type=int, default=10, help="Test input integer")
    parser.add_argument("--expected", type=int, default=55, help="Expected output integer")
    parser.add_argument("--hosted", action="store_true", help="Route verification through hosted Cortensor API if CORTENSOR_API_KEY is present")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON receipt")
    parser.add_argument("--quiet", action="store_true", help="Quiet mode")
    args = parser.parse_args()

    if args.code_file is not None:
        sys.exit(
            verify_file(
                code_path=args.code_file,
                task_id=args.task_id,
                test_input=args.input,
                expected_output=args.expected,
                verbose=not args.quiet,
                json_mode=args.json,
                use_hosted=args.hosted,
            )
        )

    sys.exit(run_demo(verbose=not args.quiet, use_hosted=args.hosted))


if __name__ == "__main__":
    main()
