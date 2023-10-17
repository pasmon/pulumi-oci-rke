class TestMain(unittest.TestCase):
    def setUp(self):
        self.config = pulumi.Config()
        self.ssh_key_path = self.config.require("ssh-key-path")
        self.ssh_public_key_path = self.config.require("ssh-public-key-path")
        self.compartment_id = self.config.require("compartment-id")

    def tearDown(self):
        # Add cleanup actions here if any resources are created in setUp method
        pass

    def test_vcn_creation(self):
        vcn = main.create_vcn(self.compartment_id)
        self.assertIsInstance(vcn, oci.core.Vcn)
        self.assertEqual(vcn.cidr_blocks, ["10.0.0.0/16"])

    def test_internet_gateway_creation(self):
        vcn = main.create_vcn(self.compartment_id)
        internet_gateway = main.create_internet_gateway(self.compartment_id, vcn.id)
        self.assertIsInstance(internet_gateway, oci.core.InternetGateway)
        self.assertTrue(internet_gateway.enabled)

    def test_route_table_creation(self):
        vcn = main.create_vcn(self.compartment_id)
        internet_gateway = main.create_internet_gateway(self.compartment_id, vcn.id)
        route_table = main.create_route_table(self.compartment_id, vcn.default_route_table_id, internet_gateway.id)
        self.assertIsInstance(route_table, oci.core.DefaultRouteTable)

    def test_subnet_creation(self):
        vcn = main.create_vcn(self.compartment_id)
        route_table = main.create_route_table(self.compartment_id, vcn.default_route_table_id, internet_gateway.id)
        subnet = main.create_subnet(self.compartment_id, vcn.id, route_table.id)
        self.assertIsInstance(subnet, oci.core.Subnet)

    def test_security_group_creation(self):
        vcn = main.create_vcn(self.compartment_id)
        security_group = main.create_security_group(self.compartment_id, vcn.id)
        self.assertIsInstance(security_group, oci.core.NetworkSecurityGroup)

    def test_instance_creation(self):
        vcn = main.create_vcn(self.compartment_id)
        route_table = main.create_route_table(self.compartment_id, vcn.default_route_table_id, internet_gateway.id)
        subnet = main.create_subnet(self.compartment_id, vcn.id, route_table.id)
        security_group = main.create_security_group(self.compartment_id, vcn.id)
        instance = main.create_instance(self.compartment_id, subnet.id, security_group.id, self.ssh_public_key)
        self.assertIsInstance(instance, oci.core.Instance)

    def test_rke_cluster_creation(self):
        vcn = main.create_vcn(self.compartment_id)
        route_table = main.create_route_table(self.compartment_id, vcn.default_route_table_id, internet_gateway.id)
        subnet = main.create_subnet(self.compartment_id, vcn.id, route_table.id)
        security_group = main.create_security_group(self.compartment_id, vcn.id)
        instance = main.create_instance(self.compartment_id, subnet.id, security_group.id, self.ssh_public_key)
        rke_cluster = main.create_rke_cluster(instance.public_ip, instance.private_ip, self.ssh_key_path)
        self.assertIsInstance(rke_cluster, rke.Cluster)

if __name__ == '__main__':
    unittest.main()
