import pytest

from app.manifests import APPLICATION_TEMPLATES, render_application_template, render_snapshot, validate_manifest_content, validate_manifest_path


def test_default_nginx_bundle_contains_expected_structure():
    files = render_application_template("nginx-demo", "demo")
    assert set(files) == {"namespace.yaml", "deployment.yaml", "service.yaml", "ingress.yaml"}
    rendered, documents = render_snapshot(files)
    assert documents[0]["kind"] == "Namespace"
    assert {item["kind"] for item in documents} == {"Namespace", "Deployment", "Service", "Ingress"}
    assert "demo.lab.local" in rendered


def test_application_templates_are_rendered_for_requested_name():
    assert {"blank", "nginx-demo", "whoami", "rollout-demo"}.issubset(APPLICATION_TEMPLATES)
    blank = render_application_template("blank", "grafana")
    assert set(blank) == {"namespace.yaml"}
    assert "name: grafana" in blank["namespace.yaml"]
    demo = render_application_template("nginx-demo", "web")
    rendered, documents = render_snapshot(demo)
    assert "namespace: web" in rendered
    assert "web.lab.local" in rendered
    assert {item["kind"] for item in documents} == {"Namespace", "Deployment", "Service", "Ingress"}


def test_whoami_template_exposes_ingress_echo_app():
    files = render_application_template("whoami", "headers")
    rendered, documents = render_snapshot(files)
    assert set(files) == {"namespace.yaml", "deployment.yaml", "service.yaml", "ingress.yaml"}
    assert "traefik/whoami" in rendered
    assert "headers.lab.local" in rendered
    assert {item["kind"] for item in documents} == {"Namespace", "Deployment", "Service", "Ingress"}


def test_rollout_demo_template_contains_configmap_and_rolling_update():
    files = render_application_template("rollout-demo", "release")
    rendered, documents = render_snapshot(files)
    assert set(files) == {"namespace.yaml", "configmap.yaml", "deployment.yaml", "service.yaml", "ingress.yaml"}
    assert "rollout-demo/version: v1" in rendered
    assert "type: RollingUpdate" in rendered
    assert "release.lab.local" in rendered
    assert {item["kind"] for item in documents} == {"Namespace", "ConfigMap", "Deployment", "Service", "Ingress"}




@pytest.mark.parametrize("path", ["../secret.yaml", "/tmp/file.yaml", "manifest.txt"])
def test_unsafe_manifest_paths_are_blocked(path):
    with pytest.raises(ValueError):
        validate_manifest_path(path)


def test_multi_document_yaml_is_supported():
    documents = validate_manifest_content("apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: one\n---\napiVersion: v1\nkind: Service\nmetadata:\n  name: two\nspec:\n  ports: []\n")
    assert len(documents) == 2
