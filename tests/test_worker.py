import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.worker import ingress_test_targets, validate_proxmox

from .helpers import valid_config


def test_proxmox_preflight_uses_configured_template_vm_id(monkeypatch, tmp_path):
    config = valid_config()

    class FakeProxmoxClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def discover(self):
            return {
                "nodes": [{"node": "pve"}],
                "vms": [{"vmid": config.proxmox.template_vm_id, "template": 1, "type": "qemu", "node": "pve"}],
                "details": {
                    "pve": {
                        "storages": [{"storage": "local-lvm"}],
                        "bridges": [{"iface": "vmbr0"}],
                    }
                },
            }

    monkeypatch.setattr("app.worker.ProxmoxClient", FakeProxmoxClient)
    monkeypatch.setattr("app.worker.append_log", lambda *_args, **_kwargs: None)

    validate_proxmox(SimpleNamespace(id="test-job"), config, "test-token", tmp_path)


def test_destroy_plan_avoids_terraform_refresh_and_proxmox_preflight():
    worker = (Path(__file__).parents[1] / "app/worker.py").read_text(encoding="utf-8")
    assert 'command.extend(["-destroy", "-refresh=false"])' in worker
    assert "if job.kind == JobKind.PLAN:\n                validate_proxmox" in worker


def test_terraform_commands_limit_parallelism():
    project = Path(__file__).parents[1]
    worker = (project / "app/worker.py").read_text(encoding="utf-8")
    config = (project / "app/config.py").read_text(encoding="utf-8")
    assert "terraform_parallelism: int = Field(default=2" in config
    assert "terraform_parallelism_arg()" in worker
    assert '["terraform", "apply", "-input=false", terraform_parallelism_arg(), "tfplan"]' in worker
    assert '["terraform", "apply", "-input=false", terraform_parallelism_arg(), "destroy.tfplan"]' in worker


def test_apply_consumes_the_reviewed_tfplan_without_replacing_it():
    worker = (Path(__file__).parents[1] / "app/worker.py").read_text(encoding="utf-8")
    assert "def create_terraform_plan(" in worker
    apply_branch = worker.split("if job.kind == JobKind.APPLY:", 1)[1].split("if job.kind == JobKind.ANSIBLE:", 1)[0]
    assert "create_terraform_plan(" not in apply_branch
    assert 'plan_path = terraform_dir / "tfplan"' in apply_branch
    assert "Der geprüfte Terraform-Plan fehlt" in apply_branch
    assert "plan_path.unlink(missing_ok=True)" in apply_branch


def test_ingress_test_targets_use_vip_and_host_header():
    targets = ingress_test_targets(
        [
            {
                "kind": "Ingress",
                "spec": {
                    "rules": [
                        {"host": "web.lab.local", "http": {"paths": [{"path": "/"}, {"path": "/api"}]}},
                        {"host": "web.lab.local", "http": {"paths": [{"path": "/"}]}},
                    ]
                },
            }
        ],
        "10.200.50.150",
    )
    assert targets == [
        ("http://10.200.50.150/", "web.lab.local"),
        ("http://10.200.50.150/api", "web.lab.local"),
    ]


def test_manifest_apply_runs_ingress_tests_inside_the_worker():
    worker = (Path(__file__).parents[1] / "app/worker.py").read_text(encoding="utf-8")
    assert "HTTP-Funktionstest über die Cluster-VIP:" in worker
    assert "run_ingress_tests(job, documents, api_vip)" in worker
    assert "client.get(url, headers={\"Host\": host})" in worker
    assert "Kein Ingress-Host im Bundle gefunden" in worker


def test_helm_and_cluster_verification_wait_for_ready_resources():
    worker = (Path(__file__).parents[1] / "app/worker.py").read_text(encoding="utf-8")
    assert '"--version", config.addons.ingress.chart_version' in worker
    assert '"--wait", "--wait-for-jobs", "--timeout", "10m"' in worker
    assert '"wait", "--for=condition=Ready", "--timeout=300s"' in worker
    assert '"--field-selector=status.phase!=Succeeded,status.phase!=Failed"' in worker


def test_proxmox_preflight_only_exempts_vm_ids_owned_by_terraform_state(monkeypatch, tmp_path):
    config = valid_config()
    state_dir = tmp_path / "terraform"
    state_dir.mkdir()
    (state_dir / "terraform.tfstate").write_text(json.dumps({
        "resources": [{
            "type": "proxmox_virtual_environment_vm",
            "instances": [{"attributes": {"vm_id": config.nodes[0].vm_id}}],
        }]
    }), encoding="utf-8")

    class FakeProxmoxClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def discover(self):
            return {
                "nodes": [{"node": "pve"}],
                "vms": [
                    {"vmid": config.proxmox.template_vm_id, "template": 1, "type": "qemu", "node": "pve"},
                    {"vmid": config.nodes[0].vm_id, "template": 0, "type": "qemu", "node": "pve"},
                    {"vmid": config.nodes[1].vm_id, "template": 0, "type": "qemu", "node": "pve"},
                ],
                "details": {"pve": {"storages": [{"storage": "local-lvm"}], "bridges": [{"iface": "vmbr0"}]}},
            }

    monkeypatch.setattr("app.worker.ProxmoxClient", FakeProxmoxClient)
    monkeypatch.setattr("app.worker.append_log", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match=str(config.nodes[1].vm_id)):
        validate_proxmox(SimpleNamespace(id="test-job"), config, "test-token", tmp_path)


def test_worker_recovers_stale_jobs_and_supports_ansible_rerun():
    project = Path(__file__).parents[1]
    worker = (project / "app/worker.py").read_text(encoding="utf-8")
    models = (project / "app/models.py").read_text(encoding="utf-8")
    migration = (project / "migrations/versions/0005_job_recovery_ansible.py").read_text(encoding="utf-8")

    assert 'ANSIBLE = "ansible"' in models
    assert "heartbeat_at" in models
    assert "ALTER TYPE jobkind ADD VALUE IF NOT EXISTS 'ANSIBLE'" in migration
    assert "op.add_column(\"jobs\", sa.Column(\"heartbeat_at\"" in migration
    assert "def recover_interrupted_jobs()" in worker
    assert "def recover_stale_running_jobs()" in worker
    assert "recover_interrupted_jobs()" in worker
    assert "recover_stale_running_jobs()" in worker.split("def recover_interrupted_jobs()", 1)[1].split("def recover_stale_running_jobs()", 1)[0]
    assert "JobKind.ANSIBLE" in worker
    assert "Ansible/Helm/Verify wird ohne Terraform erneut ausgefuehrt." in worker
    assert "Kurzdiagnose:" in worker
