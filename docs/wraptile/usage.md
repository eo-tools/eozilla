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

## STAC testing processes

The local testing service includes `create_inline_stac` and `create_linked_stac`.
Both accept `item_count` (default 2, allowed 1–4) and generate equivalent STAC
Items with stable IDs, geometry, temporal metadata, and Assets named `data`
(2×2 Zarr NDVI grid) and `report` (CSV). Every run has a separate generated
directory.

Run from the repository root:

```powershell
pixi run serve
```

The service listens on port 8008 by default and mounts only its testing artifact
directory at `/testing-stac`. Existing service CORS settings allow browser access
from eozilla-app. Other service implementations do not mount this route. Files
are retained for inspection; the directory has no browser listing.

Optional environment settings, configured **before** starting the server:

```powershell
$env:EOZILLA_TESTING_STAC_DIR = "C:/path/to/testing-artifacts"
$env:EOZILLA_TESTING_STAC_URL = "http://localhost:8008/testing-stac"
pixi run serve
```

Defaults are `.pixi/testing-stac` beneath the server working directory and
`http://localhost:8008/testing-stac`. The public URL must identify this server's
mount from the client/browser's perspective; adjust it for another hostname,
port, or reverse-proxy prefix. It cannot contain credentials, queries, or
fragments. Generation uses the development environment's NumPy, xarray, and Zarr,
without requiring PySTAC on the producer.

Submit `POST /processes/create_inline_stac/execution` or
`POST /processes/create_linked_stac/execution` with:

```json
{"inputs": {"item_count": 2}}
```

Inspect `GET /jobs/{jobID}/results` after the job succeeds. Both have five named
outputs: `item`, `item_collection`, `report`, `item_count`, and `optional`.
Inline outputs hold JSON directly; linked metadata outputs have this shape
(the run ID differs per execution):

```json
{
  "item": {"href": "http://localhost:8008/testing-stac/<run-id>/scene-1.json", "type": "application/geo+json"},
  "item_collection": {"href": "http://localhost:8008/testing-stac/<run-id>/items.json", "type": "application/geo+json"},
  "report": {"href": "http://localhost:8008/testing-stac/<run-id>/scene-1/products/summary.csv", "type": "text/csv"},
  "item_count": 2,
  "optional": null
}
```

An Item's `data` Asset has relative href `scene-1/products/data.zarr`, title
`NDVI grid`, media type `application/zarr`, and role `data`. Embedded Items use
their containing ItemCollection base. Scene 1 contains `[[0, 1], [2, 3]]`; Scene 2
contains `[[1, 2], [3, 4]]`. CSV means are 1.5 and 2.5. IDs and Asset keys remain
stable across runs, while locations differ. The ordinary CSV Link, integer, and
explicit null also exercise non-STAC output selection in eozilla-app.

These processes supply raw API values and reachable products for app testing.
They do not add new browser STAC presentation or Python Asset actions. See the
[Cuiman opener guide](../cuiman/guides/openers.md#native-stac-outputs) for opening
these outputs as native PySTAC objects.

When finished, stop the server and remove the generated run directories from
the configured artifact directory. For the default directory, from the repository
root, use `Remove-Item -LiteralPath .pixi/testing-stac -Recurse`. Keep any products
you want to retain before cleaning up.
