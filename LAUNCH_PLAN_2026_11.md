# Eeksha: November 2026 launch execution plan

**Deadline:** 2026-11-30 (IST). **Budget:** zero upfront. **Owner:** Manoj Kumar Dadala. **Source of truth:** `Roy0x/eeksha` on GitHub.

## What is being launched

A public, clearly marked **research MVP / developer preview** with a runnable local workflow and a downloadable example/review candidate. A hosted product that processes strangers' uploads is **not** authorized or safe by merely exposing the current Flask dev server. Keep `/correct`, `/annotate`, `/review`, `/process` and file-upload/export endpoints bound to localhost until a production security and persistence pass is completed.

## Ordered work and evidence gates

| Window (IST) | Priority | Deliverable | Definition of done |
| --- | --- | --- | --- |
| Nov 9–11 | P0 | Freeze and publish current local MVP | GitHub main holds 33-test suite, reproducible real-data smoke test, limitations, setup and release notes; green local CI-style run. |
| Nov 12–15 | P0 | Repeatable Windows onboarding | Clean Python installation tested; single startup command; demo loads, RGB previews, existing ZIP resumes; erroneous ZIP receives actionable validation message. |
| Nov 16–19 | P0 | Independent dataset evidence | Reviewer checks broccoli head mask visually, separately records disputed pixels; RGB/depth alignment, camera metadata and depth coverage documented. No claim of true physical accuracy without a measured reference. |
| Nov 20–23 | P0 | Public read-only showcase | Static page with 3D explorer/demo screenshots, 90-second workflow video, GitHub/download links, dataset attribution/license, explicit limitations and contact. No public upload processing. |
| Nov 24–26 | P1 | Hardening and UX | Re-test PNG/ZIP limits and archive safety; error and loading states; keyboard/resize checks; accessibility and mobile readability for showcase. |
| Nov 27–29 | P0 | Release candidate and external tester | Fresh laptop/clean browser walk-through, at least one external tester, documented defects; versioned GitHub release with checksums and samples permitted by source license. |
| Nov 30 | P0 | Launch and distribute | Public showcase reachable via HTTPS, release/download valid, demo video accessible, launch post published, feedback channel open. |

## Product decisions

- **Audience:** research labs, agricultural-robotics builders, computer-vision researchers needing an auditable semantic RGB-D annotation/QA workflow.
- **First proof of value:** one real broccoli RGB-D scene produces editable class labels, a traceable 3D export, and a QA report, with uncertainty visible.
- **No premature claims:** neither automated labeling, robotic reliability, certified ground truth, field-calibrated metric accuracy, nor proprietary data collection has been demonstrated.
- **No paid infrastructure required:** use GitHub for source/releases and a free static host for the public demo/landing page. Verify the chosen host's terms and capacity before deploying.
- **Current blocker for hosted editing:** in-memory single-run `RUNS` store, server-side uploads and Flask dev process; a secure hosted editor requires multi-user isolation, bounded resource usage, persistent object storage or client-side processing, and security review.

## Launch acceptance checklist

- [ ] `python -m unittest discover -q` passes in a clean installation.
- [ ] Real dataset smoke test produces an internally consistent ZIP, retains original source, and reports no invented depth.
- [ ] User completes entire Windows browser workflow without developer intervention.
- [ ] Source dataset and code license/attribution verified before redistribution.
- [ ] GitHub release tag, README, evidence report and download assets are public and correct.
- [ ] Static HTTPS showcase loads and 3D preview works in Chrome and a mobile browser.
- [ ] Independent reviewer caveats and known limitations are prominently shown.
- [ ] Public contact/feedback link works; first five relevant researcher/builder conversations requested.

## Go / no-go rule

If a safe publicly hosted editor cannot be built and verified by Nov 27, launch **the local desktop-style research MVP plus a static interactive showcase** on Nov 30. Do not open a localhost Flask development server to the public internet or call it a production SaaS.
