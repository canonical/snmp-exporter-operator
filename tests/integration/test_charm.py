#!/usr/bin/env python3
# Copyright 2023 Dylan
# See LICENSE file for licensing details.

import asyncio
import json
import logging
import time

import pytest
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

APP_NAME = "snmp-exporter"


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest):
    """Build the charm-under-test and deploy it together with related charms.

    Assert on the unit status before any relations/configurations take place.
    """
    # Build and deploy charm from local source folder
    charm = await ops_test.build_charm(".")

    # Deploy the charm and wait for active/idle status
    await asyncio.gather(
        ops_test.model.deploy(charm, config={"targets": "1.2.3.4"}, application_name=APP_NAME),
        ops_test.model.wait_for_idle(apps=[APP_NAME], status="active", timeout=1000),
    )


async def test_relate_to_cos(ops_test: OpsTest):
    """Relate to grafana-agent and assert that the SNMP targets are being scraped."""
    await asyncio.gather(
        ops_test.model.deploy("grafana-agent", channel="edge"),
        ops_test.model.deploy("grafana-cloud-integrator", channel="edge"),
    )
    await asyncio.gather(
        ops_test.model.integrate("grafana-agent", "grafana-cloud-integrator"),
        ops_test.model.integrate("grafana-agent", APP_NAME),
    )
    await ops_test.model.wait_for_idle(
        wait_for_active=True,
        apps=["grafana-agent", APP_NAME],
        wait_for_at_least_units=1,
    )
    agent_app = ops_test.model.applications["grafana-agent"]
    agent_unit = agent_app.units[0]
    for _i in range(60):
        # wait_for_idle does not wait so we need this loop.
        time.sleep(10)
        await agent_app.get_status()  # Refresh the cached statuses.
        if agent_unit.workload_status == "active":
            break
    else:
        assert False, "Timeout waiting for grafana-agent status to become active"

    time.sleep(20)  # Make sure the service has started.
    p = await agent_unit.ssh("curl localhost:12345/agent/api/v1/targets")
    data = json.loads(p)["data"]
    target_groups = [instance["target_group"] for instance in data]
    assert f"{APP_NAME}_0_snmp" in target_groups
    assert f"{APP_NAME}_1_snmp-exporter" in target_groups
