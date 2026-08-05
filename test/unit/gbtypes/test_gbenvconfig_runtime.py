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

"""Runtime registration of extra GB environments.

Covers ``load_extra_environment_configs`` and the tolerance it enables in
``gb_environment``/``gb_env_formating``, so a deployment can target a gbserver
instance that is not one of the built-in environments.
"""

import json
import os

import pytest

from gbcommon.types import gbenvconfig
from gbcommon.types.gbenvconfig import (
    GBEnvConfig,
    gb_env_normalize,
    gb_environment,
    gb_environment_config,
    is_registered_environment,
    load_extra_environment_configs,
)


@pytest.fixture(autouse=True)
def _isolate_env_registry(monkeypatch):
    """Give each test a fresh registry and a cleared run-once guard.

    ``_GB_ENVIRONMENT_CONFIGS`` is module-global, so a registered test environment
    would otherwise leak into later tests. Mutate-and-restore rather than rebinding
    the name: other modules import helpers like ``is_registered_environment`` by
    value, and those close over the real dict — a rebind would leave them reading
    the original while the test wrote to a copy.
    """
    original = dict(gbenvconfig._GB_ENVIRONMENT_CONFIGS)
    monkeypatch.setattr(gbenvconfig, "_LOADED_EXTRA_ENVIRONMENT_CONFIGS", False)
    # Any GB_ENV_* left over from the ambient environment would confuse the
    # "no config" cases below.
    for key in list(os.environ):
        if key.startswith("GB_ENV_"):
            monkeypatch.delenv(key, raising=False)
    try:
        yield
    finally:
        gbenvconfig._GB_ENVIRONMENT_CONFIGS.clear()
        gbenvconfig._GB_ENVIRONMENT_CONFIGS.update(original)


class TestNoConfiguration:
    def test_no_env_vars_is_a_noop(self):
        assert load_extra_environment_configs() is None

    def test_builtin_environments_unaffected(self, monkeypatch):
        monkeypatch.setenv("GB_ENVIRONMENT", "PROD")
        config = gb_environment_config()
        assert config.env == "PROD"
        # The built-ins keep a local profile store; that property drives space
        # resolution, so a regression here would be significant.
        assert config.config_spaces == "gb.spaces"
        assert config.config_profile == "gb.spaces.profiles"


