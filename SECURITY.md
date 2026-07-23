# Security Policy

## Reporting a vulnerability

If you discover a security issue in **GitHub Growth Bot**, please report it **privately**.

**Email:** [contact@arnobmahmud.com](mailto:contact@arnobmahmud.com)

Please include:

- A clear description of the issue
- Steps to reproduce (or a minimal proof of concept)
- Affected component (e.g. backend API, frontend auth, SSE proxy)
- Impact assessment if you have one (e.g. data exposure, auth bypass)

**Do not** open a public GitHub issue or pull request for sensitive reports.

I aim to acknowledge valid reports within a few business days and will work with you on a fix timeline when appropriate.

## Please avoid in reports

- Sharing production secrets, private OAuth tokens, or real user data beyond what is needed to demonstrate the issue
- Destructive testing against systems you do not own
- Social-engineering GitHub.com or third-party providers as part of a “report” against this repo

## Scope (high level)

In scope examples:

- Auth / session / API key handling flaws in this project’s code
- Cross-user data leaks in multi-tenant endpoints
- Injection, SSRF, or unsafe deserialization in this codebase
- Secrets accidentally exposed by project configuration templates (not your private `.env`)

Out of scope examples:

- Denial of service via volumetric traffic alone
- Issues solely in upstream GitHub, Vercel, or LLM provider platforms
- Missing security headers on a local `npm run dev` setup without a realistic exploit path

## Safe harbor

Security research conducted in good faith against instances you own (or with explicit permission), that follows this policy and avoids privacy violations or service disruption, is appreciated. Thank you for helping keep the project and its users safer.
