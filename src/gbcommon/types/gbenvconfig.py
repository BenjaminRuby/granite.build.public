#!/usr/bin/env python3

# Copyright LLM.build Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unified environment configuration for GB (gbcli + gbserver)."""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Self

import yaml
from pydantic import BaseModel

from gbcommon.types.constants import DEFAULT_GH_DOMAIN

logger = logging.getLogger(__name__)

# The single source of truth for what counts as "false"/"true" when parsing a
# boolean from an environment-variable string. Anything set but not falsy is
# treated as true; the truthy set is used only to warn on unrecognized input.
_FALSY_TOKENS = frozenset({"false", "null", "undefined", "no", "off", "0", ""})
_TRUTHY_TOKENS = frozenset({"true", "yes", "on", "1"})


def parse_boolean(value: str | None, default: bool = False) -> bool:
    """Parse an env-var-style string into a boolean.

    ``None`` (unset) → ``default``. Otherwise the value is lower-cased and
    compared against the falsy token set (see ``_FALSY_TOKENS``); a match is
    ``False``, anything else set is ``True``. A non-falsy value that also isn't a
    recognized truthy token (a likely typo, e.g. ``on-prod``) is still treated as
    ``True`` but logs a warning. This never raises — the single place the
    string→bool rule is defined, shared by ``getenv_boolean`` and any other
    caller that already has the string in hand.
    """
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in _FALSY_TOKENS:
        return False
    if normalized not in _TRUTHY_TOKENS:
        logger.warning(
            "Unrecognized boolean value %r — treating as true; " "use one of %s / %s",
            value,
            sorted(_TRUTHY_TOKENS),
            sorted(_FALSY_TOKENS),
        )
    return True


def getenv_boolean(envname: str, default: bool = False) -> bool:
    """Evaluate the environment variable and return as a boolean value."""
    return parse_boolean(os.getenv(envname), default)


class GBEnvConfig(BaseModel):
    """Unified environment configuration for gbcli and gbserver."""

    env: str
    """The GB env name. One of PROD, STAGING, DEV, or STANDALONE."""

    lakehouse_environment: str
    """The lakehouse environment to use. One of PROD or STAGING."""

    feature_flags: Dict[str, bool] = {}
    """Feature flags for this environment."""

    space_config_branch_name: str = ""
    """The branch in a space repo holding steps, assetstores, etc."""

    # --- gbcli-origin fields ---

    gbserver_host: str = ""
    """The gbserver API endpoint URL."""

    default_space: str = ""
    """The default space name."""

    web_ui_url: str = ""
    """The full web UI base URL."""

    config_spaces: str = ""
    """Config section name for spaces."""

    config_profile: str = ""
    """Config section name for profiles."""

    server_log_application_name: str = ""
    """Application name for logging."""

    branch_assets: str = ""
    """Git branch name for assets."""

    hf_organization: str = ""
    """HuggingFace organization."""

    # --- gbserver-origin fields ---

    dashboard_instance: str = ""
    """The dashboard URL for build status."""

    public_space_git_uri: str = ""
    """The URI of the public space git repo."""

    public_space_lh_subnamespace: str = ""
    """The child name of the Lakehouse namespace under the main GB namespace."""

    buildwatcher_deployment_yaml: str = ""
    """The location of the buildwatcher's deployment yaml."""

    default_pod_namespace: str = ""
    """The default K8s namespace for servers."""

    default_sql_schema: str = ""
    """The default schema to use in SQL storage."""

    def model_post_init(self: Self, context: Any, /) -> None:
        if self.env == "":
            raise ValueError("field env cannot be empty")


DEFAULT_GB_ENVIRONMENT = "PROD"

