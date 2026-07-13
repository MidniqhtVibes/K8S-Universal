from pathlib import Path
from types import SimpleNamespace

from app.models import CredentialKind
from app.services import bind_proxmox_credential


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


def test_cluster_form_uses_endpoint_and_tls_from_selected_credential(monkeypatch):
    credential = SimpleNamespace(
        id="prox",
        kind=CredentialKind.PROXMOX,
        public_data={"endpoint": "https://trusted-pve.test:8006/", "verify_tls": False},
    )
    db = SimpleNamespace(get=lambda _model, credential_id: credential if credential_id == "prox" else None)
    monkeypatch.setattr("app.services.credential_payload", lambda *_args, **_kwargs: {"api_token": "secret"})

    trusted = bind_proxmox_credential(db, {
        "proxmox_credential": "credential://prox",
        "proxmox_endpoint": "https://attacker.invalid/",
        "verify_tls": "on",
    })

    assert trusted["proxmox_endpoint"] == "https://trusted-pve.test:8006/"
    assert "verify_tls" not in trusted
