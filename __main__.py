import pulumi
import pulumi_gcp as gcp


# Get some provider-namespaced configuration values
provider_cfg = pulumi.Config("gcp")
gcp_project = provider_cfg.require("project")
gcp_region = provider_cfg.get("region", "europe-west9")

# Get some additional configuration values
config = pulumi.Config()
nodes_per_zone = config.get_int("nodesPerZone", 1)


# GKE
# Create the GKE cluster with autopilot enabled
cluster = gcp.container.Cluster("simple-gke-cluster",
    location=gcp_region,
    enable_autopilot=True,
    initial_node_count=nodes_per_zone,
    min_master_version="latest",
)

# Create a NodePool with autoscaling enabled
node_pool = gcp.container.NodePool("app-node-pool",
    cluster=cluster.name,
    location=cluster.location,
    autoscaling=gcp.container.NodePoolAutoscalingArgs(
        enabled=True,
        min_node_count=1,
        max_node_count=2,
    ),
    node_config=gcp.container.NodePoolNodeConfigArgs(
        preemptible=True,
    ),
)


# Export the cluster's endpoint and name
pulumi.export("cluster_name", cluster.name)
pulumi.export("node_pool_name", node_pool.name)
pulumi.export("endpoint", cluster.endpoint)
