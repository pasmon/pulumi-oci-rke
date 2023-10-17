import unittest
import pulumi
from pulumi_command import remote
import pulumi_oci as oci
import pulumi_rke as rke
import __main__ as main

class TestMain(unittest.TestCase):

    def test_vcn_creation(self):
        vcn = oci.core.Vcn("oci-vcn", compartment_id="compartment_id", cidr_blocks=["10.0.0.0/16"])
        self.assertIsInstance(vcn, oci.core.Vcn)
        self.assertEqual(vcn.cidr_blocks, ["10.0.0.0/16"])

    def test_internet_gateway_creation(self):
        internet_gateway = oci.core.InternetGateway("oci-internetgateway", compartment_id="compartment_id", vcn_id="vcn_id", enabled=True)
        self.assertIsInstance(internet_gateway, oci.core.InternetGateway)
        self.assertTrue(internet_gateway.enabled)

    def test_route_table_creation(self):
        route_table = oci.core.DefaultRouteTable("oci-routetable", compartment_id="compartment_id", manage_default_resource_id="vcn.default_route_table_id", route_rules=[oci.core.DefaultRouteTableRouteRuleArgs(network_entity_id="internet_gateway.id", destination="0.0.0.0/0")])
        self.assertIsInstance(route_table, oci.core.DefaultRouteTable)

    def test_subnet_creation(self):
        subnet = oci.core.Subnet("oci-subnet", cidr_block="10.0.0.0/24", compartment_id="compartment_id", vcn_id="vcn.id", route_table_id="route_table.id")
        self.assertIsInstance(subnet, oci.core.Subnet)

    def test_security_group_creation(self):
        security_group = oci.core.NetworkSecurityGroup("oci-securitygroup", compartment_id="compartment_id", vcn_id="vcn.id", display_name="oci-security-group")
        self.assertIsInstance(security_group, oci.core.NetworkSecurityGroup)

    def test_instance_creation(self):
        instance = oci.core.Instance("oci-master", display_name="k8s-master", availability_domain="Dtqv:EU-STOCKHOLM-1-AD-1", compartment_id="compartment_id", shape="VM.Standard.A1.Flex", create_vnic_details=oci.core.InstanceCreateVnicDetailsArgs(subnet_id="subnet.id", nsg_ids=["security_group.id"]), source_details=oci.core.InstanceSourceDetailsArgs(source_id="ocid1.image.oc1.eu-stockholm-1.aaaaaaaaicyhmukvotwdsfxgwk73p2z3kk344bxbg2ycwltyyktw26hz3kna", source_type="image"), shape_config=oci.core.InstanceShapeConfigArgs(memory_in_gbs=12, ocpus=2), metadata={"ssh_authorized_keys": "ssh_public_key", "user_data": "USER_DATA_BASE64"})
        self.assertIsInstance(instance, oci.core.Instance)

    def test_rke_cluster_creation(self):
        rke_cluster = rke.Cluster("masterofclusters", nodes=[rke.ClusterNodeArgs(hostname_override="master", address="vm1.public_ip", internal_address="vm1.private_ip", user="ubuntu", roles=["controlplane", "etcd", "worker"]), rke.ClusterNodeArgs(hostname_override="worker", address="vm2.public_ip", internal_address="vm2.private_ip", user="ubuntu", roles=["worker"])], services_kube_proxy_deprecated=rke.ClusterServicesKubeProxyDeprecatedArgs(extra_args={"healthz-bind-address": "0.0.0.0"}), cluster_name="masterofclusters", ssh_agent_auth=False, ssh_key_path="ssh_key_path", system_images=rke.ClusterSystemImagesArgs(calico_node="rancher/mirrored-calico-node:v3.22.1", calico_cni="rancher/mirrored-calico-cni:v3.22.1", calico_controllers="rancher/mirrored-calico-kube-controllers:v3.22.1", calico_flex_vol="rancher/mirrored-calico-pod2daemon-flexvol:v3.22.1", calico_ctl="rancher/mirrored-calico-ctl:v3.22.1", canal_cni="rancher/mirrored-calico-cni:v3.22.1", canal_node="rancher/mirrored-calico-node:v3.22.1", canal_flex_vol="rancher/mirrored-calico-pod2daemon-flexvol:v3.22.1"))
        self.assertIsInstance(rke_cluster, rke.Cluster)

if __name__ == '__main__':
    unittest.main()
