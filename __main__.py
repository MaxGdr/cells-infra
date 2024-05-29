
import pulumi
from pulumi_gcp import container
from pulumi_kubernetes import Provider

# Get some provider-namespaced configuration values
provider_cfg = pulumi.Config("gcp")
gcp_project = provider_cfg.require("project")
gcp_region = provider_cfg.get("region", "europe-west9")

# Get some additional configuration values
config = pulumi.Config()
nodes_per_zone = config.get_int("nodesPerZone", 1)



name = "helloworld"

# Create a GKE cluster
engine_version = container.get_engine_versions(location=gcp_region).latest_master_version
cluster = container.Cluster(name,
    initial_node_count=2,
    min_master_version=engine_version,
    node_version=engine_version,
    node_config=container.ClusterNodeConfigArgs(
        machine_type="n1-standard-1",
        oauth_scopes=[
            "https://www.googleapis.com/auth/compute",
            "https://www.googleapis.com/auth/devstorage.read_only",
            "https://www.googleapis.com/auth/logging.write",
            "https://www.googleapis.com/auth/monitoring"
        ]
    )
)

# Export the Cluster name
pulumi.export("cluster_name", cluster.name)

# Manufacture a GKE-style kubeconfig
def generate_kubeconfig(args):
    name, endpoint, master_auth = args
    context = f"{gcp_project}_{gcp_region}_{name}"
    return f"""apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: {master_auth['clusterCaCertificate']}
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
cluster_provider = Provider(name, kubeconfig=kubeconfig)
