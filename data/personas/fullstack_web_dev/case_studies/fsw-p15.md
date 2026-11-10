---
project: fsw-p15
client_industry: SaaS
date: 2025-09
duration_weeks: 4
repo: teamboard-auth
---
<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# Teamboard: authentication in 2025

When Teamboard reached out, enterprise prospects required SSO and the homegrown login had no MFA. I spent 4 weeks on it. The heart of the solution was moved login to a standard auth library with Google and SAML SSO, passkeys and session hardening, built with TypeScript, a fast, SEO-friendly React website, Auth.js, PostgreSQL.

The part I am proudest of: closed two enterprise deals blocked on SSO. Password reset tickets down 55%.
