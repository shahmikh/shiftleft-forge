# 🛡️ ShiftLeft Forge

> A production-grade, six-layer DevSecOps security pipeline built on GitHub Actions and AWS Free Tier.  
> Every commit is scanned, every container is signed, every finding is explained.

![Pipeline Status](https://github.com/shahmikh/shiftleft-forge/actions/workflows/pipeline.yml/badge.svg)
![Security Scanning](https://img.shields.io/badge/security-6--layer--scanning-brightgreen)
![Signed](https://img.shields.io/badge/image--signing-Cosign%20%2B%20Sigstore-blue)
![IaC](https://img.shields.io/badge/IaC-Terraform%20%2B%20Checkov-purple)
![AWS](https://img.shields.io/badge/registry-AWS%20ECR-orange)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## What This Is

Most teams bolt on one scanner and call it "DevSecOps."  
This project implements **layered, defense-in-depth security** across six distinct stages — from the first line of code all the way to a cryptographically signed, production-ready container image.

Built to demonstrate real-world DevSecOps engineering, not tutorial-following.

---

## Pipeline Architecture

```
Developer pushes code
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                   GitHub Actions Pipeline                        │
│                                                                  │
│  Stage 1 ▶  Secret Scanning         gitleaks                    │
│             Scans full git history for leaked credentials        │
│                                                                  │
│  Stage 2 ▶  SAST                    Semgrep                     │
│             Static code analysis — OWASP Top 10 rule packs      │
│                                                                  │
│  Stage 3 ▶  Dependency Scanning     pip-audit                   │
│             Checks every package against the OSV CVE database   │
│                                                                  │
│  Stage 4 ▶  IaC Scanning            Checkov                     │
│             Scans Terraform for misconfigurations before deploy  │
│                                                                  │
│  Stage 5 ▶  Container Build         Docker                      │
│             Non-root user, slim base image, pinned layers        │
│                                                                  │
│  Stage 6 ▶  Image Scanning          Trivy                       │
│             Scans OS packages + app deps inside the built image  │
│                                                                  │
│  Stage 7 ▶  Push to Registry        AWS ECR via OIDC            │
│             Short-lived credentials only — no stored AWS keys    │
│                                                                  │
│  Stage 8 ▶  Keyless Signing         Cosign + Sigstore           │
│             Cryptographic proof of build origin, no private key  │
│                                                                  │
│  Stage 9 ▶  Aggregate Findings      Custom Python tool          │
│             Merges all SARIF outputs into one ranked summary     │
│                                                                  │
│  Stage 10 ▶ PR Comment              Sticky bot comment          │
│             Posts the summary on every pull request automatically│
│                                                                  │
│  DEPLOY GATE: blocks merge if any CRITICAL severity found        │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
  AWS ECR — signed, scanned, traceable image
```

---

## Tech Stack

| Layer | Tool | Purpose |
|---|---|---|
| Secret Scanning | gitleaks | Detects credentials in code and git history |
| SAST | Semgrep | Static code analysis against OWASP Top 10 |
| SCA | pip-audit | CVE scanning of Python dependencies via OSV |
| IaC | Checkov | Terraform misconfiguration detection |
| Container Scan | Trivy | OS + app vulnerability scanning inside images |
| Registry | AWS ECR | Private container registry (free tier) |
| Auth | GitHub OIDC | Short-lived AWS credentials, zero stored secrets |
| Signing | Cosign + Sigstore | Keyless, tamper-evident image signing |
| Aggregation | Python (custom) | SARIF merger + ranked severity summary |
| CI/CD | GitHub Actions | Pipeline orchestration |

---

## Security Design Decisions

### 1. Why OIDC instead of stored AWS keys?

Long-lived AWS Access Keys stored as GitHub Secrets are a credential-leak waiting to happen. This pipeline uses **GitHub's OIDC identity tokens** — GitHub cryptographically proves "this is workflow X running on repo Y," AWS trusts it and issues a credential that **expires in under one hour**, automatically. No secret sits anywhere.

```yaml
# No AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY anywhere in this repo.
# The role trust policy restricts access to this specific repo only:
"token.actions.githubusercontent.com:sub": "repo:YOUR-USERNAME/shiftleft-forge:*"
```

### 2. Why keyless image signing?

Traditional image signing requires a private key you must store, protect, rotate, and never lose. **Cosign keyless signing** uses the same OIDC token as proof of identity, gets a short-lived certificate from Sigstore's Fulcio CA, records the signature in a public tamper-evident log (Rekor), then the certificate expires. No key to manage. Ever.

Verify any image from this pipeline:
```bash
cosign verify \
  --certificate-identity-regexp "https://github.com/YOUR-USERNAME/shiftleft-forge/*" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  YOUR_ECR_REGISTRY/shiftleft-forge-demo:COMMIT_SHA
```

### 3. Why this stage order?

**Fail fast, fail cheap.** Secret scanning takes under 30 seconds. If a credential was accidentally committed, the pipeline stops before wasting 4 minutes building a Docker image. Expensive stages (build + scan) only run after cheap stages pass.

### 4. Why a custom Python aggregator?

Six separate scanner bot comments on a PR get ignored by developers. One ranked, prioritised summary gets read. The aggregator reads every scanner's SARIF output, sorts findings by severity, and posts a single comment — plus exits with code 1 if any CRITICAL finding exists, blocking the merge.

---

## Real Findings (Before/After)

This project was built against a real (intentionally imperfect) application. The pipeline found and documented two genuine issues:

### Finding 1 — Dependency CVE (pip-audit)

| | Detail |
|---|---|
| Package | `requests==2.25.1` |
| CVE | `GHSA-j8r2-6x86-q33q` |
| Severity | HIGH |
| Fix | Upgrade to `requests==2.31.0` |

**Before:**
```
Name      Version  ID                   Fix Versions
--------  -------  -------------------  ------------
requests  2.25.1   GHSA-j8r2-6x86-q33q  2.31.0
```

**After:** `pip-audit` passes clean. `requests` pinned to `2.31.0`.

---

### Finding 2 — IaC Misconfiguration (Checkov)

| | Detail |
|---|---|
| Resource | `aws_s3_bucket.demo_bucket` |
| Checks Failed | CKV_AWS_19 (no encryption), CKV_AWS_21 (no versioning), CKV2_AWS_6 (no public access block) |
| Fix | Added `aws_s3_bucket_server_side_encryption_configuration`, `aws_s3_bucket_versioning`, `aws_s3_bucket_public_access_block` resources |

**Before (3 Checkov failures):**
```
Check: CKV_AWS_19 — Ensure data stored in S3 is encrypted at rest
  FAILED for resource: aws_s3_bucket.demo_bucket

Check: CKV_AWS_21 — Ensure the S3 bucket has versioning enabled
  FAILED for resource: aws_s3_bucket.demo_bucket

Check: CKV2_AWS_6 — Ensure that S3 bucket has a Public Access block
  FAILED for resource: aws_s3_bucket.demo_bucket
```

**After (all pass):** Encryption, versioning, and public access block added to Terraform. Checkov exits 0.

---

## Repository Structure

```
shiftleft-forge/
├── .github/
│   └── workflows/
│       └── pipeline.yml          # Full 10-stage security pipeline
├── app/
│   ├── main.py                   # Flask demo API
│   ├── requirements.txt          # Python dependencies
│   └── Dockerfile                # Non-root, hardened container
├── infra/
│   └── main.tf                   # Hardened Terraform (post-fix)
├── aggregator/
│   └── aggregate.py              # Custom SARIF merger + deploy gate
├── docs/
│   ├── architecture.png          # Pipeline architecture diagram
│   ├── before-checkov.png        # Checkov failures — before fix
│   ├── after-checkov.png         # Checkov passing — after fix
│   ├── pip-audit-finding.png     # CVE finding in pip-audit
│   └── cosign-verify-output.png  # Signed image verification
└── README.md
```

---

## Running Locally (macOS)

### Prerequisites

```bash
# Install all tools via Homebrew
brew install awscli python cosign semgrep gitleaks

# Install Python tools
pip3 install checkov pip-audit
```

### Run each scanner locally

```bash
# Secret scan
gitleaks detect --source . --verbose

# SAST
semgrep --config p/owasp-top-ten app/

# Dependency CVE scan
pip-audit -r app/requirements.txt

# IaC scan
checkov -d infra/

# Build and scan container locally
docker build -t shiftleft-forge-demo:local ./app
trivy image shiftleft-forge-demo:local
```

### Run the aggregator

```bash
# After running scanners with --output sarif flags
python3 aggregator/aggregate.py *.sarif
cat pr-summary.md
```

---

## AWS Setup (Free Tier)

**Cost: $0** — this project uses only ECR free tier (500 MB/month free for 12 months).

1. Create ECR repository:
```bash
aws ecr create-repository \
  --repository-name shiftleft-forge-demo \
  --region us-east-1
```

2. Set up GitHub OIDC trust in IAM (no static keys stored anywhere — see build guide for full steps).

3. Add your role ARN to `pipeline.yml`:
```yaml
role-to-assume: arn:aws:iam::YOUR_ACCOUNT_ID:role/github-actions-shiftleft-forge
```

---

## What I Learned

- **Defence in depth across a CI/CD pipeline** — not one scanner, but six distinct layers each catching a different class of problem
- **OIDC federation** — why short-lived, identity-bound credentials are fundamentally safer than long-lived secrets, and how to configure the trust relationship between GitHub and AWS
- **Keyless cryptographic signing** — how Sigstore/Cosign eliminates the private-key management problem while maintaining full tamper-evidence
- **SARIF format** — how to aggregate findings from multiple tools into a single structured report
- **Fail-fast pipeline ordering** — why stage sequence is a design decision with real performance and security implications
- **IaC misconfiguration in practice** — what Checkov checks actually look like against real Terraform, and how to fix them
- **Supply chain thinking** — the difference between securing code vs. securing the pipeline that builds and ships code

---

## Resume Bullets

> These are the actual bullets used on my resume for this project.

- Designed and built a six-layer DevSecOps pipeline (secrets, SAST, SCA, IaC, container, signing) as a reusable GitHub Actions workflow, enforcing severity-based deploy gates across every stage.
- Implemented GitHub OIDC federation with AWS, eliminating all long-lived credentials from CI/CD — no AWS keys stored anywhere in the pipeline.
- Achieved cryptographic supply-chain attestation using Sigstore/Cosign keyless signing, making every ECR image traceable to its exact source commit with tamper-evident verification.
- Built a custom Python SARIF aggregator that merges findings from four scanners into a single ranked PR comment, replacing six separate noisy bot outputs with one actionable summary.
- Identified and remediated a real published CVE (`GHSA-j8r2-6x86-q33q` in `requests==2.25.1`) and three Terraform misconfigurations (missing S3 encryption, versioning, public access block), documented as before/after evidence.

---

## Part of a Larger Portfolio

This is **Project 1** in a five-project DevSecOps/Cloud Security portfolio:

| # | Project | Focus |
|---|---|---|
| 1 | **ShiftLeft Forge** (this) | Six-layer DevSecOps pipeline |
| 2 | SecureGate Cloud | Multi-account AWS Landing Zone |
| 3 | KubeSentinel | Kubernetes hardening + runtime defence |
| 4 | SentinelStack | AI-augmented SIEM + SOC automation |
| 5 | AI Supply Chain Guard | LLM/RAG pipeline security scanner |

---

## Connect

**LinkedIn:** https://www.linkedin.com/in/syed-shahmikh-ali-6b962b201/  
**GitHub:** https://github.com/shahmikh

---

*Built in 2026 as part of a DevSecOps/Cloud Security/AIOps portfolio transition. All findings are real — no staged vulnerabilities.*
