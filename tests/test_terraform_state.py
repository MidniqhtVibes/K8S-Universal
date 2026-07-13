import json

import pytest

from app.terraform_state import managed_vm_ids


def test_reads_managed_vm_ids_from_native_state(tmp_path):
    state = tmp_path / "terraform.tfstate"
    state.write_text(json.dumps({
        "resources": [
            {
                "type": "proxmox_virtual_environment_vm",
                "instances": [
                    {"attributes": {"vm_id": 301}},
                    {"attributes": {"vm_id": "302"}},
                ],
            },
            {"type": "random_id", "instances": [{"attributes": {"vm_id": 999}}]},
        ]
    }), encoding="utf-8")
    assert managed_vm_ids(state) == {301, 302}


def test_reads_managed_vm_ids_from_terraform_show_tree(tmp_path):
    state = tmp_path / "show.json"
    state.write_text(json.dumps({
        "values": {
            "root_module": {
                "child_modules": [{
                    "resources": [{
                        "type": "proxmox_virtual_environment_vm",
                        "values": {"vm_id": 401},
                    }]
                }]
            }
        }
    }), encoding="utf-8")
    assert managed_vm_ids(state) == {401}


def test_present_but_invalid_state_never_silently_looks_empty(tmp_path):
    state = tmp_path / "terraform.tfstate"
    state.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Terraform-State"):
        managed_vm_ids(state)