class TestInlineRegistration:
    def test_gb_env_name_registers_environment(self, monkeypatch):
        monkeypatch.setenv("GB_ENV_NAME", "ACME")
        monkeypatch.setenv("GB_ENV_LAKEHOUSE_ENVIRONMENT", "STAGING")
        monkeypatch.setenv("GB_ENV_GBSERVER_HOST", "http://acme.example.com:8080")

        config = load_extra_environment_configs()

        assert isinstance(config, GBEnvConfig)
        assert config.env == "ACME"
        assert config.gbserver_host == "http://acme.example.com:8080"
        assert is_registered_environment("ACME")

    def test_maps_all_model_fields_generically(self, monkeypatch):
        """Every GBEnvConfig field is settable as GB_ENV_<FIELD_NAME_UPPER>.

        The mapping iterates ``model_fields`` rather than a hand-maintained list, so
        a field added to the model later is covered without touching the loader.
        """
        monkeypatch.setenv("GB_ENV_NAME", "ACME")
        monkeypatch.setenv("GB_ENV_LAKEHOUSE_ENVIRONMENT", "PROD")
        monkeypatch.setenv("GB_ENV_DEFAULT_SPACE", "acme-space")
        monkeypatch.setenv("GB_ENV_DEFAULT_SQL_SCHEMA", "acme_schema")
        monkeypatch.setenv("GB_ENV_WEB_UI_URL", "http://ui.acme.example.com")
        monkeypatch.setenv("GB_ENV_HF_ORGANIZATION", "acme-org")
        monkeypatch.setenv("GB_ENV_SPACE_CONFIG_BRANCH_NAME", "acme-config")
        monkeypatch.setenv("GB_ENV_PUBLIC_SPACE_GIT_URI", "https://git.example.com/pub")

        config = load_extra_environment_configs()

        assert config.default_space == "acme-space"
        assert config.default_sql_schema == "acme_schema"
        assert config.web_ui_url == "http://ui.acme.example.com"
        assert config.hf_organization == "acme-org"
        assert config.space_config_branch_name == "acme-config"
        assert config.public_space_git_uri == "https://git.example.com/pub"

    def test_unset_fields_default_to_empty(self, monkeypatch):
        """config_spaces/config_profile stay empty — this selects live resolution."""
        monkeypatch.setenv("GB_ENV_NAME", "ACME")
        monkeypatch.setenv("GB_ENV_LAKEHOUSE_ENVIRONMENT", "STAGING")

        config = load_extra_environment_configs()

        assert config.config_spaces == ""
        assert config.config_profile == ""
        assert config.default_space == ""

    def test_feature_flags_from_json(self, monkeypatch):
        monkeypatch.setenv("GB_ENV_NAME", "ACME")
        monkeypatch.setenv("GB_ENV_LAKEHOUSE_ENVIRONMENT", "STAGING")
        monkeypatch.setenv(
            "GB_ENV_FEATURE_FLAGS",
            json.dumps({"gbserver_build_events": True, "other_flag": False}),
        )

        config = load_extra_environment_configs()

        assert config.feature_flags == {
            "gbserver_build_events": True,
            "other_flag": False,
        }

    def test_feature_flags_per_flag_vars(self, monkeypatch):
        monkeypatch.setenv("GB_ENV_NAME", "ACME")
        monkeypatch.setenv("GB_ENV_LAKEHOUSE_ENVIRONMENT", "STAGING")
        monkeypatch.setenv("GB_ENV_FEATURE_FLAG_GBSERVER_BUILD_EVENTS", "true")
        monkeypatch.setenv("GB_ENV_FEATURE_FLAG_SOMETHING_OFF", "false")

        config = load_extra_environment_configs()

        assert config.feature_flags["gbserver_build_events"] is True
        assert config.feature_flags["something_off"] is False

    def test_per_flag_var_overrides_json(self, monkeypatch):
        """Per-flag vars are applied on top of the JSON blob.

        Lets a deployment override one flag without restating the whole object.
        """
        monkeypatch.setenv("GB_ENV_NAME", "ACME")
        monkeypatch.setenv("GB_ENV_LAKEHOUSE_ENVIRONMENT", "STAGING")
        monkeypatch.setenv("GB_ENV_FEATURE_FLAGS", json.dumps({"shared": True}))
        monkeypatch.setenv("GB_ENV_FEATURE_FLAG_SHARED", "false")

        config = load_extra_environment_configs()

        assert config.feature_flags["shared"] is False

    def test_invalid_feature_flags_json_raises(self, monkeypatch):
        """A malformed config must fail loudly, not fall back to a built-in env."""
        monkeypatch.setenv("GB_ENV_NAME", "ACME")
        monkeypatch.setenv("GB_ENV_LAKEHOUSE_ENVIRONMENT", "STAGING")
        monkeypatch.setenv("GB_ENV_FEATURE_FLAGS", "{not json")

        with pytest.raises(ValueError, match="not valid JSON"):
            load_extra_environment_configs()

    def test_runs_only_once(self, monkeypatch):
        monkeypatch.setenv("GB_ENV_NAME", "ACME")
        monkeypatch.setenv("GB_ENV_LAKEHOUSE_ENVIRONMENT", "STAGING")

        assert load_extra_environment_configs() is not None
        assert load_extra_environment_configs() is None


