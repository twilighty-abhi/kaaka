# Security policy

Kaaka handles callers' phone numbers, messages and locations. Please report security problems privately.

## Reporting

Use GitHub's **Report a vulnerability** button on the repository's Security tab. Do not open a public issue for a vulnerability. Include what you found, how to reproduce it and what an attacker could do with it.

## Supported versions

Only the latest release receives fixes.

## Scope

In scope: the control room server (`server/`), the website (`site/`), and the Kaaka Call and Kaaka Sensors apps.

Running Kaaka safely is covered in the docs (`/docs/deployment.html` and `/docs/safety.html` on a running server): always set `KAAKA_ADMIN_TOKEN`, serve public access over https, and restrict access to the data directory.
