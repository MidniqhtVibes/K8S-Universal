from pathlib import Path


def test_credentials_can_be_deleted_when_unused_only():
    project = Path(__file__).parents[1]
    main = (project / "app/main.py").read_text(encoding="utf-8")
    template = (project / "app/templates/credentials.html").read_text(encoding="utf-8")

    assert '@app.post("/credentials/{credential_id}/delete")' in main
    assert "credential_ids_used_by" in main
    assert "Cluster.status != ClusterStatus.DESTROYED" in main
    assert "delete_credential" in main
    assert "Credential wird noch von aktiven Clustern verwendet" in main

    assert "/credentials/{{ item.id }}/delete" in template
    assert "item.id in used_credential_ids" in template
    assert "Credential wird von einem aktiven Cluster verwendet" in template
