import unittest
from unittest import mock
import base64
import __main__ as main

class TestMain(unittest.TestCase):
    def setUp(self):
        self.ssh_key_data = "ssh-key-data"
        self.ssh_public_key = "ssh-public-key"
        self.user_data = main.USER_DATA
        self.user_data_base64 = base64.b64encode(self.user_data.encode("utf-8")).decode("utf-8")

    @mock.patch('builtins.open', new_callable=mock.mock_open, read_data="ssh-key-data")
    def test_read_ssh_keys(self, mock_open):
        with mock.patch('os.path.exists', return_value=True):
            ssh_key_data = main.read_ssh_key("ssh-key-path")
            self.assertEqual(ssh_key_data, self.ssh_key_data)

    def test_encode_user_data(self):
        encoded_user_data = main.encode_user_data(self.user_data)
        self.assertEqual(encoded_user_data, self.user_data_base64)

    @mock.patch('builtins.open', new_callable=mock.mock_open)
    def test_write_kubeconfig(self, mock_open):
        kubeconfig_data = "kubeconfig-data"
        main.write_kubeconfig(kubeconfig_data)
        mock_open.assert_called_once_with("out/rke_kubeconfig", "w", encoding="utf8")
        mock_open().write.assert_called_once_with(kubeconfig_data)

    @mock.patch('pulumi_oci.core.Vcn')
    @mock.patch('pulumi_oci.core.InternetGateway')
    @mock.patch('pulumi_oci.core.DefaultRouteTable')
    @mock.patch('pulumi_oci.core.Subnet')
    @mock.patch('pulumi_oci.core.NetworkSecurityGroup')
    @mock.patch('pulumi_oci.core.NetworkSecurityGroupSecurityRule')
    @mock.patch('pulumi_oci.core.Instance')
    @mock.patch('pulumi_command.remote.Command')
    @mock.patch('pulumi_rke.Cluster')
    def test_main(self, mock_cluster, mock_command, mock_instance, mock_security_rule, mock_security_group, mock_subnet, mock_route_table, mock_internet_gateway, mock_vcn):
        main.main()
        mock_subnet.assert_called_once_with(
            "oci-subnet",
            cidr_block="10.0.0.0/24",
            compartment_id=compartment_id,
            vcn_id=vcn.id,
            route_table_id=route_table.id,
        )
        mock_security_group.assert_called_once_with(
            "oci-securitygroup",
            compartment_id=compartment_id,
            vcn_id=vcn.id,
            display_name="oci-security-group",
        )
        mock_security_rule.assert_called_once_with(
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
        mock_instance.assert_called_once_with(
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
                "user_data": USER_DATA_BASE64,
            },
            opts=pulumi.ResourceOptions(delete_before_replace=True),
        )
        assert mock_command.call_count == 2
        assert mock_cluster.call_count == 1

    def tearDown(self):
        pass

if __name__ == "__main__":
    unittest.main()