_GB_ENVIRONMENT_CONFIGS: Dict[str, GBEnvConfig] = {
    "PROD": GBEnvConfig(
        env="PROD",
        lakehouse_environment="PROD",
        space_config_branch_name="gbspace-config",
        # gbcli
        gbserver_host="https://api.llm-build-prod.vpc-int.res.ibm.com",
        default_space="public",
        web_ui_url="https://dashboard.llm-build-prod.vpc-int.res.ibm.com",
        config_spaces="gb.spaces",
        config_profile="gb.spaces.profiles",
        server_log_application_name="llm-build-prod",
        branch_assets="gbspace-config",
        hf_organization="ibm-research",
        feature_flags={
            "gbserver_build_events": getenv_boolean("GBSERVER_BUILD_EVENTS", True),
            "gbserver_artifact_filter": getenv_boolean(
                "GBSERVER_ARTIFACT_FILTER", True
            ),
            "gbserver_build_update": getenv_boolean("GBSERVER_BUILD_UPDATE", True),
        },
        # gbserver
        dashboard_instance="https://api.llm-build-dev.vpc-int.res.ibm.com",
        public_space_git_uri=f"https://{DEFAULT_GH_DOMAIN}/granite-dot-build/gbspace-public",
        public_space_lh_subnamespace="public",
        buildwatcher_deployment_yaml="k8s/dep-build-runner.yaml",
        default_pod_namespace=os.getenv(
            "GBSERVER_BACKEND_SERVER_NAMESPACE_PROD", "llm-build-prod"
        ),
        default_sql_schema="granite_dot_build_prod",
    ),
    "STAGING": GBEnvConfig(
        env="STAGING",
        lakehouse_environment="STAGING",
        space_config_branch_name="gbspace-config",
        # gbcli
        gbserver_host="https://api.llm-build-staging.vpc-int.res.ibm.com",
        default_space="public",
        web_ui_url="https://dashboard.llm-build-staging.vpc-int.res.ibm.com",
        config_spaces="staging.gb.spaces",
        config_profile="staging.gb.spaces.profiles",
        server_log_application_name="llm-build-staging",
        branch_assets="gbspace-config-dev",
        hf_organization="ibm-research",
        feature_flags={
            "gbserver_build_events": getenv_boolean("GBSERVER_BUILD_EVENTS", True),
            "gbserver_artifact_filter": getenv_boolean(
                "GBSERVER_ARTIFACT_FILTER", True
            ),
            "gbserver_build_update": getenv_boolean("GBSERVER_BUILD_UPDATE", True),
        },
        # gbserver
        dashboard_instance="https://api.llm-build-dev.vpc-int.res.ibm.com",
        public_space_git_uri=f"https://{DEFAULT_GH_DOMAIN}/granite-dot-build/gb-test",
        public_space_lh_subnamespace="public",
        buildwatcher_deployment_yaml="k8s/dep-build-runner.yaml",
        default_pod_namespace=os.getenv(
            "GBSERVER_BACKEND_SERVER_NAMESPACE_STAGING", "llm-build-staging"
        ),
        default_sql_schema="granite_dot_build_staging",
    ),
    "DEV": GBEnvConfig(
        env="DEV",
        lakehouse_environment="STAGING",
        space_config_branch_name="gbspace-config",
        # gbcli
        gbserver_host="https://api.llm-build-dev.vpc-int.res.ibm.com",
        default_space="public",
        web_ui_url="https://dashboard.llm-build-dev.vpc-int.res.ibm.com",
        config_spaces="dev.gb.spaces",
        config_profile="dev.gb.spaces.profiles",
        server_log_application_name="llm-build-dev",
        branch_assets="gbspace-config-dev",
        hf_organization="ibm-research",
        feature_flags={
            "gbserver_build_events": getenv_boolean("GBSERVER_BUILD_EVENTS", True),
            "gbserver_artifact_filter": getenv_boolean(
                "GBSERVER_ARTIFACT_FILTER", True
            ),
            "gbserver_build_update": getenv_boolean("GBSERVER_BUILD_UPDATE", True),
        },
        # gbserver
        dashboard_instance="https://api.llm-build-dev.vpc-int.res.ibm.com",
        public_space_git_uri=f"https://{DEFAULT_GH_DOMAIN}/granite-dot-build/gbspace-public-dev",
        public_space_lh_subnamespace="public_dev",
        buildwatcher_deployment_yaml="k8s/dep-build-runner.yaml",
        default_pod_namespace=os.getenv(
            "GBSERVER_BACKEND_SERVER_NAMESPACE_DEV", "llm-build-dev"
        ),
        default_sql_schema="granite_dot_build_dev",
    ),
    "STANDALONE": GBEnvConfig(
        env="STANDALONE",
        lakehouse_environment="",
        space_config_branch_name="main",
        # gbcli
        gbserver_host="http://localhost:8080",
        default_space="standalone",
        web_ui_url="http://localhost:8080/dashboard",
        config_spaces="",
        config_profile="",
        server_log_application_name="gbserver-standalone",
        branch_assets="",
        hf_organization="ibm-research",
        feature_flags={
            "build_start_via_github": False,
            "gbserver_build_events": True,
            "gbserver_artifact_filter": False,
            "gbserver_build_update": True,
        },
        # gbserver
        dashboard_instance="",
        public_space_git_uri="",
        public_space_lh_subnamespace="",
        buildwatcher_deployment_yaml="",
        default_pod_namespace="default",
        default_sql_schema="standalone",
    ),
}


