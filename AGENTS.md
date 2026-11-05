# Photo Theme development

Keep this a user-owned Omarchy plugin. Never modify packaged Omarchy files.
Do not commit photos, OAuth credentials, local config, or caches. Matugen is an external GPLv2 dependency; retain LICENSE.omarchy-auto-theme for the reused MIT palette template.

## Agent skills

Issue tracker: local development notes and tests in this repository; no external issue tracker configured.
Domain: PRODUCT.md and DESIGN.md describe the product and native UI contracts.
Validation: `python -m unittest discover -s tests -v`, `omarchy plugin validate .`, and real shell lifecycle checks. Exercise picker selection, paused rotation, switching themes, and disable/enable before declaring done.
