# Deployment environments (`GB_ENVIRONMENT`)

> **Audience:** operators choosing which deployment a gbserver process targets. For the env-var list see
> [environment-variables.md](environment-variables.md).

`GB_ENVIRONMENT` selects a **per-environment config** that supplies defaults for the cluster,
namespace, SQL schema, and space git branches. The four built-in values are `DEV`, `STAGING`,
`PROD`, and `STANDALONE`; the config objects live in
[`src/gbcommon/types/gbenvconfig.py`](../../src/gbcommon/types/gbenvconfig.py) (default: `PROD`). These
are defaults — individual environment variables still override them. You can also
[register an additional environment at runtime](#runtime-registered-environments) to target a gbserver
deployment that is not one of the built-ins.

| Aspect | `PROD` | `STAGING` | `DEV` | `STANDALONE` |
|--------|--------|-----------|-------|--------------|
| K8s namespace | `llm-build-prod` | `llm-build-staging` | `llm-build-dev` | default |
| SQL schema | `granite_dot_build_prod` | `granite_dot_build_staging` | `granite_dot_build_dev` | `standalone` |
| Space-config branch | `gbspace-config` | `gbspace-config` | `gbspace-config` | `main` |

You can define or override an environment's defaults with a
[`--server-runtime-config`](config-files.md#server-runtime-config---server-runtime-config) YAML file.

## Standalone mode

`GB_ENVIRONMENT=STANDALONE` (which `gbserver standalone` sets for you) is the local/offline profile: no
Kubernetes or IBM services required. On startup `check_and_init_for_standalone()`
([`src/gbserver/commands/utils.py`](../../src/gbserver/commands/utils.py)) applies these defaults **only
where you haven't set them** (`STANDALONE_ENV_DEFAULTS` in
[`constants.py`](../../src/gbserver/types/constants.py)):

| Variable | Standalone default | Effect |
|----------|--------------------|--------|
| `GBSERVER_METADATA_STORAGE` | `sqlite` | Local SQLite instead of PostgreSQL. |
| `GBSERVER_DEFAULT_BUILDRUNNER_TYPE` | `thread` | Run builds in-process instead of as k8s jobs. |
| `GBSERVER_AUTH_MODE` | `apikey` | Simple shared-key auth (localhost allowed unauthenticated). |
| `GBSERVER_EVENT_PUBLISHING_ENABLED` | `true` | Publish build events (embedded NATS). |
| `GBSERVER_PROCEED_WITHOUT_SECRETS` | `true` | Don't require a remote secret manager. |

The defaults are applied with `os.environ.setdefault(...)`, i.e. **only where you haven't already set
them**, so any variable you export before starting the server wins (e.g. export `GBSERVER_METADATA_STORAGE=sql`
to use PostgreSQL even in standalone). Two settings are resolved dynamically rather than written to the
environment: the per-user secret backend defaults to `local`, and the lineage provider defaults to `none`.

Beyond applying those defaults, `check_and_init_for_standalone()` performs the rest of the one-time
standalone setup: it reloads the `constants` module so import-time values pick up the defaults, installs
the **SQLite** storage factory (migrating any legacy database first), installs the standalone **space
access manager** (which bypasses remote authorization), and — for the standalone *server* — registers
the `--space-dir` space under `public` (and the legacy aliases `standalone` / `local`). Outside standalone
the function is a no-op.

## Runtime-registered environments

To point the client at a gbserver deployment that is not one of the four built-ins — an external or
customer-hosted instance — register an environment from the process environment. No code change and no
fork required. Registration happens in
[`load_extra_environment_configs()`](../../src/gbcommon/types/gbenvconfig.py).

**Registering an environment also selects it**, so the common case sets one variable, not two:

```bash
export GB_ENV_CONFIG_NAME=ACME
export GB_ENV_GBSERVER_HOST=https://gbserver.acme.example.com
gb space list --all          # runs against ACME
```

Or keep the whole config in a file (YAML or JSON — JSON is a subset of YAML, so one parser reads both):

```bash
export GB_ENV_CONFIG_FILE=/etc/gb/acme.yaml   # the file's `env:` key names the environment
gb space list --all
```

| Variable | Purpose |
|----------|---------|
| `GB_ENV_CONFIG_NAME` | Names the environment being defined, and triggers inline registration. |
| `GB_ENV_CONFIG_FILE` | Path to a YAML/JSON mapping holding the whole config. Takes precedence over the inline variables. |
| `GB_ENV_<FIELD>` | Sets any single `GBEnvConfig` field, e.g. `GB_ENV_GBSERVER_HOST`, `GB_ENV_DEFAULT_SPACE`, `GB_ENV_WEB_UI_URL`. The mapping is generated from the model, so every field is settable. |
| `GB_ENV_FEATURE_FLAGS` | All feature flags at once, as a JSON object: `{"gbserver_build_events": true}`. |
| `GB_ENV_FEATURE_FLAG_<NAME>` | One flag, applied on top of the JSON above — override a single flag without restating the object. |

`GB_ENVIRONMENT` still wins if you set it, so it remains available as an override; when it names a
different environment than the one registered, that divergence is logged as a warning rather than
silently changing which backend you reach. Unset it to use the registered environment.

Fields you don't set stay empty, which is meaningful for two of them: an environment with empty
`config_spaces`/`config_profile` has no spaces section in `~/.gbcli/config`, so spaces are always
resolved live from gbserver instead of from a local profile cache (the same way `STANDALONE` behaves).
`gb space list --refresh` is rejected for such an environment, because the cache it would repopulate is
never read. A malformed config — an unreadable `GB_ENV_CONFIG_FILE`, a file that isn't a mapping, or
invalid feature-flag JSON — fails at startup rather than falling back to a built-in environment.

## See also

- [Configuration overview](README.md) · [Environment variables](environment-variables.md) · [Config files](config-files.md)
- [`gbserver` CLI reference](../cli/gbserver-cli-reference.md) — the `standalone` command
