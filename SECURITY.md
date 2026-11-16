# Eeksha AI: Deployment and data handling

## Current trust boundary

`webapp.py` is a localhost prototype intended for single-user, trusted-machine testing. It should not be exposed via a public proxy, tunnel, open firewall port or hosted server.

The server accepts user-submitted PNG, calibration JSON, and Eeksha ZIP inputs. Its temporary files and one-run in-memory artifacts are implementation details, **not** suitable public multi-user isolation or retention controls.

The `docs/index.html` research preview is a **static** page. Its example point cloud is generated in browser JavaScript. It neither requires uploads nor sends any dataset to the Flask server.

## Before any future hosted processing launch

- Assess image and ZIP parsing for zip bombs, decompression size, entry counts, path handling, and malformed metadata.
- Add authentication, authorization and tenant separation around input, run tokens, downloads, viewer, and report access.
- Enforce server-side computational quotas, memory limits, uploaded bytes, dimensions, processing duration and concurrent jobs.
- Ensure uploaded data and derived artifacts are isolated, cleaned up and encrypted as appropriate.
- Protect against cross-site requests and script/content injection; add appropriate origin, CSP and frame policies.
- Define a privacy/retention policy, consent/rights of uploaded field imagery, and incident-response procedure.
- Run adversarial security tests and independent review.

Do not label the current manual annotations or synthetic output as AI predictions or verified crop-safe ground truth.
