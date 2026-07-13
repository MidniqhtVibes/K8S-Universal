import pytest
from pydantic import ValidationError

from .helpers import valid_config


def test_valid_cluster_schema():
    config = valid_config()
    assert config.network.cidr.prefixlen == 24
    assert len(config.nodes) == 6


@pytest.mark.parametrize("field,value", [("api_vip", "10.20.1.1"), ("api_vip", "10.10.10.11")])
def test_rejects_invalid_vip(field, value):
    payload = valid_config().model_dump(mode="json")
    payload["network"][field] = value
    with pytest.raises(ValidationError):
        type(valid_config()).model_validate(payload)


def test_rejects_overlapping_networks():
    payload = valid_config().model_dump(mode="json")
    payload["kubernetes"]["pod_cidr"] = "10.10.10.0/25"
    with pytest.raises(ValidationError, match="überschneiden"):
        type(valid_config()).model_validate(payload)


def test_rejects_duplicate_vm_id():
    payload = valid_config().model_dump(mode="json")
    payload["nodes"][1]["vm_id"] = payload["nodes"][0]["vm_id"]
    with pytest.raises(ValidationError, match="VM-IDs"):
        type(valid_config()).model_validate(payload)


@pytest.mark.parametrize("conflict", ["api_vip", "node"])
def test_gateway_cannot_overlap_cluster_addresses(conflict):
    payload = valid_config().model_dump(mode="json")
    payload["network"]["gateway"] = (
        payload["network"]["api_vip"] if conflict == "api_vip" else payload["nodes"][0]["ip"]
    )
    with pytest.raises(ValidationError, match="Gateway"):
        type(valid_config()).model_validate(payload)


def test_template_id_cannot_be_reused_by_a_node():
    payload = valid_config().model_dump(mode="json")
    payload["nodes"][0]["vm_id"] = payload["proxmox"]["template_vm_id"]
    with pytest.raises(ValidationError, match="Template-VM-ID"):
        type(valid_config()).model_validate(payload)


@pytest.mark.parametrize(
    "section,field,value",
    [
        ("ssh", "port", 2222),
        ("kubernetes", "api_port", 7443),
        ("kubernetes", "version", "v1.35"),
    ],
)
def test_rejects_options_the_provisioning_stack_does_not_implement(section, field, value):
    payload = valid_config().model_dump(mode="json")
    payload[section][field] = value
    with pytest.raises(ValidationError):
        type(valid_config()).model_validate(payload)


def test_rejects_more_load_balancers_than_keepalived_supports():
    payload = valid_config().model_dump(mode="json")
    prototype = payload["nodes"][0]
    for number in range(3, 12):
        payload["nodes"].append({
            **prototype,
            "name": f"lb-{number:02d}",
            "vm_id": 400 + number,
            "ip": f"10.10.10.{40 + number}",
        })
    with pytest.raises(ValidationError, match="zehn Load Balancer"):
        type(valid_config()).model_validate(payload)
