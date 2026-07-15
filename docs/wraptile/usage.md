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
`AIRFLOW_USERNAME` / `AIRFLOW_PASSWORD` env vars).

If a gateway is set up in front of Airflow, set these env vars to switch to
OAuth2 client-credentials auth instead. Any OIDC-compliant identity provider
works; only the standard token endpoint and grant are used.

* `OIDC_TOKEN_URL`: The provider's token endpoint, e.g.
  `https://idp.example/realms/eo/protocol/openid-connect/token`.
* `OIDC_CLIENT_ID`: The client ID registered for wraptile's service account.
* `OIDC_CLIENT_SECRET`: The client secret for that service account. Omit it for
  a public client.
* `OIDC_AUDIENCE` (optional): The `audience` sent with the token request,
  defaults to `airflow`.

When `OIDC_TOKEN_URL` and `OIDC_CLIENT_ID` are both set, wraptile mints a
`client_credentials` token (`aud=airflow`) instead of using
`--airflow-username` / `--airflow-password`. The token is cached and refreshed
shortly before it expires.
