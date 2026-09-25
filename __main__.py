"""Pulumi program to deploy an RKE2 cluster to two free-tier OCI nodes."""

import base64
import os
import shlex

import pulumi
import pulumi_kubernetes as k8s
import pulumi_oci as oci
from pulumi_command import remote

config = pulumi.Config()
ssh_key_path = config.require("ssh-key-path")
ssh_public_key_path = config.require("ssh-public-key-path")
compartment_id = config.require("compartment-id")
rke2_version = config.require("rke2-version")
rke2_token = config.require_secret("rke2-token")
argocd_repo_url = config.require("argocd-repo-url")
argocd_repo_target_revision = config.get("argocd-repo-target-revision") or "main"
argocd_repo_path = config.get("argocd-repo-path") or "gitops/bootstrap"
argocd_repo_username = config.get("argocd-repo-username")
argocd_repo_password = config.get_secret("argocd-repo-password")
argocd_repo_ssh_private_key = config.get_secret("argocd-repo-ssh-private-key")

ARGOCD_NAMESPACE = "argocd"
ARGOCD_HELM_REPO = "https://argoproj.github.io/argo-helm"
ARGOCD_HELM_CHART = "argo-cd"
ARGOCD_HELM_VERSION = "8.3.3"

with open(ssh_key_path, "r", encoding="utf-8") as ssh_key_file:
    ssh_key_data = ssh_key_file.read()

with open(ssh_public_key_path, "r", encoding="utf-8") as ssh_public_file:
    ssh_public_key = ssh_public_file.read()

USER_DATA = """#!/bin/bash -x
sudo iptables -F
sudo netfilter-persistent save
sudo apt-get update
sudo apt-get install -y ca-certificates curl
echo 'AllowTcpForwarding yes' | sudo tee -a /etc/ssh/sshd_config
echo 'AcceptEnv PULUMI_COMMAND_STDOUT PULUMI_COMMAND_STDERR' | sudo tee -a /etc/ssh/sshd_config
sudo systemctl restart ssh
"""
encodedBytes = base64.b64encode(USER_DATA.encode("utf-8"))
USER_DATA_BASE64 = str(encodedBytes, "utf-8")

# TODO: lookup compartment_id
vcn = oci.core.Vcn(
    "oci-vcn",
    compartment_id=compartment_id,
    cidr_blocks=["10.0.0.0/16"],
)

internet_gateway = oci.core.InternetGateway(
    "oci-internetgateway",
    compartment_id=compartment_id,
    vcn_id=vcn.id,
    enabled=True,
)

route_table = oci.core.DefaultRouteTable(
    "oci-routetable",
    compartment_id=compartment_id,
    manage_default_resource_id=vcn.default_route_table_id,
    route_rules=[
        oci.core.DefaultRouteTableRouteRuleArgs(
            network_entity_id=internet_gateway.id,
            destination="0.0.0.0/0",
        )
    ],
    opts=pulumi.ResourceOptions(depends_on=vcn),
)

subnet = oci.core.Subnet(
    "oci-subnet",
    cidr_block="10.0.0.0/24",
    compartment_id=compartment_id,
    vcn_id=vcn.id,
    route_table_id=route_table.id,
)

security_group = oci.core.NetworkSecurityGroup(
    "oci-securitygroup",
    compartment_id=compartment_id,
    vcn_id=vcn.id,
    display_name="oci-security-group",
)

security_group_security_rule = oci.core.NetworkSecurityGroupSecurityRule(
    "oci-securitygroup-rule",
    network_security_group_id=security_group.id,
    direction="INGRESS",
    protocol=6,
    source="0.0.0.0/0",
    source_type="CIDR_BLOCK",
    tcp_options=oci.core.NetworkSecurityGroupSecurityRuleTcpOptionsArgs(
        destination_port_range=oci.core.NetworkSecurityGroupSecurityRuleTcpOptionsDestinationPortRangeArgs(
            max=22,
            min=22,
        ),
    ),
)

security_group_security_rule2 = oci.core.NetworkSecurityGroupSecurityRule(
    "oci-securitygroup-rule2",
    network_security_group_id=security_group.id,
    direction="INGRESS",
    protocol=6,
    source="0.0.0.0/0",
    source_type="CIDR_BLOCK",
    tcp_options=oci.core.NetworkSecurityGroupSecurityRuleTcpOptionsArgs(
        destination_port_range=oci.core.NetworkSecurityGroupSecurityRuleTcpOptionsDestinationPortRangeArgs(
            max=6443,
            min=6443,
        ),
    ),
)

