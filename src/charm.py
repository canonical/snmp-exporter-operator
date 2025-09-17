#!/usr/bin/env python3
# Copyright 2023 Dylan
# See LICENSE file for licensing details.

"""Charm the application."""

import logging
import os
import typing
from typing import Dict, List, Optional, Tuple, cast

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
        # Handle file writing and service restart during config change
        snmp_config = self.snmp_config
        if snmp_config:
            self._write_snmp_config_file(snmp_config=snmp_config)

        self.set_status()

    @property
    def snmp_config(self) -> Optional[Dict]:
        """Return the SNMP config from the Juju config options, if any is present."""
        if config_file := cast(str, self.config["config_file"]):
            snmp_config = yaml.safe_load(config_file)
            if not isinstance(snmp_config, Dict):
                logger.error(
                    f"Unable to set config from file. Use juju config {self.unit.name} config_file=@FILENAME"
                )
                return None
            return snmp_config

    def _write_snmp_config_file(self, snmp_config: dict) -> bool:
        """Write the SNMP config file to the expected location and restart the service.

        Returns True if successful, False otherwise.
        """
        # Get the snap data directory using the revision
        try:
            revision = self.snap.revision
            snap_data_path = f"/var/snap/prometheus-snmp-exporter/{revision}"
            config_path = os.path.join(snap_data_path, "snmp.yml")
        except (AttributeError, KeyError, TypeError) as e:
            # Fallback to current symlink if snap revision is not available
            logger.warning(f"Could not get snap revision: {e}. Using fallback path.")
            config_path = "/var/snap/prometheus-snmp-exporter/current/snmp.yml"

        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(config_path), exist_ok=True)

            with open(config_path, "w") as f:
                yaml.dump(snmp_config, f)
            logger.info(f"SNMP config file written to {config_path}")

            # Restart the snap service to pick up the new configuration
            try:
                self.snap.restart()
                logger.info("SNMP exporter service restarted to load new configuration")
            except (snap.SnapError, OSError, AttributeError) as e:
                logger.warning(f"Failed to restart SNMP exporter service: {e}")

            return True
        except OSError as e:
            logger.error(f"Failed to write SNMP config file: {e}")
            return False

    def set_status(self):
        """Calculate and set the unit status."""
        config_file = self.model.config.get("config_file", "")
        scrape_config_file = self.model.config.get("scrape_config_file", "")
        targets = self.model.config.get("targets", "")

        # Check for conflicting configuration
        if targets and (config_file or scrape_config_file):
            self.unit.status = ops.BlockedStatus(
                "Cannot set both 'targets' and config files. Please unset one of them."
            )
            return

        # Check if neither targets nor config files are set
        if not targets and not (config_file and scrape_config_file):
            self.unit.status = ops.BlockedStatus(
                'Please set either "targets" or both config files (config_file and scrape_config_file)'
            )
            return

        # Validate config files if both are set (this also parses them)
        if config_file and not self.snmp_config:
            self.unit.status = ops.BlockedStatus(
                "Invalid configuration file. Check logs for details."
            )
            return

        # Check service status
        if self.snap.services["snmp-exporter"]["active"] is False:
            self.unit.status = ops.MaintenanceStatus()
        else:
            self.unit.status = ops.ActiveStatus()

    def scrape_configs(self) -> List[Dict]:
        """Return the scrape configs for the endpoints generated by the SNMP exporter and for the SNMP exporter itself."""
        if config_file := cast(str, self.config["scrape_config_file"]):
            scrape_config = yaml.safe_load(config_file)
            if not isinstance(scrape_config, Dict):
                logger.error(
                    f"Unable to set scrape config from file. Use juju config {self.unit.name} scrape_config_file=@FILENAME"
                )
            else:
                return scrape_config["scrape_configs"]

        # Original behavior when using targets directly from Juju config
        return [
            # The actual SNMP scrape jobs
            {
                "job_name": "snmp",
                "static_configs": [
                    {"targets": typing.cast(str, self.model.config["targets"]).split(",")}
                ],
                "metrics_path": "/snmp",
                "params": {
                    "auth": ["public_v2"],
                    "module": ["if_mib"],
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
                        "replacement": f"localhost:{EXPORTER_PORT}",
                    },
                ],
            },
            # The metrics of prometheus-snmp-exporter itself
            {
                "job_name": "snmp-exporter",
                "static_configs": [{"targets": [f"localhost:{EXPORTER_PORT}"]}],
            },
        ]


if __name__ == "__main__":  # pragma: nocover
    ops.main(SNMPExporterCharm)  # type: ignore
