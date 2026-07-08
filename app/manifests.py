import re
from pathlib import PurePosixPath

import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import ApplicationBundle, Cluster, ManifestFile, ManifestRevision


PATH_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._/-]*\.ya?ml$")
KIND_PRIORITY = {
    "Namespace": 0,
    "CustomResourceDefinition": 10,
    "ServiceAccount": 20,
    "ClusterRole": 21,
    "ClusterRoleBinding": 22,
    "Role": 23,
    "RoleBinding": 24,
    "ConfigMap": 30,
    "Service": 40,
    "Deployment": 50,
    "StatefulSet": 50,
    "DaemonSet": 50,
    "Ingress": 60,
}


def cluster_dns_label(cluster: Cluster) -> str:
    label = re.sub(r"[^a-z0-9]", "", cluster.name.lower())
    if not label:
        label = re.sub(r"[^a-z0-9]", "", cluster.id.lower())[:20]
    return label[:63] or "cluster"


def default_nginx_files(cluster: Cluster, bundle_name: str = "nginx-demo") -> dict[str, str]:
    namespace = "demo" if bundle_name == "nginx-demo" else bundle_name
    resource_name = "nginx-demo" if bundle_name == "nginx-demo" else "nginx"
    service_name = f"{resource_name}-service"
    host_prefix = "nginx" if bundle_name == "nginx-demo" else bundle_name
    host = f"{host_prefix}.{cluster_dns_label(cluster)}.local"
    return {
    "namespace.yaml": """apiVersion: v1
kind: Namespace
metadata:
  name: """ + namespace + """
""",
    "deployment.yaml": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: """ + resource_name + """
  namespace: """ + namespace + """
spec:
  replicas: 3
  selector:
    matchLabels:
      app: """ + resource_name + """
  template:
    metadata:
      labels:
        app: """ + resource_name + """
    spec:
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              app: """ + resource_name + """
      containers:
        - name: nginx
          image: nginx:1.27
          ports:
            - containerPort: 80
""",
    "service.yaml": """apiVersion: v1
kind: Service
metadata:
  name: """ + service_name + """
  namespace: """ + namespace + """
spec:
  type: ClusterIP
  selector:
    app: """ + resource_name + """
  ports:
    - name: http
      port: 80
      targetPort: 80
""",
    "ingress.yaml": """apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: """ + resource_name + """
  namespace: """ + namespace + """
spec:
  ingressClassName: traefik
  rules:
    - host: """ + host + """
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: """ + service_name + """
                port:
                  number: 80
""",
    }


DEFAULT_NGINX_FILES = default_nginx_files(Cluster(id="example", name="lab"))


def validate_manifest_path(path: str) -> str:
    value = path.strip().lower()
    pure = PurePosixPath(value)
    if not PATH_PATTERN.fullmatch(value) or pure.is_absolute() or ".." in pure.parts:
        raise ValueError("Dateiname muss ein relativer, sicherer .yaml- oder .yml-Pfad sein")
    return value


def validate_manifest_content(content: str) -> list[dict]:
    if not content.strip() or len(content.encode()) > 1_000_000:
        raise ValueError("Manifest ist leer oder größer als 1 MB")
    try:
        documents = [item for item in yaml.safe_load_all(content) if item is not None]
    except yaml.YAMLError as exc:
        raise ValueError(f"Ungültiges YAML: {exc}") from exc
    if not documents:
        raise ValueError("Manifest enthält kein Kubernetes-Objekt")
    for document in documents:
        if not isinstance(document, dict):
            raise ValueError("Jedes YAML-Dokument muss ein Kubernetes-Objekt sein")
        for key in ("apiVersion", "kind", "metadata"):
            if key not in document:
                raise ValueError(f"Pflichtfeld '{key}' fehlt")
        if not isinstance(document["metadata"], dict) or not document["metadata"].get("name"):
            raise ValueError("metadata.name fehlt")
        if document["kind"] == "Secret":
            raise ValueError("Unverschlüsselte Kubernetes-Secrets sind im Manifest-Editor gesperrt")
    return documents


def snapshot_bundle(bundle: ApplicationBundle) -> dict:
    return {manifest.path: manifest.content for manifest in sorted(bundle.files, key=lambda item: item.path)}


def create_revision(db: Session, bundle: ApplicationBundle, message: str) -> ManifestRevision:
    current = db.scalar(select(func.max(ManifestRevision.version)).where(ManifestRevision.bundle_id == bundle.id)) or 0
    revision = ManifestRevision(bundle_id=bundle.id, version=current + 1, snapshot=snapshot_bundle(bundle), message=message[:255])
    db.add(revision)
    db.flush()
    return revision


def ensure_default_bundle(db: Session, cluster: Cluster) -> ApplicationBundle:
    existing = db.scalar(select(ApplicationBundle).where(ApplicationBundle.cluster_id == cluster.id, ApplicationBundle.name == "nginx-demo"))
    if existing:
        return existing
    bundle = ApplicationBundle(cluster_id=cluster.id, name="nginx-demo", description="Beispielanwendung mit Namespace, Deployment, Service und Traefik Ingress")
    db.add(bundle)
    db.flush()
    for path, content in default_nginx_files(cluster).items():
        bundle.files.append(ManifestFile(path=path, content=content))
    db.flush()
    create_revision(db, bundle, "Automatisch erzeugtes Nginx-Beispiel")
    db.commit()
    return bundle


def render_snapshot(snapshot: dict) -> tuple[str, list[dict]]:
    documents: list[dict] = []
    for path in sorted(snapshot):
        validate_manifest_path(path)
        documents.extend(validate_manifest_content(str(snapshot[path])))
    documents.sort(key=lambda item: (KIND_PRIORITY.get(str(item.get("kind")), 45), str(item.get("kind")), str(item.get("metadata", {}).get("name"))))
    return yaml.safe_dump_all(documents, sort_keys=False), documents