class TestFileRegistration:
    def _write(self, tmp_path, name, text):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_yaml_file(self, monkeypatch, tmp_path):
        path = self._write(
            tmp_path,
            "env.yaml",
            "env: ACMEFILE\n"
            "lakehouse_environment: PROD\n"
            "gbserver_host: http://from-file:9090\n"
            "default_space: file-space\n",
        )
        monkeypatch.setenv("GB_ENV_CONFIG_FILE", str(path))

        config = load_extra_environment_configs()

        assert config.env == "ACMEFILE"
        assert config.gbserver_host == "http://from-file:9090"
        assert config.default_space == "file-space"

    def test_json_file(self, monkeypatch, tmp_path):
        """JSON is a subset of YAML, so safe_load handles both."""
        path = self._write(
            tmp_path,
            "env.json",
            json.dumps(
                {
                    "env": "ACMEJSON",
                    "lakehouse_environment": "STAGING",
                    "gbserver_host": "http://json-host:1234",
                }
            ),
        )
        monkeypatch.setenv("GB_ENV_CONFIG_FILE", str(path))

        config = load_extra_environment_configs()

        assert config.env == "ACMEJSON"
        assert config.gbserver_host == "http://json-host:1234"

    def test_file_takes_precedence_over_inline(self, monkeypatch, tmp_path):
        path = self._write(
            tmp_path,
            "env.yaml",
            "env: FROMFILE\nlakehouse_environment: PROD\n",
        )
        monkeypatch.setenv("GB_ENV_CONFIG_FILE", str(path))
        monkeypatch.setenv("GB_ENV_NAME", "FROMINLINE")
        monkeypatch.setenv("GB_ENV_LAKEHOUSE_ENVIRONMENT", "STAGING")

        config = load_extra_environment_configs()

        assert config.env == "FROMFILE"

    def test_missing_file_raises(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GB_ENV_CONFIG_FILE", str(tmp_path / "nope.yaml"))

        with pytest.raises(ValueError, match="not a file"):
            load_extra_environment_configs()

    def test_non_mapping_file_raises(self, monkeypatch, tmp_path):
        path = self._write(tmp_path, "env.yaml", "- just\n- a\n- list\n")
        monkeypatch.setenv("GB_ENV_CONFIG_FILE", str(path))

        with pytest.raises(ValueError, match="must contain a mapping"):
            load_extra_environment_configs()


class TestEnvironmentNameTolerance:
    def test_registered_custom_name_resolves(self, monkeypatch):
        monkeypatch.setenv("GB_ENV_NAME", "ACME")
        monkeypatch.setenv("GB_ENV_LAKEHOUSE_ENVIRONMENT", "STAGING")
        monkeypatch.setenv("GB_ENVIRONMENT", "ACME")

        assert gb_environment() == "ACME"
        assert gb_environment_config().env == "ACME"

    def test_gb_environment_config_loads_lazily(self, monkeypatch):
        """A custom GB_ENVIRONMENT resolves even without an explicit loader call."""
        monkeypatch.setenv("GB_ENV_NAME", "LAZY")
        monkeypatch.setenv("GB_ENV_LAKEHOUSE_ENVIRONMENT", "STAGING")
        monkeypatch.setenv("GB_ENV_GBSERVER_HOST", "http://lazy:8080")
        monkeypatch.setenv("GB_ENVIRONMENT", "LAZY")

        assert gb_environment_config().gbserver_host == "http://lazy:8080"

    def test_unregistered_name_still_raises(self, monkeypatch):
        monkeypatch.setenv("GB_ENVIRONMENT", "TYPOO")

        with pytest.raises(ValueError, match="invalid value 'TYPOO'"):
            gb_environment()

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("prod", "PROD"),
            ("production", "PROD"),
            ("staging", "STAGING"),
            ("dev", "DEV"),
            ("development", "DEV"),
            ("standalone", "STANDALONE"),
            ("local", "STANDALONE"),
        ],
    )
    def test_builtin_aliases_still_normalize(self, monkeypatch, raw, expected):
        monkeypatch.setenv("GB_ENVIRONMENT", raw)
        assert gb_environment() == expected

    def test_normalize_itself_unchanged(self):
        """gb_env_normalize keeps rejecting unknown names — tolerance lives above it."""
        assert gb_env_normalize("prod") == "PROD"
        assert gb_env_normalize(None) is None
        with pytest.raises(ValueError):
            gb_env_normalize("ACME")


class TestGbcliFormattingTolerance:
    """``gb_env_formating`` sys.exit()s on invalid names, which would kill a server.

    A registered custom name must bypass that path; a genuine typo must not.
    """

    def test_registered_name_returned(self, monkeypatch):
        from gbcli.utils.gbconstants import gb_env_formating

        monkeypatch.setenv("GB_ENV_NAME", "ACME")
        monkeypatch.setenv("GB_ENV_LAKEHOUSE_ENVIRONMENT", "STAGING")
        # Importing gbconstants evaluates module-level constants that call
        # gb_environment_config(), which consumes the run-once loader guard. Reset it
        # here so the loader observes the GB_ENV_* values set just above.
        monkeypatch.setattr(gbenvconfig, "_LOADED_EXTRA_ENVIRONMENT_CONFIGS", False)
        load_extra_environment_configs()

        assert gb_env_formating("ACME", "test input") == "ACME"

    def test_invalid_name_still_exits(self):
        from gbcli.utils.gbconstants import gb_env_formating

        with pytest.raises(SystemExit):
            gb_env_formating("TYPOO", "test input")


class TestLocalProfileStoreProperty:
    """The property that replaced ``is_standalone()`` for profile-store decisions."""

    @pytest.mark.parametrize(
        "env,expected",
        [("PROD", True), ("STAGING", True), ("DEV", True), ("STANDALONE", False)],
    )
    def test_builtin_environments(self, monkeypatch, env, expected):
        from gbcli.utils.spaceutil import has_local_profile_store

        monkeypatch.setenv("GB_ENVIRONMENT", env)
        assert has_local_profile_store() is expected

    def test_runtime_registered_env_has_no_store(self, monkeypatch):
        from gbcli.utils.spaceutil import has_local_profile_store

        monkeypatch.setenv("GB_ENV_NAME", "ACME")
        monkeypatch.setenv("GB_ENV_LAKEHOUSE_ENVIRONMENT", "STAGING")
        monkeypatch.setenv("GB_ENVIRONMENT", "ACME")
        load_extra_environment_configs()

        assert has_local_profile_store() is False
