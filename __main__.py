"""A Python Pulumi program"""

import pulumi
# import pulumi_oci as oci
import pulumi_rke as rke

config = pulumi.Config()
master_public_ip = config.require("master_public_ip")
master_internal_ip = config.require("master_internal_ip")
worker_public_ip = config.require("worker_public_ip")
worker_internal_ip = config.require("worker_internal_ip")
ssh_key_path = config.require("ssh_key_path")

# Didn't get oci package working:
# pulumi:providers:oci (default_0_0_0):
# error: no resource plugin 'oci-v0.0.0' found in the workspace or on your $PATH,
# install the plugin using `pulumi plugin install resource oci v0.0.0`

# oci.core.Instance("oci-instance",
#                 availability_domain="AD-1",
#                 compartment_id="NNNN",
#                 shape="VM.Standard.E3.Flex")


def write_kubeconfig(data):
    """Write kubeconfig from RKE to 'out' directory."""
    with open("out/rke_kubeconfig", "w", encoding="utf8") as kubeconfig:
        kubeconfig.write(data)


rke_cluster = rke.Cluster("masterofclusters",
                          nodes=[
                            rke.ClusterNodeArgs(address=master_public_ip,
                                                internal_address=master_internal_ip,
                                                user="opc",
                                                roles=["controlplane", "etcd", "worker"]),
                            rke.ClusterNodeArgs(address=worker_public_ip,
                                                internal_address=worker_internal_ip,
                                                user="opc",
                                                roles=["worker"])
                          ],
                          services_kube_proxy_deprecated=rke.ClusterServicesKubeProxyDeprecatedArgs(
                              extra_args={
                                "healthz-bind-address": "0.0.0.0"
                              }
                            ),
                          cluster_name="masterofclusters",
                          ssh_agent_auth=True,
                          ssh_key_path=ssh_key_path
                          )

rke_cluster.kube_config_yaml.apply(lambda a: write_kubeconfig(data=a))
