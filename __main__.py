
import pulumi
from pulumi import Output
from pulumi_gcp import (
    container,
    artifactregistry,
    serviceaccount,
    projects,
    storage,
)
from pulumi_kubernetes import Provider

# Get some provider-namespaced configuration values
provider_cfg = pulumi.Config("gcp")
gcp_project = provider_cfg.require("project")
gcp_region = provider_cfg.require("region")
gcp_zone = provider_cfg.require("zone")

# Get some additional configuration values
config = pulumi.Config()
nodes_per_zone = config.get_int("nodesPerZone", 1)
project_number = config.get("projectNumber")

# Creates Artifact repository
docker_repository = artifactregistry.Repository(
    resource_name="cells-artifactory",
    location=gcp_region,
    repository_id="cells-dockers",
    description="Docker repository for cells project",
    format="DOCKER"
)

# Create a service account for the Kubernetes cluster
k8s_service_account = serviceaccount.Account(
    resource_name="k8s-sa",
    account_id="k8s-sa",
    display_name="Kubernetes Service Account"
)

# Bind artifactregistry.reader permission to k8s_service_account in artifact
iam_binding = k8s_service_account.email.apply(
    lambda email: projects.IAMBinding(
        "artifact-registry-reader-binding",
        project=gcp_project,
        role="roles/artifactregistry.reader",
        members=[f"serviceAccount:{email}"],
    )
)

base_resource_name = "cells-gke-cluster"

# Create a GKE cluster
engine_version = container.get_engine_versions(location=gcp_region).latest_master_version

cluster = container.Cluster(
    resource_name=base_resource_name,
    location=gcp_zone,
    initial_node_count=1,
    min_master_version=engine_version,
    node_version=engine_version,
    node_config=container.ClusterNodeConfigArgs(
        service_account=k8s_service_account.email,
        machine_type="e2-medium",
        disk_size_gb=100,
        disk_type="pd-balanced",
        oauth_scopes=[
            "https://www.googleapis.com/auth/compute",
            "https://www.googleapis.com/auth/devstorage.read_only",
            "https://www.googleapis.com/auth/logging.write",
            "https://www.googleapis.com/auth/monitoring"
        ]
    ),
    opts=pulumi.ResourceOptions(depends_on=[k8s_service_account])
)

# Export the Cluster name
pulumi.export("cluster_name", cluster.name)

# Manufacture a GKE-style kubeconfig
def generate_kubeconfig(args):
    name, endpoint, master_auth = args
    context = f"{gcp_project}_{gcp_zone}_{name}"
    return f"""apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: {master_auth['cluster_ca_certificate']}
    server: https://{endpoint}
  name: {context}
contexts:
- context:
    cluster: {context}
    user: {context}
  name: {context}
current-context: {context}
kind: Config
preferences: {{}}
users:
- name: {context}
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      command: gke-gcloud-auth-plugin
      installHint: Install gke-gcloud-auth-plugin for use with kubectl by following
        https://cloud.google.com/blog/products/containers-kubernetes/kubectl-auth-changes-in-gke
      provideClusterInfo: true
"""

kubeconfig = pulumi.Output.all(cluster.name, cluster.endpoint, cluster.master_auth).apply(generate_kubeconfig)

# Create a Kubernetes provider instance that uses our cluster from above
cluster_provider = Provider(base_resource_name, kubeconfig=kubeconfig)


# Create a GCS bucket for machine learning vertex projects
gcs_bucket = storage.Bucket(
    resource_name="ml-vertex-bucket",
    location=gcp_region,
    storage_class="STANDARD",
    force_destroy=True,
)

SVC_ACCOUNT=f"{project_number}-compute@developer.gserviceaccount.com"

# Create a service account for the Kubernetes cluster
ml_service_account = serviceaccount.Account(
    resource_name="ml-sa",
    account_id="ml-infra-sa",
    display_name="ML Infra Service Account"
)

compute_sa_storage_iam = ml_service_account.email.apply(
    lambda email: projects.IAMBinding(
        "storage-bucket-admin-binding",
        project=gcp_project,
        role="roles/storage.objectAdmin",
        members=[f"serviceAccount:{SVC_ACCOUNT}", f"serviceAccount:{email}"],
    )
)

backend_service_account = serviceaccount.Account(
    resource_name="backend-sa",
    account_id="backend-sa",
    display_name="Cells Backend Service Account"
)

backend_vertex_iam = backend_service_account.email.apply(
    lambda email: projects.IAMBinding(
        "vertex-ai-backend-service-vertex-user-binding",
        project=gcp_project,
        role="roles/aiplatform.user",
        members=[f"serviceAccount:{email}"],
    )
)
