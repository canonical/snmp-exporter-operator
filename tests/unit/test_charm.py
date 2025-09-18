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
    """Test that valid config_file and scrape_config_file result in active status."""
    config_dict = {
        "auths": {"public_v2": {"community": "public", "version": 2}},
        "modules": {"my_module": {"walk": ["1.3.6.1.2.1.1"]}},
    }
    config_yaml = yaml.dump(config_dict)

    scrape_config_dict = {
        "scrape_configs": [
            {
                "job_name": "snmp",
                "static_configs": [{"targets": ["1.2.3.4"]}],
                "metrics_path": "/snmp",
                "params": {"auth": ["public_v2"], "module": ["my_module"]},
                "relabel_configs": [
                    {
                        "source_labels": ["__address__"],
                        "target_label": "__param_target",
                    },
                    {
                        "source_labels": ["__param_target"],
                        "target_label": "instance",
                    },
                    {
                        "target_label": "__address__",
                        "replacement": "localhost:9116",
                    },
                ],
            }
        ]
    }
    scrape_config_yaml = yaml.dump(scrape_config_dict)

    # Mock file operations to prevent actual file writing
    with mock.patch("builtins.open", mock.mock_open()), mock.patch("yaml.dump"), mock.patch(
        "os.makedirs"
    ), mock.patch("charms.operator_libs_linux.v2.snap.Snap.restart"):
        state = State(
            config={
                "targets": "",
                "config_file": config_yaml,
                "scrape_config_file": scrape_config_yaml,
            }
        )
        state_out = ctx.run(ctx.on.config_changed(), state=state)
        assert state_out.unit_status.name == "active"


def test_status_with_config_file_no_scrape_config(ctx):
    """Test that having config_file without scrape_config_file results in blocked status."""
    config_dict = {
        "auths": {"public_v2": {"community": "public", "version": 2}},
        "modules": {"my_module": {"walk": ["1.3.6.1.2.1.1"]}},
    }
    config_yaml = yaml.dump(config_dict)

    state = State(
        config={
            "targets": "",
            "config_file": config_yaml,
            "scrape_config_file": "",
        }
    )
    state_out = ctx.run(ctx.on.config_changed(), state=state)
    assert state_out.unit_status.name == "blocked"


def test_invalid_config_file(ctx):
    """Test that invalid config_file (like filename string) results in blocked status."""
    # Test with a filename string instead of YAML content
    state = State(
        config={
            "targets": "",
            "config_file": "snmp.yaml",  # This is a filename, not YAML content
            "scrape_config_file": "scrape_config.yaml",  # This is a filename, not YAML content
        }
    )
    state_out = ctx.run(ctx.on.config_changed(), state=state)
    assert state_out.unit_status.name == "blocked"


def test_conflicting_config(ctx):
    """Test that setting both targets and config files results in blocked status."""
    config_dict = {
        "auths": {"public_v2": {"community": "public", "version": 2}},
        "modules": {"my_module": {"walk": ["1.3.6.1.2.1.1"]}},
    }
    config_yaml = yaml.dump(config_dict)

    scrape_config_dict = {
        "scrape_configs": [
            {
                "job_name": "snmp",
                "static_configs": [{"targets": ["1.2.3.4"]}],
                "metrics_path": "/snmp",
                "params": {"auth": ["public_v2"], "module": ["my_module"]},
            }
        ]
    }
    scrape_config_yaml = yaml.dump(scrape_config_dict)

    state = State(
        config={
            "targets": "1.2.3.4",  # Setting targets
            "config_file": config_yaml,  # And config files - this should conflict
            "scrape_config_file": scrape_config_yaml,
        }
    )
    state_out = ctx.run(ctx.on.config_changed(), state=state)
    assert state_out.unit_status.name == "blocked"


def test_scrape_job_with_config(ctx):
    """Test that scrape job is properly configured when config_file is provided."""
    config_dict = {
        "auths": {"public_v2": {"community": "public", "version": 2}},
        "modules": {"my_custom_module": {"walk": ["1.3.6.1.2.1.1"]}},
    }
    config_yaml = yaml.dump(config_dict)

    scrape_config_dict = {
        "scrape_configs": [
            {
                "job_name": "snmp",
                "static_configs": [{"targets": ["1.2.3.4", "1.2.3.5"]}],
                "metrics_path": "/snmp",
                "params": {
                    "auth": ["public_v2"],
                    "module": ["my_custom_module"],
                },
                "relabel_configs": [
                    {
                        "source_labels": ["__address__"],
                        "target_label": "__param_target",
                    },
                    {
                        "source_labels": ["__param_target"],
                        "target_label": "instance",
                    },
                    {
                        "target_label": "__address__",
                        "replacement": "localhost:9116",
                    },
                ],
            }
        ]
    }
    scrape_config_yaml = yaml.dump(scrape_config_dict)

    # Mock file operations to prevent actual file writing
    with mock.patch("builtins.open", mock.mock_open()), mock.patch("yaml.dump"), mock.patch(
        "os.makedirs"
    ), mock.patch("charms.operator_libs_linux.v2.snap.Snap.restart"):
        # Create a relation to get the scrape job configuration
        cos_agent_relation = Relation("cos-agent", remote_app_name="grafana-agent")
        state = State(
            relations=[cos_agent_relation],
            config={
                "targets": "",
                "config_file": config_yaml,
                "scrape_config_file": scrape_config_yaml,
            },
        )

        # First trigger config_changed to set the status
        state_out = ctx.run(ctx.on.config_changed(), state=state)

        # Verify the charm is active
        assert state_out.unit_status.name == "active"

        # Then trigger relation_changed to get the scrape job data
        # Use the relation from the updated state
        updated_relation = next(iter(state_out.relations))
        state_out = ctx.run(ctx.on.relation_changed(updated_relation), state=state_out)

        # Check the scrape job configuration from relation data
        relation_data = json.loads(next(iter(state_out.relations)).local_unit_data["config"])
        scrape_jobs = relation_data["metrics_scrape_jobs"]

        # Find the SNMP scrape job
        snmp_job = next(job for job in scrape_jobs if job["job_name"].endswith("snmp"))

        # Verify targets are still defined
        assert snmp_job["static_configs"][0]["targets"] == [
            "1.2.3.4",
            "1.2.3.5",
        ]

        # Verify custom module is used
        assert snmp_job["params"]["module"] == ["my_custom_module"]


def test_cos_agent_relation_data_is_set(ctx):
    cos_agent_relation = Relation("cos-agent", remote_app_name="grafana-agent")
    state = State(relations=[cos_agent_relation], config={"targets": "1.2.3.4"})
    state_out = ctx.run(ctx.on.relation_changed(cos_agent_relation), state=state)

    relation_data = json.loads(next(iter(state_out.relations)).local_unit_data["config"])
    assert len(relation_data["metrics_scrape_jobs"]) == 2
