"""Unit tests for Pulumi OCI RKE provisioning program."""

# pylint: disable=redefined-outer-name

import asyncio
import base64
import importlib.util
import os
import shutil
import tempfile

import pulumi
import pytest


class PulumiMocks(pulumi.runtime.Mocks):
    """Mocks for Pulumi engine during unit tests."""

    def new_resource(self, args: pulumi.runtime.MockResourceArgs):
        return [args.name + "_id", args.inputs]

    def call(self, args: pulumi.runtime.MockCallArgs):
        return {}


@pytest.fixture(scope="session")
def pulumi_stack():
    """Fixture that initializes Pulumi with mocks and loads the stack from __main__.py."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    temp_dir = tempfile.mkdtemp()
    ssh_key_path = os.path.join(temp_dir, "test_id_rsa")
    ssh_pub_key_path = os.path.join(temp_dir, "test_id_rsa.pub")

    with open(ssh_key_path, "w", encoding="utf-8") as f:
        f.write("dummy-private-key-data")
    with open(ssh_pub_key_path, "w", encoding="utf-8") as f:
        f.write("dummy-public-key-data")

    os.environ["PULUMI_CONFIG"] = (
        '{"oci-rke-provision:ssh-key-path":"'
        + ssh_key_path.replace("\\", "\\\\")
        + '",'
        '"oci-rke-provision:ssh-public-key-path":"'
        + ssh_pub_key_path.replace("\\", "\\\\")
        + '",'
        '"oci-rke-provision:compartment-id":"ocid1.compartment.oc1..test",'
        '"oci-rke-provision:rke2-version":"v1.34.1+rke2r1",'
        '"oci-rke-provision:rke2-token":"test-rke2-token"}'
    )

    pulumi.runtime.set_mocks(PulumiMocks(), project="oci-rke-provision", stack="test")

    spec = importlib.util.spec_from_file_location(
        "main", os.path.abspath("__main__.py")
    )
    infra = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(infra)

    yield infra

    shutil.rmtree(temp_dir, ignore_errors=True)
    if os.path.exists("out/rke2_kubeconfig"):
        try:
            os.remove("out/rke2_kubeconfig")
        except OSError:
            pass


def test_user_data_configuration(pulumi_stack):
    """Test user_data script generation and base64 encoding."""
    assert "sudo iptables -F" in pulumi_stack.USER_DATA
    assert "AllowTcpForwarding yes" in pulumi_stack.USER_DATA
    assert "ca-certificates curl" in pulumi_stack.USER_DATA
    assert "docker-ce" not in pulumi_stack.USER_DATA

    decoded = base64.b64decode(pulumi_stack.USER_DATA_BASE64).decode("utf-8")
    assert decoded == pulumi_stack.USER_DATA


def test_write_kubeconfig(pulumi_stack, tmp_path, monkeypatch):
    """Test write_kubeconfig helper handles none and writes data properly."""
    monkeypatch.chdir(tmp_path)

    # Test None data does not create file
    pulumi_stack.write_kubeconfig(None, "203.0.113.10")
    assert os.path.exists(tmp_path / "out")
    assert not os.path.exists(tmp_path / "out" / "rke2_kubeconfig")

    # Test writing valid kubeconfig content
    content = "server: https://127.0.0.1:6443\napiVersion: v1\nclusters: []"
    pulumi_stack.write_kubeconfig(content, "203.0.113.10")
    assert os.path.exists(tmp_path / "out" / "rke2_kubeconfig")
    with open(tmp_path / "out" / "rke2_kubeconfig", "r", encoding="utf-8") as f:
        assert f.read() == content.replace("127.0.0.1", "203.0.113.10")


def test_network_resources(pulumi_stack):
    """Test VCN, Internet Gateway, Subnet, and Security Group creation."""
    assert pulumi_stack.vcn is not None
    assert pulumi_stack.internet_gateway is not None
    assert pulumi_stack.subnet is not None
    assert pulumi_stack.security_group is not None
    assert pulumi_stack.security_group_security_rule is not None
    assert pulumi_stack.security_group_security_rule2 is not None
    assert pulumi_stack.security_group_security_rule3 is not None
    assert pulumi_stack.security_group_security_rule4 is not None
    assert pulumi_stack.security_group_security_rule5 is not None
    assert pulumi_stack.security_group_security_rule6 is not None


def test_compute_instances(pulumi_stack):
    """Test master and worker compute instances configuration."""
    assert pulumi_stack.vm1 is not None
    assert pulumi_stack.vm2 is not None
    assert pulumi_stack.vm1_ready is not None
    assert pulumi_stack.vm2_ready is not None
    assert pulumi_stack.vm1_config["name"] == "oci-master"
    assert pulumi_stack.vm2_config["name"] == "oci-worker"


def test_rke2_cluster_config(pulumi_stack):
    """Test RKE2 server, agent, and kubeconfig resources."""
    assert pulumi_stack.rke2_server is not None
    assert pulumi_stack.rke2_agent is not None
    assert pulumi_stack.rke2_kubeconfig is not None


def test_rke2_commands(pulumi_stack):
    """Test RKE2 server and agent command generation."""
    server = pulumi_stack.server_command("test-token", "203.0.113.20")
    agent = pulumi_stack.agent_command("test-token", "10.0.0.10")
    assert "INSTALL_RKE2_VERSION=v1.34.1+rke2r1" in server
    assert "tls-san:" in server
    assert "203.0.113.20" in server
    assert "rke2-server.service" in server
    assert "server: https://%s:9345" in agent
    assert "10.0.0.10" in agent
    assert "rke2-agent.service" in agent


@pulumi.runtime.test
def test_vcn_cidr(pulumi_stack):
    """Test VCN CIDR block configuration via Pulumi Output."""

    def check_cidr(cidr_blocks):
        assert cidr_blocks == ["10.0.0.0/16"]

    return pulumi_stack.vcn.cidr_blocks.apply(check_cidr)


@pulumi.runtime.test
def test_subnet_cidr(pulumi_stack):
    """Test Subnet CIDR block configuration via Pulumi Output."""

    def check_subnet(cidr):
        assert cidr == "10.0.0.0/24"

    return pulumi_stack.subnet.cidr_block.apply(check_subnet)


@pulumi.runtime.test
def test_rke2_version(pulumi_stack):
    """Test the configured RKE2 release."""
    assert pulumi_stack.rke2_version == "v1.34.1+rke2r1"
