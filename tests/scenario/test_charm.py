import json

from scenario import Context, Relation, State

import charm


def test_status_no_config():
    context = Context(charm_type=charm.SNMPExporterCharm)
    state = State(config={"targets": ""})
    state_out = context.run(context.on.config_changed(), state=state)
    assert state_out.unit_status.name == "blocked"


def test_status_with_config():
    context = Context(charm_type=charm.SNMPExporterCharm)
    state = State(config={"targets": "1.2.3.4"})
    state_out = context.run(context.on.config_changed(), state=state)
    assert state_out.unit_status.name == "active"


def test_cos_agent_relation_data_is_set():
    cos_agent_relation = Relation("cos-agent", remote_app_name="grafana-agent")
    context = Context(charm_type=charm.SNMPExporterCharm)
    state = State(relations=[cos_agent_relation], config={"targets": "1.2.3.4"})
    state_out = context.run(context.on.relation_changed(cos_agent_relation), state=state)

    relation_data = json.loads(
        state_out.get_relation(cos_agent_relation.id).local_unit_data["config"]
    )
    assert len(relation_data["metrics_scrape_jobs"]) == 2