# TODO: allow from specific ips
security_group_security_rule3 = oci.core.NetworkSecurityGroupSecurityRule(
    "oci-securitygroup-rule3",
    network_security_group_id=security_group.id,
    direction="INGRESS",
    protocol=6,
    source="10.0.0.0/16",
    source_type="CIDR_BLOCK",
    tcp_options=oci.core.NetworkSecurityGroupSecurityRuleTcpOptionsArgs(
        destination_port_range=oci.core.NetworkSecurityGroupSecurityRuleTcpOptionsDestinationPortRangeArgs(
            max=9345,
            min=9345,
        ),
    ),
)

security_group_security_rule4 = oci.core.NetworkSecurityGroupSecurityRule(
    "oci-securitygroup-rule4",
    network_security_group_id=security_group.id,
    direction="INGRESS",
    protocol=6,
    source="10.0.0.0/16",
    source_type="CIDR_BLOCK",
    tcp_options=oci.core.NetworkSecurityGroupSecurityRuleTcpOptionsArgs(
        destination_port_range=oci.core.NetworkSecurityGroupSecurityRuleTcpOptionsDestinationPortRangeArgs(
            max=10250,
            min=10250,
        ),
    ),
)

security_group_security_rule5 = oci.core.NetworkSecurityGroupSecurityRule(
    "oci-securitygroup-rule5",
    network_security_group_id=security_group.id,
    direction="INGRESS",
    protocol=6,
    source="10.0.0.0/16",
    source_type="CIDR_BLOCK",
    tcp_options=oci.core.NetworkSecurityGroupSecurityRuleTcpOptionsArgs(
        destination_port_range=oci.core.NetworkSecurityGroupSecurityRuleTcpOptionsDestinationPortRangeArgs(
            max=2380,
            min=2379,
        ),
    ),
)

security_group_security_rule6 = oci.core.NetworkSecurityGroupSecurityRule(
    "oci-securitygroup-rule6",
    network_security_group_id=security_group.id,
    direction="INGRESS",
    protocol=17,
    source="10.0.0.0/16",
    source_type="CIDR_BLOCK",
    udp_options=oci.core.NetworkSecurityGroupSecurityRuleUdpOptionsArgs(
        destination_port_range=oci.core.NetworkSecurityGroupSecurityRuleUdpOptionsDestinationPortRangeArgs(
            max=8472,
            min=8472,
        ),
    ),
)


def create_instance(instance_config):
    """
    Create an instance in Oracle Cloud Infrastructure (OCI).

    Args:
        instance_config (dict): A dictionary containing the configuration for the instance.

    Returns:
        oci.core.Instance: The created instance.
    """
    return oci.core.Instance(
        instance_config["name"],
        display_name=instance_config["display_name"],
        availability_domain="Dtqv:EU-STOCKHOLM-1-AD-1",
        compartment_id=compartment_id,
        shape="VM.Standard.A1.Flex",
        create_vnic_details=oci.core.InstanceCreateVnicDetailsArgs(
            subnet_id=instance_config["subnet_id"],
            nsg_ids=[instance_config["security_group_id"]],
        ),
        source_details=oci.core.InstanceSourceDetailsArgs(
            source_id="ocid1.image.oc1.eu-stockholm-1.aaaaaaaai7jn6m3ethcud7hivw4ad32st7f7l24xqqmvigqfco5zffceqj3q",
            source_type="image",
        ),
        shape_config=oci.core.InstanceShapeConfigArgs(
            memory_in_gbs=12,
            ocpus=2,
        ),
        metadata={
            "ssh_authorized_keys": instance_config["ssh_public_key"],
            "user_data": instance_config["user_data_base64"],
        },
        opts=pulumi.ResourceOptions(delete_before_replace=True),
    )


vm1_config = {
    "name": "oci-master",
    "display_name": "k8s-master",
    "subnet_id": subnet.id,
    "security_group_id": security_group.id,
    "ssh_public_key": ssh_public_key,
    "user_data_base64": USER_DATA_BASE64,
}
vm1 = create_instance(vm1_config)