def gb_env_normalize(value: Optional[str], source: str = "input") -> Optional[str]:
    """Normalize user-facing env name to canonical form.

    Returns None if value is None/empty. Raises ValueError on invalid input.
    """
    if not value:
        return None
    v = value.lower()
    if v in ("prod", "production"):
        return "PROD"
    elif v in ("staging",):
        return "STAGING"
    elif v in ("dev", "development"):
        return "DEV"
    elif v in ("standalone", "local"):
        return "STANDALONE"
    else:
        raise ValueError(f"Error: {source} has invalid value '{value}'")


def is_registered_environment(value: Optional[str]) -> bool:
    """Return True if value names an environment present in the config table.

    Used to let a runtime-registered environment name (see
    ``load_extra_environment_configs``) bypass ``gb_env_normalize``, which only
    knows the built-in names and their aliases.
    """
    return bool(value) and value in _GB_ENVIRONMENT_CONFIGS


def gb_environment() -> str:
    """Read GB_ENVIRONMENT env var, normalize, default to PROD.

    A name registered at runtime is returned as-is; anything else goes through
    ``gb_env_normalize``, so aliases still resolve and typos still raise. The
    loader runs first so this works regardless of which entry point a caller
    reaches initially.
    """
    load_extra_environment_configs()
    raw = os.environ.get("GB_ENVIRONMENT")
    if is_registered_environment(raw):
        return raw
    normalized = gb_env_normalize(raw, "Environment variable GB_ENVIRONMENT")
    return normalized if normalized else DEFAULT_GB_ENVIRONMENT


def gb_environment_config(gb_env: Optional[str] = None) -> GBEnvConfig:
    """Get the config for the given env. If gb_env is None or empty, uses gb_environment().

    Loads any runtime-registered environment first, so a custom GB_ENVIRONMENT
    resolves even if this is the first call in the process.
    """
    load_extra_environment_configs()
    if not gb_env:
        gb_env = gb_environment()
    if gb_env not in _GB_ENVIRONMENT_CONFIGS:
        valid_keys = list(_GB_ENVIRONMENT_CONFIGS.keys())
        raise ValueError(
            f"unknown GB environment: {gb_env}, expected one of {valid_keys}"
        )
    return _GB_ENVIRONMENT_CONFIGS[gb_env]


def is_standalone() -> bool:
    """Return True if the current environment is STANDALONE."""
    return gb_environment() == "STANDALONE"


def add_environment_config(config_dict: Dict) -> GBEnvConfig:
    """Add or overwrite a runtime config entry. Used by gbserver for --server-runtime-config."""
    config = GBEnvConfig.model_validate(config_dict)
    if config.env in _GB_ENVIRONMENT_CONFIGS:
        old = _GB_ENVIRONMENT_CONFIGS[config.env]
        print(
            f"[WARNING] the environment config '{config.env}'"
            + f" already exists: {old} , overwriting with {config}"
        )
    _GB_ENVIRONMENT_CONFIGS[config.env] = config
    return config


# --- runtime environment registration (for externally deployed gbserver instances) ---

_LOADED_EXTRA_ENVIRONMENT_CONFIGS = False

GB_ENV_CONFIG_FILE_VAR = "GB_ENV_CONFIG_FILE"
GB_ENV_VAR_PREFIX = "GB_ENV_"
GB_ENV_NAME_VAR = "GB_ENV_NAME"
GB_ENV_FEATURE_FLAGS_VAR = "GB_ENV_FEATURE_FLAGS"
GB_ENV_FEATURE_FLAG_PREFIX = "GB_ENV_FEATURE_FLAG_"


def _load_env_config_from_file(path_str: str) -> Dict:
    """Read an environment config dict from a YAML or JSON file."""
    path = Path(path_str)
    if not path.is_file():
        raise ValueError(
            f"{GB_ENV_CONFIG_FILE_VAR} points at '{path}', which is not a file"
        )
    with open(path, "r", encoding="utf-8") as f:
        # safe_load parses JSON too, since JSON is a subset of YAML.
        config_dict = yaml.safe_load(f)
    if not isinstance(config_dict, dict):
        raise ValueError(
            f"{GB_ENV_CONFIG_FILE_VAR} '{path}' must contain a mapping,"
            f" got {type(config_dict).__name__}"
        )
    return config_dict


