# Eeksha AI — November 30, 2026 public research preview

Release type: **public research preview**, not a production hosted dataset processing service.

## Release scope

- [x] Static public landing page source in `docs/index.html` with a synthetic, browser-only interactive 3D example.
- [x] Local Python RGB-D processing and annotation workflow.
- [x] Automated unit tests and synthetic export smoke job on Python 3.11/3.13.
- [ ] Run and review final CI on the release commit.
- [ ] Browser QA on desktop and mobile, including Canvas fallback/keyboard navigation.
- [ ] Test real licensed RGB-D input with the correct supplied calibration, export and provenance.
- [ ] Verify annotation ZIP resume, correction and disagreement-review paths on the target laptop.
- [ ] Conduct input/security review and decide whether any processing backend will ever be internet-facing.
- [ ] Publish the static page and confirm the **actual** public URL in an incognito browser.
- [ ] Record a real, reproducible 60–90 second product walkthrough.
- [ ] Add independent tester notes and log at least three target-user conversations.
- [ ] Create tagged release and verify installation instructions from a clean checkout.

## Deployment — static preview only

Recommended cost-free option: GitHub Pages, publishing from the `/docs` directory on the protected/reviewed `main` branch:

1. Finish code review and merge the approved PR into `main`.
2. GitHub repository → Settings → Pages → Build and deployment → Deploy from a branch.
3. Select `main`, folder `/docs`, and save.
4. Check the deployment status, then verify the URL GitHub reports. Do not assume Pages is enabled.
5. Confirm every CTA, responsive layout, rendered point cloud, attribution, and limitations text.

**Do not publicly deploy `webapp.py` or bind it to `0.0.0.0`.** The Flask app is built for localhost. The public static page makes no network requests to this backend.

## Go / no-go gate

Ship the public preview only when tests, browser smoke checks, dataset licensing/attribution, instructions, and external URL verification pass. A blank or broken page is a no-go.

A hosted multi-user product needs a separate architecture: authentication, tenant isolation, secure temporary file handling, cleanup, enforced upload and decompression limits, resource quotas, timeouts, privacy policy, and abuse protection. That is **not** part of this release.

## Truthful claims

Supported: calibrated RGB-D → colored / labeled 3D point clouds; imported or human-labeled masks; provenance, structural QA and reproducible exports.

Not supported: AI-generated crop/weed labels; automatic geometry calibration; independent metric accuracy; certified semantic ground truth; live robot operation or safe autonomous weeding.

## Priority calendar

- **Nov 16–19:** Static preview and CI, eliminate release-blocking regressions.
- **Nov 20–23:** Real licensed dataset regression, upload/ZIP audit, browser testing.
- **Nov 24–26:** External user walkthroughs, examples, documentation and demonstration recording.
- **Nov 27–29:** Feature freeze, clean install, static site publication, end-to-end release QA.
- **Nov 30:** Public research preview announcement and issue intake.

Avoid feature creep: semantic model training, billing, hosted accounts, and robot control are deferred.
