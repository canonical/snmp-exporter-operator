#!/usr/bin/env python3
# Copyright 2023 Dylan
# See LICENSE file for licensing details.

"""Charm the application."""

import logging
import os
import typing
from typing import Optional, Tuple, cast

import ops
import yaml
from charms.grafana_agent.v0.cos_agent import COSAgentProvider
from charms.operator_libs_linux.v2 import snap

logger = logging.getLogger(__name__)

SNAP_CHANNEL = "0.24/stable"
EXPORTER_PORT = 9116


class SNMPExporterCharm(ops.CharmBase):
    """Charm the application."""

    def __init__(self, *args):
        super().__init__(*args)

        self.snap = snap.SnapCache()["prometheus-snmp-exporter"]

        self.cos_agent = COSAgentProvider(
            charm=self,
            scrape_configs=self.scrape_configs(),
            refresh_events=[self.on.config_changed],
        )

        self.framework.observe(self.on.install, self.on_install)
        self.framework.observe(self.on.start, self.on_start)
        self.framework.observe(self.on.config_changed, self.on_config_changed)

    def on_install(self, event: ops.InstallEvent):
        """Handle install event."""
        self.snap.ensure(state=snap.SnapState.Latest, channel=SNAP_CHANNEL)

    def on_start(self, event: ops.StartEvent):
        """Handle start event."""
        self.snap.start(enable=True)
        self.set_status()

    def on_stop(self, event: ops.StopEvent):
        """Handle stop event."""
        self.snap.stop(disable=True)
        self.snap.ensure(state=snap.SnapState.Absent)

    def on_config_changed(self, event: ops.ConfigChangedEvent):
        """Handle config changed event."""
        self._get_local_config()
        self.set_status()

    def _get_local_config(
        self,
    ) -> Optional[Tuple[Optional[dict], Optional[str]]]:
        """Handle config file and custom module configuration."""
        config = self.model.config.get("config_file", "")
        custom_module = self.model.config.get("custom_module", "")

        if config and custom_module:
            try:
                local_config = yaml.safe_load(cast(str, config))

                # If `juju config` is executed like this `config_file=snmp.yaml` instead of
                # `config_file=@snmp.yaml` local_config will be the string `snmp.yaml` instead
                # of its content (dict).
                if not isinstance(local_config, dict):
                    msg = f"Unable to set config from file. Use juju config {self.unit.name} config_file=@FILENAME"
                    logger.error(msg)
                    return None

                # Both config_file and custom_module are provided
                snap_data = os.environ.get("SNAP_DATA", "")
                if snap_data:
                    config_path = os.path.join(snap_data, "snmp.yaml")
                else:
                    config_path = (
                        "/var/snap/prometheus-snmp-exporter/current/snmp.yml"
                    )

                # Write the config file content to the expected location
                try:
                    with open(config_path, "w") as f:
                        yaml.dump(local_config, f)
                    logger.info(f"SNMP config file written to {config_path}")
                    return local_config, str(custom_module)
                except Exception as e:
                    logger.error(f"Failed to write SNMP config file: {e}")
                    return None
            except yaml.YAMLError as e:
                logger.error(f"Failed to parse YAML config: {e}")
                return None

        return None

    def set_status(self):
        """Calculate and set the unit status."""
        config_file = self.model.config.get("config_file", "")
        custom_module = self.model.config.get("custom_module", "")

        if not self.model.config["targets"]:
            self.unit.status = ops.BlockedStatus('Please set the "targets" config variable')
            return
        elif (config_file and not custom_module) or (
            custom_module and not config_file
        ):
            self.unit.status = ops.BlockedStatus(
                "Both config_file and custom_module must be set together"
            )
            return
        elif config_file and custom_module:
            # Check if config file can be parsed
            try:
                local_config = yaml.safe_load(cast(str, config_file))
                if not isinstance(local_config, dict):
                    self.unit.status = ops.BlockedStatus(
                        f"Unable to set config from file. Use juju config {self.unit.name} config_file=@FILENAME"
                    )
                    return
            except yaml.YAMLError:
                self.unit.status = ops.BlockedStatus(
                    "Invalid YAML in config_file"
                )
                return

        if self.snap.services["snmp-exporter"]["active"] is False:
            self.unit.status = ops.MaintenanceStatus()
        else:
            self.unit.status = ops.ActiveStatus()

    def scrape_configs(self):
        """Return the scrape configs for the endpoints generated by the SNMP exporter and for the SNMP exporter itself."""
        config_file = self.model.config.get("config_file", "")
        custom_module = self.model.config.get("custom_module", "")

        # Build params for SNMP scrape job
        params = {}
        if config_file and custom_module:
            # Use custom module when config file is provided, no auth needed
            params["module"] = [custom_module]
        else:
            # Default behavior - use public_v2 auth and if_mib module
            params["auth"] = ["public_v2"]
            params["module"] = ["if_mib"]

        return [
            # The actual SNMP scrape jobs
            {
                "job_name": "snmp",
                "static_configs": [
                    {
                        "targets": typing.cast(
                            str, self.model.config["targets"]
                        ).split(",")
                    }
                ],
                "metrics_path": "/snmp",
                "params": params,
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
                        "replacement": f"localhost:{EXPORTER_PORT}",
                    },
                ],
            },
            # The metrics of prometheus-snmp-exporter itself
            {
                "job_name": "snmp-exporter",
                "static_configs": [
                    {"targets": [f"localhost:{EXPORTER_PORT}"]}
                ],
            },
        ]


if __name__ == "__main__":  # pragma: nocover
    ops.main(SNMPExporterCharm)  # type: ignore
