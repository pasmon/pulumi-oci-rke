import os
import base64

import pulumi
from pulumi_command import remote
import pulumi_oci as oci
import pulumi_rke as rke

config = pulumi.Config()
ssh_key_path = config.require("ssh-key-path")
ssh_public_key_path = config.require("ssh-public-key-path")
compartment_id = config.require("compartment-id")

with open(ssh_key_path, "r") as ssh_key_file:
    ssh_key_data = ssh_key_file.read()

with open(ssh_public_key_path, "r") as ssh_public_file:
    ssh_public_key = ssh_public_file.read()

# install docker and do modifications for rke installation
user_data = """#!/bin/bash -x
sudo apt-get remove -y ufw
sudo iptables -F
sudo netfilter-persistent save
sudo apt-get install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu focal stable"
sudo apt-get update
#sudo apt-cache policy docker-ce
sudo apt-get install -y docker.io
sudo usermod -aG docker ubuntu
sudo sysctl -w net.bridge.bridge-nf-call-iptables=1
sudo sysctl -p
echo 'AllowTcpForwarding yes' | sudo tee -a /etc/ssh/sshd_config
"""
encodedBytes = base64.b64encode(user_data.encode("utf-8"))
user_data_base64 = str(encodedBytes, "utf-8")

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
            max=10250,
            min=10250,
        ),
    ),
)

# TODO: allow from specific ips
security_group_security_rule3 = oci.core.NetworkSecurityGroupSecurityRule(
    "oci-securitygroup-rule3",
    network_security_group_id=security_group.id,
    direction="INGRESS",
    protocol=6,
    source="0.0.0.0/0",
    source_type="CIDR_BLOCK",
    tcp_options=oci.core.NetworkSecurityGroupSecurityRuleTcpOptionsArgs(
        destination_port_range=oci.core.NetworkSecurityGroupSecurityRuleTcpOptionsDestinationPortRangeArgs(
            max=2379,
            min=2379,
        ),
    ),
)

security_group_security_rule4 = oci.core.NetworkSecurityGroupSecurityRule(
    "oci-securitygroup-rule4",
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

# TODO: update source_id for ubuntu 22.04
vm1 = oci.core.Instance(
    "oci-master",
    display_name="k8s-master",
    availability_domain="Dtqv:EU-STOCKHOLM-1-AD-1",
    compartment_id=compartment_id,
    shape="VM.Standard.A1.Flex",
    create_vnic_details=oci.core.InstanceCreateVnicDetailsArgs(
        subnet_id=subnet.id,
        nsg_ids=[security_group.id],
    ),
    source_details=oci.core.InstanceSourceDetailsArgs(
        source_id="ocid1.image.oc1.eu-stockholm-1.aaaaaaaaicyhmukvotwdsfxgwk73p2z3kk344bxbg2ycwltyyktw26hz3kna",
        source_type="image",
    ),
    shape_config=oci.core.InstanceShapeConfigArgs(
        memory_in_gbs=12,
        ocpus=2,
    ),
    metadata={
        "ssh_authorized_keys": ssh_public_key,
        "user_data": user_data_base64,
    },
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

vm2 = oci.core.Instance(
    "oci-worker",
    display_name="k8s-worker",
    availability_domain="Dtqv:EU-STOCKHOLM-1-AD-1",
    compartment_id=compartment_id,
    shape="VM.Standard.A1.Flex",
    create_vnic_details=oci.core.InstanceCreateVnicDetailsArgs(
        subnet_id=subnet.id,
        nsg_ids=[security_group.id],
    ),
    source_details=oci.core.InstanceSourceDetailsArgs(
        source_id="ocid1.image.oc1.eu-stockholm-1.aaaaaaaaicyhmukvotwdsfxgwk73p2z3kk344bxbg2ycwltyyktw26hz3kna",
        source_type="image",
    ),
    shape_config=oci.core.InstanceShapeConfigArgs(
        memory_in_gbs=12,
        ocpus=2,
    ),
    metadata={
        "ssh_authorized_keys": ssh_public_key,
        "user_data": user_data_base64,
    },
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

# TODO: parametrize user
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


def write_kubeconfig(data):
    """Write kubeconfig from RKE to 'out' directory."""
    if not os.path.exists("out"):
        os.mkdir("out")
    if data is not None:
        with open("out/rke_kubeconfig", "w", encoding="utf8") as kubeconfig:
            kubeconfig.write(data)


rke_cluster = rke.Cluster(
    "masterofclusters",
    nodes=[
        rke.ClusterNodeArgs(
            hostname_override="master",
            address=vm1.public_ip,
            internal_address=vm1.private_ip,
            user="ubuntu",
            roles=["controlplane", "etcd", "worker"],
        ),
        rke.ClusterNodeArgs(
            hostname_override="worker",
            address=vm2.public_ip,
            internal_address=vm2.private_ip,
            user="ubuntu",
            roles=["worker"],
        ),
    ],
    services_kube_proxy_deprecated=rke.ClusterServicesKubeProxyDeprecatedArgs(
        extra_args={"healthz-bind-address": "0.0.0.0"}
    ),
    cluster_name="masterofclusters",
    ssh_agent_auth=False,
    ssh_key_path=ssh_key_path,
    # fix the images to work with arm64
    system_images=rke.ClusterSystemImagesArgs(
        calico_node="rancher/mirrored-calico-node:v3.22.1",
        calico_cni="rancher/mirrored-calico-cni:v3.22.1",
        calico_controllers="rancher/mirrored-calico-kube-controllers:v3.22.1",
        calico_flex_vol="rancher/mirrored-calico-pod2daemon-flexvol:v3.22.1",
        calico_ctl="rancher/mirrored-calico-ctl:v3.22.1",
        canal_cni="rancher/mirrored-calico-cni:v3.22.1",
        canal_node="rancher/mirrored-calico-node:v3.22.1",
        canal_flex_vol="rancher/mirrored-calico-pod2daemon-flexvol:v3.22.1",
    ),
    opts=pulumi.ResourceOptions(depends_on=[vm1_ready, vm2_ready]),
)

rke_cluster.kube_config_yaml.apply(lambda a: write_kubeconfig(data=a))

pulumi.export("images", rke_cluster.running_system_images)
pulumi.export("state", rke_cluster.rke_state)
