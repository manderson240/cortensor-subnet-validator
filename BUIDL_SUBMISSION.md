# DoraHacks BUIDL Submission Guide: Cortensor Task Sentinel

**Hackathon**: [Cortensor Hackathon #5 (DoraHacks ID: 2418)](https://dorahacks.io/hackathon/2418/detail)  
**Track**: Subnet Task Verification Agent  
**Deadline**: December 18, 2026, 23:59 UTC-8  
**Repository**: `https://github.com/manderson240/cortensor-subnet-validator`  

---

## Copy-Paste Form Fields for DoraHacks

### 1. Project Name
```text
Cortensor Task Sentinel
```

### 2. Tagline (Under 120 characters)
```text
Autonomous Subnet Task Verification Agent built with OpenMinion 0.1 SDK and zero-token deterministic AST safety defense.
```

### 3. Track Selection
```text
OpenMinion 0.1 Python SDK / Subnet Task Verification Track
```

### 4. Project Links
- **GitHub Repository**: `https://github.com/manderson240/cortensor-subnet-validator`
- **Demo Video (2K QHD)**: Located at `docs/cortensor_pitch_demo.mp4` in repository (upload to YouTube/Loom as unlisted/public if URL required)
- **Developer Feedback Report**: `https://github.com/manderson240/cortensor-subnet-validator/blob/main/docs/cortensor_openminion_feedback_report.md`
- **Upstream Contribution**: `https://github.com/openminion/openminion/pull/734`

---

### 5. Detailed Project Description (Markdown for DoraHacks Form)

```markdown
# Cortensor Task Sentinel

### The Problem
Decentralized AI subnets face a fundamental security dilemma: miners submit arbitrary algorithm proposals that validators must verify before paying rewards. Relying on slow, expensive cloud LLMs creates latency bottlenecks and exposes validator nodes to prompt injection, trojaned bytecode, and resource-exhaustion loops.

### The Solution: Cortensor Task Sentinel
Built with the official **OpenMinion 0.1 Python SDK** (`openminion.Agent` and `@tool`), **Task Sentinel** delivers sub-millisecond, deterministic verification for Cortensor Subnet nodes:
1. **Zero-Token AST Safety Engine**: Pre-execution static analysis inspects source proposals in under 0.5 ms, intercepting forbidden system calls (`os.system`, `subprocess`, `eval`) and infinite CPU loops before execution.
2. **Deterministic Correctness Execution**: Executes verified functions against deterministic input-output suites with hard CPU budget timeouts.
3. **Epoch-Fenced Cryptographic Receipts**: Generates HMAC-SHA256 attestation receipts committed to the subnet mempool.
4. **Hosted Portal Adapter**: Supports hosted Cortensor API routing (`CORTENSOR_API_KEY`) with automatic local AST fallback.

### Upstream OpenMinion Contribution
As part of our evaluation of the OpenMinion 0.1 SDK, we diagnosed and resolved a critical circular import between `Agent` and `AgentExecutor` in the upstream framework ([PR #734](https://github.com/openminion/openminion/pull/734)). We also authored a comprehensive 7-page developer feedback report ([`docs/cortensor_openminion_feedback_report.md`](docs/cortensor_openminion_feedback_report.md)) detailing SDK developer experience, serialization ergonomics, and AST hook recommendations.

### Key Performance Metrics
- **Verification Cycle Latency**: < 0.9 ms total execution time
- **LLM Token Overhead**: 0 tokens burned for deterministic verification
- **Unit Test Pass Rate**: 15/15 unit tests passing in 2.83s
- **Codebase Simplicity**: KISS Grade A+ (15 clean files, 2 runtime dependencies)

### How to Verify in 60 Seconds
```bash
git clone https://github.com/manderson240/cortensor-subnet-validator.git
cd cortensor-subnet-validator
uv run pytest     # Runs 15/15 unit tests in < 3 seconds
uv run sentinel   # Runs full end-to-end verification demo in < 1 ms!
```
```
