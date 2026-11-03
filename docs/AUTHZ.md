# Product Forge authorization modes

Product Forge has two explicit authorization modes. The default remains local
bearer auth for a single operator; OIDC is opt-in for a shared workspace
deployment.

| Mode | Identity | Workspace boundary | Mutations |
| --- | --- | --- | --- |
| `local-bearer` | `Authorization: Bearer <pf token>` | `config.principals[].workspaces`; empty principals are local wildcard | editor; token rotation/revocation is admin |
| `oidc` | verified JWT from configured issuer/JWKS | required `workspaces` or `workspace_ids` claim | `roles`/`role`: viewer < editor < admin |

## OIDC configuration

Set the following values in `config.json` or environment variables before
starting the API:

```json
{
  "oidc": {
    "enabled": true,
    "issuer": "https://keycloak.example/realms/product",
    "audience": "product-forge",
    "jwks_url": "https://keycloak.example/realms/product/protocol/openid-connect/certs"
  }
}
```

The server verifies `iss`, `aud`, `exp`, `sub`, and the JWT signature through
the configured JWKS endpoint. An identity without an explicit workspace claim
is denied; it never becomes a wildcard. Product, source, knowledge, agent,
workspace, and session-context access is checked server-side.

The Portal should obtain the JWT through the organization's Authorization Code
flow with PKCE and send it as a bearer token. Product Forge does not accept a
spoofable `X-PF-Principal` header as identity in OIDC mode. Keep local bearer
mode enabled only for local development or a deliberately single-user
deployment.

## Migration

1. Keep local bearer mode enabled while creating the IdP client and JWKS URL.
2. Add `workspaces` and `roles` claims to the Keycloak client scope.
3. Exercise the IdP-mocked authorization tests and one real Keycloak run.
4. Enable OIDC and verify cross-workspace requests return `PF-FORBIDDEN`.
5. Remove shared bearer tokens after the Portal login flow is validated.

Unknown or incomplete IdP configuration remains an explicit unverified/error
state; it is never silently downgraded to local wildcard access.
