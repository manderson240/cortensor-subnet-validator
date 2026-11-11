"""Cryptographic Attestation Receipts for Subnet Verification.
=============================================================
Signs verification results using HMAC-SHA256 with epoch fencing and timestamps.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AttestationReceipt:
    """Tamper-evident attestation receipt for a verified subnet task."""

    task_id: str
    validator_id: str
    epoch: int
    passed: bool
    signature: str
    timestamp_ns: int


class AttestationSigner:
    """Signs and verifies HMAC-SHA256 attestation receipts."""

    def __init__(
        self,
        validator_id: str = "val-cortensor-01",
        secret_key: bytes = b"cortensor_subnet_secret_key_2026",
        current_epoch: int = 1,
    ) -> None:
        self.validator_id = validator_id
        self.secret_key = secret_key
        self.current_epoch = current_epoch

    def sign(
        self,
        task_id: str,
        passed: bool,
        epoch: int | None = None,
    ) -> AttestationReceipt:
        """Create an attestation receipt for a task outcome."""
        target_epoch = epoch if epoch is not None else self.current_epoch
        timestamp_ns = time.time_ns()

        message = f"{task_id}:{self.validator_id}:{target_epoch}:{passed}:{timestamp_ns}".encode("utf-8")
        sig = hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()

        return AttestationReceipt(
            task_id=task_id,
            validator_id=self.validator_id,
            epoch=target_epoch,
            passed=passed,
            signature=sig,
            timestamp_ns=timestamp_ns,
        )

    def verify(self, receipt: AttestationReceipt) -> bool:
        """Verify the cryptographic integrity of an attestation receipt."""
        message = (
            f"{receipt.task_id}:{receipt.validator_id}:{receipt.epoch}:{receipt.passed}:{receipt.timestamp_ns}"
        ).encode("utf-8")
        expected_sig = hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(receipt.signature, expected_sig)
