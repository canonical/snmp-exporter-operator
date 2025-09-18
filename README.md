# snmp-exporter

Charmhub package name: snmp-exporter  
More information: https://charmhub.io/snmp-exporter

The SNMP Exporter charm exposes SNMP data over a Prometheus compatible OpenMetrics endpoint.

## Running SNMP Exporter

```sh
juju deploy snmp-exporter
juju config snmp-exporter targets="192.168.0.34,my-server.example.com"
juju relate grafana-agent snmp-exporter
```

## Configuration

The charm supports the following configuration options:

### targets
Comma separated list of targets to scrape.

```sh
juju config snmp-exporter targets="192.168.0.34,my-server.example.com"
```

### config_file and scrape_config_file
Custom SNMP and Prometheus scrape configuration files (yaml). **Both options must be provided together or the charm will remain blocked.**

To send the contents of a file to these configuration options, the symbol `@` must be used:

```sh
juju config snmp-exporter config_file=@snmp.yaml scrape_config_file=@scrape_config.yaml
```

#### config_file
The content of this file should not be manually created or edited by user. For reference on how to generate config file, please refer to: https://github.com/prometheus/snmp_exporter/tree/main/generator

#### scrape_config_file
For reference on how to format the Prometheus config file, please refer to: https://github.com/prometheus/snmp_exporter?tab=readme-ov-file#prometheus-configuration

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
