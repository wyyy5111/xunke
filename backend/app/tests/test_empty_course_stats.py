"""A newly created course must render statistics before its first agent run."""


def test_experiment_with_no_agent_runs(client, teacher_token):
    headers = {"Authorization": f"Bearer {teacher_token}"}
    created = client.post("/api/courses", headers=headers, json={"name": "空课程统计验证"})
    assert created.status_code == 200
    cid = created.json()["data"]["id"]
    response = client.get(f"/api/stats/experiment/{cid}", headers=headers)
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["multi_vs_single_agent"]["multi_agent_steps"] == 0
    assert result["multi_vs_single_agent"]["single_agent_steps"] == 0
    assert result["llm_calls"] == 0
