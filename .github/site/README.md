# Documentation site build

The site renders a small, explicit set of public repository Markdown with
markdown-it. Edit the canonical source documents to update setup instructions.
`pages.json` owns the source/route map; `build.cjs` owns the short landing copy and
HTML shell; `site.css` owns the design. No client JavaScript or remote assets.

## Local build

Use Node 24.20.0 and the committed dependency lock. From the repository root:

```sh
npm ci --prefix .github/site --ignore-scripts --omit=dev --no-audit --no-fund
npm test --prefix .github/site
npm run build --prefix .github/site
```

The build requires a new output directory. Its default is `.github/site/_site`.
For another destination, use `node .github/site/build.cjs PATH_TO_NEW_OUTPUT`.
Inspect old output before removing it or choose a new directory for a rebuild.
Open `index.html` directly for a local preview; no server is required.

## Content boundary

Only routes in `pages.json`, the authored landing page, `assets/site.css` and
the repository license are written. No recursive source-directory copy occurs.
Missing selected Markdown, missing local link targets or missing linked headings
fail the build before writing output. README's Quick Start is selected by heading,
not line numbers. Missing or duplicate section titles fail rather than drifting.

Links within the selected pages become relative HTML links, including anchors.
Other existing public repository files remain links to GitHub. Links from an
excerpt to a heading outside that excerpt remain links to the full source.
Images become descriptive text; raw HTML is escaped. New Markdown constructs or
unusual headings should be reviewed before expanding the allowlist.

The default canonical URL is `https://section11.net/`.
Navigation and CSS use relative paths so both the project subpath and direct-file
preview work. The canonical production URL uses the chosen custom domain.

Before publication, the owner must register/control section11.net, verify it
for their GitHub account, and configure it in this repository under Settings →
Pages → Custom domain. Configure apex DNS and the recommended www alias
using GitHub’s current custom-domain guide, then enable Enforce HTTPS when
available. This Actions deployment does not require a tracked CNAME file;
GitHub ignores one for custom Actions workflows. These source changes do not
configure DNS, register a domain, or publish the site.

## Publication

The Pages workflow builds on `main` Markdown, license and site-source changes,
and supports manual dispatch on `main`. All public Markdown changes trigger it
because selected pages also link to unselected source documents.
Only `.github/site/_site` is uploaded. The deploy job has Pages/OIDC permissions;
the build job can read repository content and Pages metadata. The owner enables GitHub Actions
as the Pages source and controls the `github-pages` environment. No athlete
credentials or repository-wide write permission is needed.

The checkout SHA follows the existing repository examples. Pages action major
versions follow the supplied official Pages guidance. Node setup uses
`actions/setup-node@v4`; its major tag, like the Pages action tags, is not a
full-commit pin. Resolve these through the owner's normal dependency review if
full-SHA pinning is required before publication.

## Updater and license

All build files and generated output live under `.github/`, already excluded by
`examples/sync.py`'s manifest generator. They do not become athlete updater
payloads. The root README integration link is an ordinary source change; the
maintainer regenerates `manifest.json` through the normal release workflow.
Do not commit generated site output or node_modules.

Site source follows the project's MIT license, copyright 2026 CrankAddict.
No fonts, images, scripts or third-party components are vendored into the site.
The build-only dependencies and their licenses are recorded in package-lock.json:
markdown-it, linkify-it, mdurl, punycode.js and uc.micro (MIT), entities
(BSD-2-Clause), argparse (PSF-2.0). They are installed for building and are not
copied into the public output.
