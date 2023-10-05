# snmp-exporter

Charmhub package name: snmp-exporter  
More information: https://charmhub.io/snmp-exporter

The SNMP Exporter charm exposes SNMP data over a Prometheus compatible OpenMetrics endpoint.

## Running SNMP Exporter

```sh
juju deploy snmp-exporter
juju configure snmp-exporter targets="192.168.0.34,my-server.example.com"
juju relate grafana-agent snmp-exporter
```

## Building SNMP Exporter

The charm can be easily built with charmcraft.
```sh
charmcraft pack
```

## Testing SNMP Exporter

The run the standard set of linting and tests simply run tox with no arguments.

```sh
tox
```

To run just the unit tests:

```sh
tox -e unit,scenario
```

To run the integration tests:

```sh
tox -e integration
```

## Links
[Docs](https://charmhub.io/snmp-exporter)  
[Pull Requests](https://github.com/canonical/snmp-exporter-operator/pulls)  
[Issues](https://github.com/canonical/snmp-exporter-operator/issues)  