vm2_config = {
    "name": "oci-worker",
    "display_name": "k8s-worker",
    "subnet_id": subnet.id,
    "security_group_id": security_group.id,
    "ssh_public_key": ssh_public_key,
    "user_data_base64": USER_DATA_BASE64,
}
vm2 = create_instance(vm2_config)
# let's wait for VMs to run their cloud init to completion
vm1_ready = remote.Command(
    "vm1-ready",
    connection=remote.ConnectionArgs(
        host=vm1.public_ip,
        private_key=ssh_key_data,
        user="ubuntu",
    ),
    create="cloud-init status --wait",
)

vm2_ready = remote.Command(
    "vm2-ready",
    connection=remote.ConnectionArgs(
        host=vm2.public_ip,
        private_key=ssh_key_data,
        user="ubuntu",
    ),
    create="cloud-init status --wait",
)


def write_kubeconfig(data, server_address):
    """Write kubeconfig from RKE2 to 'out' directory."""
    if not os.path.exists("out"):
        os.mkdir("out")
    if data is not None:
        with open("out/rke2_kubeconfig", "w", encoding="utf8") as kubeconfig:
            kubeconfig.write(rewrite_kubeconfig_server(data, server_address))


def rewrite_kubeconfig_server(data, server_address):
    """Rewrite the loopback API endpoint in the kubeconfig."""
    if data is None or server_address is None:
        return data
    return data.replace("127.0.0.1", server_address)


def build_argocd_repository_secret_string_data(
    repo_url, repo_username=None, repo_password=None, repo_ssh_private_key=None
):
    """Build the optional Argo CD repository secret payload."""
    if repo_ssh_private_key is not None and (
        repo_username is not None or repo_password is not None
    ):
        raise ValueError(
            "Use either HTTPS credentials or an SSH private key for Argo CD repository access, not both."
        )
    if (repo_username is None) != (repo_password is None):
        raise ValueError(
            "Set both argocd-repo-username and argocd-repo-password, or neither."
        )
    if repo_ssh_private_key is not None:
        return {
            "type": "git",
            "url": repo_url,
            "sshPrivateKey": repo_ssh_private_key,
        }
    if repo_username is not None and repo_password is not None:
        return {
            "type": "git",
            "url": repo_url,
            "username": repo_username,
            "password": repo_password,
        }
    return None


def server_command(token, server_address):
    """Build the RKE2 server installation command."""
    return f"""set -eu
curl -sfL https://get.rke2.io | sudo INSTALL_RKE2_VERSION={shlex.quote(rke2_version)} sh -
sudo mkdir -p /etc/rancher/rke2
sudo install -m 600 /dev/null /etc/rancher/rke2/config.yaml
printf 'token: %s\\nnode-name: master\\nwrite-kubeconfig-mode: "0600"\\ntls-san:\\n  - %s\\n' \
    {shlex.quote(token)} {shlex.quote(server_address)} | sudo tee /etc/rancher/rke2/config.yaml >/dev/null
sudo systemctl enable rke2-server.service
sudo systemctl start rke2-server.service
sudo systemctl is-active --wait rke2-server.service
"""


def agent_command(token, server_address):
    """Build the RKE2 agent installation command."""
    return f"""set -eu
curl -sfL https://get.rke2.io | sudo INSTALL_RKE2_TYPE=agent INSTALL_RKE2_VERSION={shlex.quote(rke2_version)} sh -
sudo mkdir -p /etc/rancher/rke2
sudo install -m 600 /dev/null /etc/rancher/rke2/config.yaml
printf 'server: https://%s:9345\\ntoken: %s\\nnode-name: worker\\n' \
    {shlex.quote(server_address)} {shlex.quote(token)} | sudo tee /etc/rancher/rke2/config.yaml >/dev/null
sudo systemctl enable rke2-agent.service
sudo systemctl start rke2-agent.service
sudo systemctl is-active --wait rke2-agent.service
"""


rke2_server = remote.Command(
    "rke2-server",
    connection=remote.ConnectionArgs(
        host=vm1.public_ip,
        private_key=ssh_key_data,
        user="ubuntu",
    ),
    create=pulumi.Output.all(rke2_token, vm1.public_ip).apply(
        lambda values: server_command(values[0], values[1])
    ),
    opts=pulumi.ResourceOptions(depends_on=[vm1_ready]),
)

rke2_agent = remote.Command(
    "rke2-agent",
    connection=remote.ConnectionArgs(
        host=vm2.public_ip,
        private_key=ssh_key_data,
        user="ubuntu",
    ),
    create=pulumi.Output.all(rke2_token, vm1.private_ip).apply(
        lambda values: agent_command(values[0], values[1])
    ),
    opts=pulumi.ResourceOptions(depends_on=[vm2_ready, rke2_server]),
)