def _collect_feature_flags() -> Optional[Dict[str, bool]]:
    """Build feature_flags from GB_ENV_FEATURE_FLAGS (JSON) and/or per-flag vars.

    Per-flag ``GB_ENV_FEATURE_FLAG_<NAME>`` entries are applied on top of the JSON
    blob, so a single flag can be overridden without restating the whole object.
    Returns None when neither form is present, so the caller can leave the field
    at its default rather than clobbering it with an empty dict.
    """
    flags: Dict[str, bool] = {}
    found = False

    raw_json = os.environ.get(GB_ENV_FEATURE_FLAGS_VAR)
    if raw_json:
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"{GB_ENV_FEATURE_FLAGS_VAR} is not valid JSON: {e}"
            ) from e
        if not isinstance(parsed, dict):
            raise ValueError(
                f"{GB_ENV_FEATURE_FLAGS_VAR} must be a JSON object,"
                f" got {type(parsed).__name__}"
            )
        # Reuse parse_boolean so "true"/1/True all behave the same as elsewhere.
        flags.update({k: parse_boolean(str(v)) for k, v in parsed.items()})
        found = True

    for key, value in os.environ.items():
        if (
            key.startswith(GB_ENV_FEATURE_FLAG_PREFIX)
            and key != GB_ENV_FEATURE_FLAGS_VAR
        ):
            flag_name = key[len(GB_ENV_FEATURE_FLAG_PREFIX) :].lower()
            if flag_name:
                flags[flag_name] = parse_boolean(value)
                found = True

    return flags if found else None


def _collect_inline_env_config() -> Optional[Dict]:
    """Build an environment config dict from inline GB_ENV_* variables.

    Maps generically over ``GBEnvConfig.model_fields`` — every field is settable as
    ``GB_ENV_<FIELD_NAME_UPPER>`` — so fields added to the model later are picked up
    without touching this function. Returns None when GB_ENV_NAME is unset.
    """
    env_name = os.environ.get(GB_ENV_NAME_VAR)
    if not env_name:
        return None

    config_dict: Dict[str, Any] = {"env": env_name}
    for field_name in GBEnvConfig.model_fields:
        if field_name in ("env", "feature_flags"):
            continue  # env is set above; feature_flags is not a plain string
        value = os.environ.get(f"{GB_ENV_VAR_PREFIX}{field_name.upper()}")
        if value is not None:
            config_dict[field_name] = value

    feature_flags = _collect_feature_flags()
    if feature_flags is not None:
        config_dict["feature_flags"] = feature_flags

    return config_dict


def _log_resolved_config(config: GBEnvConfig, source: str) -> None:
    """Log what was registered, and which fields fell back to empty.

    Unset fields are legitimate — notably config_spaces/config_profile, whose
    emptiness is what selects live space resolution instead of a local profile
    store. Logging them means an operator can see what they did not set rather
    than debugging an empty string much later.
    """
    empty_fields = sorted(
        name
        for name in GBEnvConfig.model_fields
        if getattr(config, name, None) in ("", {}, None)
    )
    logger.info(
        "Registered GB environment '%s' from %s (gbserver_host=%r,"
        " lakehouse_environment=%r)",
        config.env,
        source,
        config.gbserver_host,
        config.lakehouse_environment,
    )
    if empty_fields:
        logger.info(
            "GB environment '%s': fields left empty: %s."
            " Empty config_spaces/config_profile is intentional for a stateless"
            " deployment — it selects live space resolution over a local profile store.",
            config.env,
            ", ".join(empty_fields),
        )


def load_extra_environment_configs() -> Optional[GBEnvConfig]:
    """Register an extra GB environment from the process environment.

    Lets a deployment target a gbserver instance that is not one of the built-in
    environments, without a code change. Env-only (no argparse) so it works for
    any process — servers, CLIs, tests.

    Sources, in precedence order:
      1. ``GB_ENV_CONFIG_FILE=/path/to/config.(yaml|json)`` — a full config mapping.
      2. Inline ``GB_ENV_*`` variables, triggered by ``GB_ENV_NAME``.

    Runs at most once per process; later calls are no-ops returning None. Returns
    None when neither source is configured. Raises ValueError on a malformed
    config — a deployment misconfiguration should fail loudly at startup rather
    than silently fall back to a built-in environment.

    Callers that read module-level constants derived from the env config must call
    this **before** those modules are imported.
    """
    global _LOADED_EXTRA_ENVIRONMENT_CONFIGS
    if _LOADED_EXTRA_ENVIRONMENT_CONFIGS:
        return None
    _LOADED_EXTRA_ENVIRONMENT_CONFIGS = True

    config_file = os.environ.get(GB_ENV_CONFIG_FILE_VAR)
    if config_file:
        config_dict = _load_env_config_from_file(config_file)
        source = f"{GB_ENV_CONFIG_FILE_VAR}={config_file}"
    else:
        config_dict = _collect_inline_env_config()
        source = f"inline {GB_ENV_VAR_PREFIX}* variables"
        if config_dict is None:
            return None

    config = add_environment_config(config_dict=config_dict)
    _log_resolved_config(config, source)
    return config
