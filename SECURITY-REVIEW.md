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