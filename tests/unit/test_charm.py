import json

from ops.testing import Relation, State


def test_status_no_config(ctx):
    state = State(config={"targets": ""})
    state_out = ctx.run(ctx.on.config_changed(), state=state)
    assert state_out.unit_status.name == "blocked"


def test_status_with_config(ctx):
    state = State(config={"targets": "1.2.3.4"})
    state_out = ctx.run(ctx.on.config_changed(), state=state)
    assert state_out.unit_status.name == "active"


def test_cos_agent_relation_data_is_set(ctx):
    cos_agent_relation = Relation("cos-agent", remote_app_name="grafana-agent")
    state = State(relations=[cos_agent_relation], config={"targets": "1.2.3.4"})
    state_out = ctx.run(ctx.on.relation_changed(cos_agent_relation), state=state)

    print(state_out)
    relation_data = json.loads(next(iter(state_out.relations)).local_unit_data["config"])
    assert len(relation_data["metrics_scrape_jobs"]) == 2
