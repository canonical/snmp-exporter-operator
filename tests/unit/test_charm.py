import json
from unittest import mock

import yaml
from ops.testing import Relation, State


def test_status_no_config(ctx):
    state = State(config={"targets": ""})
    state_out = ctx.run(ctx.on.config_changed(), state=state)
    assert state_out.unit_status.name == "blocked"


def test_status_with_targets(ctx):
    state = State(config={"targets": "1.2.3.4"})
    state_out = ctx.run(ctx.on.config_changed(), state=state)
    assert state_out.unit_status.name == "active"


def test_status_with_config_file(ctx):
    """Test that valid config_file and custom_module result in active status."""
    config_dict = {
        "auths": {"public_v2": {"community": "public", "version": 2}},
        "modules": {"my_module": {"walk": ["1.3.6.1.2.1.1"]}},
    }
    valid_yaml = yaml.dump(config_dict)

    state = State(
        config={
            "targets": "1.2.3.4",
            "config_file": valid_yaml,
            "custom_module": "my_module",
        }
    )
    state_out = ctx.run(ctx.on.config_changed(), state=state)
    assert state_out.unit_status.name == "active"


def test_status_with_config_file_no_module(ctx):
    """Test that having config_file without custom_module results in blocked status."""
    config_dict = {
        "auths": {"public_v2": {"community": "public", "version": 2}},
        "modules": {"my_module": {"walk": ["1.3.6.1.2.1.1"]}},
    }
    valid_yaml = yaml.dump(config_dict)

    state = State(
        config={
            "targets": "1.2.3.4",
            "config_file": valid_yaml,
            "custom_module": "",
        }
    )
    state_out = ctx.run(ctx.on.config_changed(), state=state)
    assert state_out.unit_status.name == "blocked"
    assert (
        "Both config_file and custom_module must be set together"
        in state_out.unit_status.message
    )


def test_invalid_config_file(ctx):
    """Test that invalid config_file (like filename string) results in blocked status."""
    # Test with a filename string instead of YAML content
    state = State(
        config={
            "targets": "1.2.3.4",
            "config_file": "snmp.yaml",  # This is a filename, not YAML content
            "custom_module": "my_module",
        }
    )
    state_out = ctx.run(ctx.on.config_changed(), state=state)
    assert state_out.unit_status.name == "blocked"
    assert "Use juju config" in state_out.unit_status.message
    assert "config_file=@FILENAME" in state_out.unit_status.message


def test_scrape_job_with_config(ctx):
    """Test that scrape job is properly configured when config_file is provided."""
    config_dict = {
        "auths": {"public_v2": {"community": "public", "version": 2}},
        "modules": {"my_custom_module": {"walk": ["1.3.6.1.2.1.1"]}},
    }
    valid_yaml = yaml.dump(config_dict)

    # Mock file operations to prevent actual file writing
    with mock.patch("builtins.open", mock.mock_open()), mock.patch(
        "yaml.dump"
    ):
        # Create a relation to get the scrape job configuration
        cos_agent_relation = Relation(
            "cos-agent", remote_app_name="grafana-agent"
        )
        state = State(
            relations=[cos_agent_relation],
            config={
                "targets": "1.2.3.4,1.2.3.5",
                "config_file": valid_yaml,
                "custom_module": "my_custom_module",
            },
        )

        # First trigger config_changed to set the status
        state_out = ctx.run(ctx.on.config_changed(), state=state)

        # Verify the charm is active
        assert state_out.unit_status.name == "active"

        # Then trigger relation_changed to get the scrape job data
        # Use the relation from the updated state
        updated_relation = next(iter(state_out.relations))
        state_out = ctx.run(
            ctx.on.relation_changed(updated_relation), state=state_out
        )

        # Check the scrape job configuration from relation data
        relation_data = json.loads(
            next(iter(state_out.relations)).local_unit_data["config"]
        )
        scrape_jobs = relation_data["metrics_scrape_jobs"]

        # Find the SNMP scrape job
        snmp_job = next(
            job for job in scrape_jobs if job["job_name"].endswith("snmp")
        )

        # Verify targets are still defined
        assert snmp_job["static_configs"][0]["targets"] == [
            "1.2.3.4",
            "1.2.3.5",
        ]

        # Verify no auth parameter (should be handled by config file)
        assert "auth" not in snmp_job["params"]

        # Verify custom module is used
        assert snmp_job["params"]["module"] == ["my_custom_module"]


def test_cos_agent_relation_data_is_set(ctx):
    cos_agent_relation = Relation("cos-agent", remote_app_name="grafana-agent")
    state = State(relations=[cos_agent_relation], config={"targets": "1.2.3.4"})
    state_out = ctx.run(ctx.on.relation_changed(cos_agent_relation), state=state)

    relation_data = json.loads(next(iter(state_out.relations)).local_unit_data["config"])
    assert len(relation_data["metrics_scrape_jobs"]) == 2
