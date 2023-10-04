#!/usr/bin/env python3
# Copyright 2023 Dylan
# See LICENSE file for licensing details.

"""Charm the application."""

import logging

import ops
from charms.grafana_agent.v0.cos_agent import COSAgentProvider
from charms.operator_libs_linux.v2 import snap

logger = logging.getLogger(__name__)


class PrometheusSnmpExporterCharm(ops.CharmBase):
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
        self.snap.ensure(state=snap.SnapState.Latest, channel="0.24/stable")

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
        self.set_status()

    def set_status(self):
        """Calculate and set the unit status."""
        if not self.model.config["targets"]:
            self.unit.status = ops.BlockedStatus('Please set the "targets" config variable')
        elif self.snap.services["snmp-exporter"]["active"] is False:
            self.unit.status = ops.MaintenanceStatus()
        else:
            self.unit.status = ops.ActiveStatus()

    def scrape_configs(self):
        """Return the scrape configs for scraping the exporter."""
        return [
            # The actual SNMP scrape jobs
            {
                "job_name": "snmp",
                "static_configs": [{"targets": self.model.config["targets"].split(",")}],
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
                        "replacement": "localhost:9116",
                    },
                ],
            },
            # The metrics of prometheus-snmp-exporter itself
            {"job_name": "snmp-exporter", "static_configs": [{"targets": ["localhost:9116"]}]},
        ]


if __name__ == "__main__":  # pragma: nocover
    ops.main(PrometheusSnmpExporterCharm)  # type: ignore
