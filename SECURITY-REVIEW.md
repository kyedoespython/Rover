# Security Review - Rover

## 1. Vulnerability Scan (Docker Scout)
- **Critical/High Vulnerabilities:** 0 (Zero fixable critical or high vulnerabilities found in the application layer).
- **Medium Finding:** CVE-2025-45582 in Debian `tar`. No upstream fix available as of this review. This binary is only used during image builds and is not exposed at runtime. Accepted risk; we will monitor upstream for a patch.

## 2. Supply Chain & Attestations
- SBOM (Software Bill of Materials) and Provenance attestations are generated and attached to the image via `docker buildx`.
- Docker Scout confirms all required supply chain attestations are present.

## 3. License Compliance
- **Copyleft Packages:** Scout flagged copyleft-licensed packages (GPL/LGPL) in the Debian base image. 
- **Decision:** Accepted. This application is not distributed as a compiled, closed-source binary. The use of these licenses in the base OS complies with open-source distribution norms.

## 4. Container Security
- The application runs as a **non-root user** (verified by Scout).
- The source code is baked into the image (no production bind mounts).

## 5. Dependency and Application Review (2026-11-10)
- **Application review:** Reviewed `main/models/user.py`, the Notes route and persistence boundaries, and relevant authentication, API-key, session, and CSRF configuration. No actionable vulnerabilities were identified in this bounded scope; this was not a full review of every route or service.
- **Python dependency finding:** `pytest==8.4.2` was affected by PYSEC-2026-1845 / CVE-2025-71176 (vulnerable temporary-directory handling on Unix, with local denial-of-service or possible privilege escalation impact). Updated the pin to `pytest==9.0.3`, the fixed release.
- **Verification:** `pip-audit` reported no known vulnerabilities in `requirements.txt` or the active `.venv` after the update. `npm audit --omit=dev` reported zero vulnerabilities.
- **Remaining scope:** This review did not rerun Docker Scout or re-evaluate the container finding documented above.
