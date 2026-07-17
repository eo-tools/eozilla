# Wraptile Usage

## Local execution service

Running Wraptile with a local service:

```commandline
pixi shell
wraptile run -- wraptile.services.local.testing:service --processes --max-workers=5
```

The possible options are

* `--processes` /  `--no-processes`: Whether to use processes or threads, defaults
  to threads.
* `--max-workers=INTEGER`: Maximum number of processes or threads, defaults to 3.

## Airflow service

Start by running a local Airflow instance with some test DAGs:
```commandline
cd eozilla-airflow
pixi install
pixi run airflow standalone
```

Then run the Wraptile server with the local Airflow instance (assuming
the local Airflow webserver runs on http://localhost:8080):

```commandline
pixi shell
wraptile run -- wraptile.services.airflow:service --airflow-password=a8e7f4bb230
```

The possible options are

* `--airflow-base-url=TEXT`: The base URL of the Airflow web API, defaults to 
  `http://localhost:8080`. 
* `--airflow-username=TEXT`: The Airflow username, defaults to `admin`. 
* `--airflow-password=TEXT`: The Airflow password. 
  For an Airflow installation with the simple Auth manager, use the one from
  `.airflow/simple_auth_manager_passwords.json.generated`.

### Airflow authentication

By default, the Airflow service authenticates with a username and password
against Airflow's own `/auth/token` endpoint (see options above, or the
`AIRFLOW_USERNAME` / `AIRFLOW_PASSWORD` env vars). This suits a local Airflow
with the simple auth manager.

For a deployment where Airflow is configured against an identity provider
(and typically fronted by a gateway), set these env vars instead. Any
OIDC-compliant provider works; only the standard token endpoint and grant are
used.

* `OIDC_TOKEN_URL`: The provider's token endpoint, e.g.
  `https://idp.example/realms/eo/protocol/openid-connect/token`.
* `OIDC_CLIENT_ID`: The client ID registered for wraptile's service account.
* `OIDC_CLIENT_SECRET`: The client secret for that service account. Omit it for
  a public client.
* `OIDC_AUDIENCE` (optional): The `audience` sent with the token request,
  defaults to `airflow`.

When `OIDC_TOKEN_URL` and `OIDC_CLIENT_ID` are both set, wraptile stops using
`--airflow-username` / `--airflow-password` and performs a **two-step token
exchange** instead:

1. mint a `client_credentials` token at `OIDC_TOKEN_URL`;
2. `POST` it to Airflow's `/auth/token` (as the `Authorization` header) together
   with the client credentials (in the body), receiving an **Airflow-issued**
   JWT in return;
3. use that Airflow JWT as the bearer for every API call.

The Airflow JWT is cached and refreshed shortly before it expires, on its own
schedule — the two tokens have unrelated lifetimes.

> **Why two tokens, and not just the provider's?**
> **Airflow's API accepts only tokens Airflow itself issued.** Sending the
> provider's token as the API bearer returns `403 "Invalid JWT token"`, even
> though Airflow is configured against that very provider — an auth manager uses
> the provider to authenticate a *login* and to answer *authorization* queries,
> then mints its own JWT. Airflow's own token is typically HMAC-signed with no
> `iss` claim, which is also why a gateway cannot validate it.
>
> So each leg is authenticated by whichever party can actually verify it: the
> **gateway** checks the provider token on the `/auth/token` request (this is
> where audience and role enforcement happen), and **Airflow** checks its own JWT
> on everything after. Without a gateway in the path the `Authorization` header
> is simply ignored, and the same flow still works.
