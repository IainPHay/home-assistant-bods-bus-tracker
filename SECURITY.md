# Security

## Sensitive information

A BODS API key is required to retrieve live vehicle data. Treat the key as a credential.

- Do not include BODS API keys in issues, screenshots, logs, or pull requests.
- If routed walking is enabled, do not post routing-provider credentials or precise person/device coordinates.
- Home Assistant diagnostics produced by this integration are designed to redact the BODS API key and live vehicle coordinates.
- BODS Bus Tracker stores only the selected Home Assistant travel-time entity ID; provider credentials and the provider's origin/destination configuration remain owned by the separate routing integration.

## Reporting a security issue

If you believe you have found a security issue, avoid publishing credentials or exploit details in a public issue. Contact the repository owner privately through GitHub where possible, then provide only the minimum information required to reproduce the problem.
