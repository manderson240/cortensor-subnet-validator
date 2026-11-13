"""Unit tests for Cortensor Sentinel Task Validator."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from cortensor_validator.attestation import AttestationSigner
from cortensor_validator.openminion_agent import (
    CortensorSentinel,
    audit_code_safety,
    create_attestation_receipt,
    execute_test_case,
)
from cortensor_validator.sentinel import verify_file
from cortensor_validator.verifier import verify_code_safety


def test_code_safety_accepts_clean_code() -> None:
    code = "def solution(x: int) -> int:\n    return x * 2\n"
    res = verify_code_safety(code)
    assert res.valid is True
    assert len(res.violations) == 0
    assert res.ast_nodes_scanned > 0


def test_code_safety_rejects_forbidden_imports() -> None:
    code = "import os\ndef solution(x: int) -> int:\n    return x\n"
    res = verify_code_safety(code)
    assert res.valid is False
    assert any("Forbidden import: 'os'" in v for v in res.violations)


def test_code_safety_rejects_forbidden_builtins() -> None:
    code = "def solution(x: str) -> None:\n    eval(x)\n"
    res = verify_code_safety(code)
    assert res.valid is False
    assert any("Forbidden builtin call: 'eval()'" in v for v in res.violations)


def test_code_safety_rejects_obfuscated_dynamic_imports() -> None:
    code = "def solution(x: str) -> None:\n    getattr(__builtins__, 'eval')(x)\n"
    res = verify_code_safety(code)
    assert res.valid is False
    assert any("Forbidden builtin call: 'getattr()'" in v or "Forbidden variable access: '__builtins__'" in v for v in res.violations)


def test_code_safety_rejects_sandbox_breakout_attributes() -> None:
    code = "def solution(x: int) -> int:\n    classes = ().__class__.__bases__[0].__subclasses__()\n    return len(classes)\n"
    res = verify_code_safety(code)
    assert res.valid is False
    assert any("Forbidden attribute access: '__class__'" in v or "Forbidden attribute access: '__subclasses__'" in v for v in res.violations)


def test_code_safety_rejects_syntax_errors() -> None:
    code = "def solution(x:\n    return x\n"
    res = verify_code_safety(code)
    assert res.valid is False
    assert any("SyntaxError" in v for v in res.violations)


def test_attestation_signing_and_verification() -> None:
    signer = AttestationSigner(validator_id="val-test-01")
    receipt = signer.sign(task_id="task-123", passed=True)
    assert receipt.task_id == "task-123"
    assert receipt.validator_id == "val-test-01"
    assert receipt.passed is True
    assert len(receipt.signature) == 64
    assert signer.verify(receipt) is True


def test_openminion_tool_audit_safety() -> None:
    clean = audit_code_safety("def solution(x: int) -> int:\n    return x + 1\n")
    assert clean["valid"] is True
    assert len(clean["violations"]) == 0

    bad = audit_code_safety("import subprocess\n")
    assert bad["valid"] is False
    assert len(bad["violations"]) > 0


def test_openminion_tool_execute_test_case() -> None:
    code = "def solution(x: int) -> int:\n    return x ** 2\n"
    res = execute_test_case(code, 4, 16)
    assert res["passed"] is True
    assert res["actual_output"] == 16


def test_openminion_agent_instantiation() -> None:
    sentinel = CortensorSentinel(validator_id="val-node-01")
    agent = sentinel.create_agent()
    assert agent.name == "CortensorSentinel-val-node-01"
    assert "audit_code_safety" in agent.tools
    assert "execute_test_case" in agent.tools
    assert "create_attestation_receipt" in agent.tools


def test_sentinel_end_to_end_verification() -> None:
    sentinel = CortensorSentinel(validator_id="val-node-01")
    code = "def solution(x: int) -> int:\n    return x * 3\n"
    passed, receipt = sentinel.verify_submission(
        task_id="task-triple-5",
        code=code,
        test_input=5,
        expected_output=15,
    )
    assert passed is True
    assert receipt.passed is True
    assert sentinel.signer.verify(receipt) is True


def test_environment_variable_configuration(monkeypatch) -> None:
    monkeypatch.setenv("CORTENSOR_VALIDATOR_ID", "val-env-override-99")
    monkeypatch.setenv("CORTENSOR_EPOCH", "42")

    signer = AttestationSigner()
    assert signer.validator_id == "val-env-override-99"
    assert signer.current_epoch == 42

    sentinel = CortensorSentinel()
    assert sentinel.validator_id == "val-env-override-99"
    assert sentinel.epoch == 42


def test_cli_verify_file() -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp:
        tmp.write("def solution(n: int) -> int:\n    return n + 10\n")
        tmp_path = Path(tmp.name)

    try:
        ret = verify_file(
            code_path=tmp_path,
            task_id="test-file-task",
            test_input=5,
            expected_output=15,
            verbose=False,
        )
        assert ret == 0
    finally:
        tmp_path.unlink(missing_ok=True)


def test_execute_test_case_timeout() -> None:
    # Bounded infinite loop should trigger ExecutionTimeoutError
    infinite_loop_code = "def solution(n: int) -> int:\n    while True:\n        pass\n"
    res = execute_test_case(infinite_loop_code, 5, 5, timeout_seconds=0.2)
    assert res["passed"] is False
    assert "timed out" in res["error"].lower()


def test_cli_verify_file_json(capsys) -> None:
    import json

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp:
        tmp.write("def solution(n: int) -> int:\n    return n * 4\n")
        tmp_path = Path(tmp.name)

    try:
        ret = verify_file(
            code_path=tmp_path,
            task_id="test-json-task",
            test_input=3,
            expected_output=12,
            json_mode=True,
        )
        assert ret == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["task_id"] == "test-json-task"
        assert data["status"] == "CERTIFIED"
        assert data["passed"] is True
        assert len(data["signature"]) == 64
    finally:
        tmp_path.unlink(missing_ok=True)


def test_query_hosted_portal_without_key() -> None:
    from cortensor_validator.openminion_agent import query_hosted_portal, verify_via_hosted_portal

    res = query_hosted_portal("def solution(x: int) -> int: return x", 1, 1, api_key=None)
    assert res["mode"] == "local"
    assert res["connected"] is False

    tool_res = verify_via_hosted_portal("def solution(x: int) -> int: return x * 2", 3, 6)
    assert tool_res["mode"] == "fallback_local"
    assert tool_res["result"]["passed"] is True


def test_query_hosted_portal_mock_connected(monkeypatch) -> None:
    from unittest.mock import MagicMock
    import urllib.request
    from cortensor_validator.openminion_agent import CortensorSentinel, query_hosted_portal

    class MockResponse:
        status = 200

        def read(self):
            return b'{"passed": true, "task_id": "test-mock-01", "miner_score": 1.0}'

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout: MockResponse())

    res = query_hosted_portal(
        "def solution(x: int) -> int: return x",
        1,
        1,
        api_key="ct-test-api-key",
    )
    assert res["mode"] == "hosted"
    assert res["connected"] is True
    assert res["data"]["passed"] is True

    # Test Sentinel routing with hosted portal
    sentinel = CortensorSentinel(api_key="ct-test-api-key")
    passed, receipt = sentinel.verify_submission(
        task_id="task-mock-hosted",
        code="def solution(x: int) -> int: return x",
        test_input=1,
        expected_output=1,
        use_hosted=True,
    )
    assert passed is True
    assert sentinel.last_mode == "hosted"
    assert receipt.passed is True