rke2_kubeconfig = remote.Command(
    "rke2-kubeconfig",
    connection=remote.ConnectionArgs(
        host=vm1.public_ip,
        private_key=ssh_key_data,
        user="ubuntu",
    ),
    create="sudo cat /etc/rancher/rke2/rke2.yaml",
    opts=pulumi.ResourceOptions(
        additional_secret_outputs=["stdout"], depends_on=[rke2_agent]
    ),
)

rke2_kubeconfig.stdout.apply(
    lambda data: pulumi.Output.all(data, vm1.public_ip).apply(
        lambda values: write_kubeconfig(values[0], values[1])
    )
)

bootstrap_kubeconfig = pulumi.Output.all(rke2_kubeconfig.stdout, vm1.public_ip).apply(
    lambda values: rewrite_kubeconfig_server(values[0], values[1])
)

argocd_provider = k8s.Provider(
    "rke2-kubernetes",
    kubeconfig=bootstrap_kubeconfig,
    enable_server_side_apply=True,
    opts=pulumi.ResourceOptions(depends_on=[rke2_kubeconfig]),
)

argocd_namespace = k8s.core.v1.Namespace(
    "argocd-namespace",
    metadata={"name": ARGOCD_NAMESPACE},
    opts=pulumi.ResourceOptions(provider=argocd_provider),
)

argocd_release = k8s.helm.v3.Release(
    "argocd",
    chart=ARGOCD_HELM_CHART,
    version=ARGOCD_HELM_VERSION,
    namespace=ARGOCD_NAMESPACE,
    repository_opts=k8s.helm.v3.RepositoryOptsArgs(repo=ARGOCD_HELM_REPO),
    values={
        "crds": {"install": True},
        "server": {"service": {"type": "ClusterIP"}},
    },
    opts=pulumi.ResourceOptions(
        provider=argocd_provider, depends_on=[argocd_namespace]
    ),
)

argocd_bootstrap_repo_secret_string_data = build_argocd_repository_secret_string_data(
    repo_url=argocd_repo_url,
    repo_username=argocd_repo_username,
    repo_password=argocd_repo_password,
    repo_ssh_private_key=argocd_repo_ssh_private_key,
)

argocd_bootstrap_repo = None
if argocd_bootstrap_repo_secret_string_data is not None:
    argocd_bootstrap_repo = k8s.core.v1.Secret(
        "argocd-bootstrap-repo",
        metadata={
            "name": "bootstrap-repo",
            "namespace": ARGOCD_NAMESPACE,
            "labels": {
                "argocd.argoproj.io/secret-type": "repository",
            },
        },
        string_data=argocd_bootstrap_repo_secret_string_data,
        type="Opaque",
        opts=pulumi.ResourceOptions(
            provider=argocd_provider, depends_on=[argocd_namespace]
        ),
    )

argocd_root_application_dependencies = [argocd_release]
if argocd_bootstrap_repo is not None:
    argocd_root_application_dependencies.append(argocd_bootstrap_repo)

argocd_root_application = k8s.apiextensions.CustomResource(
    "argocd-root-application",
    api_version="argoproj.io/v1alpha1",
    kind="Application",
    metadata={"name": "bootstrap-root", "namespace": ARGOCD_NAMESPACE},
    spec={
        "project": "default",
        "source": {
            "repoURL": argocd_repo_url,
            "targetRevision": argocd_repo_target_revision,
            "path": argocd_repo_path,
        },
        "destination": {
            "server": "https://kubernetes.default.svc",
            "namespace": ARGOCD_NAMESPACE,
        },
        "syncPolicy": {
            "automated": {
                "prune": True,
                "selfHeal": True,
            },
            "syncOptions": ["CreateNamespace=true"],
        },
    },
    opts=pulumi.ResourceOptions(
        provider=argocd_provider, depends_on=argocd_root_application_dependencies
    ),
)

pulumi.export("master_pip", vm1.public_ip)
pulumi.export("worker_pip", vm2.public_ip)
pulumi.export("rke2_version", rke2_version)
pulumi.export("argocd_namespace", ARGOCD_NAMESPACE)
pulumi.export("argocd_bootstrap_application", argocd_root_application.metadata["name"])
