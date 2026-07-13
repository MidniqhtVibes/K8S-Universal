import json
from pathlib import Path
from typing import Any


PROXMOX_VM_RESOURCE_TYPE = "proxmox_virtual_environment_vm"


def managed_vm_ids(state_path: Path) -> set[int]:
    """Read VM IDs owned by this workspace from Terraform state JSON.

    Terraform's native state and ``terraform show -json`` use different tree
    shapes. Supporting both keeps the safety check useful for existing state
    files and for exported diagnostic state. A present but unreadable state is
    treated as an error: silently returning an empty set could allow deletion
    of a workspace while its VMs still exist.
    """
    if not state_path.is_file():
        return set()
    try:
        document = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Terraform-State kann nicht gelesen werden: {exc}") from exc

    result: set[int] = set()
    for resource in document.get("resources", []):
        if not isinstance(resource, dict) or resource.get("type") != PROXMOX_VM_RESOURCE_TYPE:
            continue
        for instance in resource.get("instances", []):
            if isinstance(instance, dict):
                attributes = instance.get("attributes", {})
                if isinstance(attributes, dict):
                    _add_vm_id(result, attributes.get("vm_id"))

    values = document.get("values", {})
    root_module = values.get("root_module", {}) if isinstance(values, dict) else {}
    _collect_show_resources(root_module, result)
    return result


def _collect_show_resources(module: Any, result: set[int]) -> None:
    if not isinstance(module, dict):
        return
    for resource in module.get("resources", []):
        if isinstance(resource, dict) and resource.get("type") == PROXMOX_VM_RESOURCE_TYPE:
            values = resource.get("values", {})
            if isinstance(values, dict):
                _add_vm_id(result, values.get("vm_id"))
    for child in module.get("child_modules", []):
        _collect_show_resources(child, result)


def _add_vm_id(result: set[int], value: Any) -> None:
    if value is None:
        return
    try:
        result.add(int(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Ungültige VM-ID im Terraform-State: {value!r}") from exc
