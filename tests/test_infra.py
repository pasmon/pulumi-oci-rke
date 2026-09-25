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
        outputs = dict(args.inputs)

        if args.name == "oci-master":
            outputs["public_ip"] = "203.0.113.10"
            outputs["private_ip"] = "10.0.0.10"
        elif args.name == "oci-worker":
            outputs["public_ip"] = "203.0.113.11"
            outputs["private_ip"] = "10.0.0.11"

        if args.typ == "command:remote:Command":
            outputs.setdefault("stdout", "")
            outputs.setdefault("stderr", "")
            if args.name == "rke2-kubeconfig":
                outputs["stdout"] = (
                    "apiVersion: v1\n"
                    "clusters:\n"
                    "- cluster:\n"
                    "    server: https://127.0.0.1:6443\n"
                    "  name: default\n"
                    "contexts: []\n"
                    "current-context: default\n"
                    "kind: Config\n"
                    "preferences: {}\n"
                    "users: []\n"
                )

        return [args.name + "_id", outputs]

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
        '"oci-rke-provision:rke2-token":"test-rke2-token",'
        '"oci-rke-provision:argocd-repo-url":"https://github.com/pasmon/pulumi-oci-rke.git",'
        '"oci-rke-provision:argocd-repo-target-revision":"main",'
        '"oci-rke-provision:argocd-repo-path":"gitops/bootstrap",'
        '"oci-rke-provision:argocd-repo-username":"git",'
        '"oci-rke-provision:argocd-repo-password":"test-password"}'
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
    assert (
        "AcceptEnv PULUMI_COMMAND_STDOUT PULUMI_COMMAND_STDERR"
        in pulumi_stack.USER_DATA
    )
    assert "sudo systemctl restart ssh" in pulumi_stack.USER_DATA
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


def test_rewrite_kubeconfig_server(pulumi_stack):
    """Test rewriting the kubeconfig server address."""
    kubeconfig = "server: https://127.0.0.1:6443\napiVersion: v1\n"
    assert (
        pulumi_stack.rewrite_kubeconfig_server(kubeconfig, "203.0.113.20")
        == "server: https://203.0.113.20:6443\napiVersion: v1\n"
    )


def test_argocd_repository_secret_builder(pulumi_stack):
    """Test Argo CD repository secret generation and validation."""
    https_secret = pulumi_stack.build_argocd_repository_secret_string_data(
        "https://github.com/pasmon/pulumi-oci-rke.git",
        repo_username="git",
        repo_password="token",
    )
    assert https_secret == {
        "type": "git",
        "url": "https://github.com/pasmon/pulumi-oci-rke.git",
        "username": "git",
        "password": "token",
    }

    ssh_secret = pulumi_stack.build_argocd_repository_secret_string_data(
        "git@github.com:pasmon/pulumi-oci-rke.git",
        repo_ssh_private_key="PRIVATE KEY",
    )
    assert ssh_secret == {
        "type": "git",
        "url": "git@github.com:pasmon/pulumi-oci-rke.git",
        "sshPrivateKey": "PRIVATE KEY",
    }

    assert (
        pulumi_stack.build_argocd_repository_secret_string_data(
            "https://github.com/pasmon/pulumi-oci-rke.git"
        )
        is None
    )

    with pytest.raises(
        ValueError, match="Set both argocd-repo-username and argocd-repo-password"
    ):
        pulumi_stack.build_argocd_repository_secret_string_data(
            "https://github.com/pasmon/pulumi-oci-rke.git",
            repo_username="git",
        )

    with pytest.raises(
        ValueError, match="Use either HTTPS credentials or an SSH private key"
    ):
        pulumi_stack.build_argocd_repository_secret_string_data(
            "https://github.com/pasmon/pulumi-oci-rke.git",
            repo_username="git",
            repo_password="token",
            repo_ssh_private_key="PRIVATE KEY",
        )


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
    assert pulumi_stack.argocd_provider is not None
    assert pulumi_stack.argocd_namespace is not None
    assert pulumi_stack.argocd_release is not None
    assert pulumi_stack.argocd_root_application is not None
    assert pulumi_stack.argocd_bootstrap_repo is not None


def test_argocd_config(pulumi_stack):
    """Test Argo CD bootstrap configuration defaults and constants."""
    assert (
        pulumi_stack.argocd_repo_url == "https://github.com/pasmon/pulumi-oci-rke.git"
    )
    assert pulumi_stack.argocd_repo_target_revision == "main"
    assert pulumi_stack.argocd_repo_path == "gitops/bootstrap"
    assert pulumi_stack.ARGOCD_NAMESPACE == "argocd"
    assert pulumi_stack.ARGOCD_HELM_CHART == "argo-cd"
    assert pulumi_stack.ARGOCD_HELM_REPO == "https://argoproj.github.io/argo-helm"
    assert pulumi_stack.ARGOCD_HELM_VERSION == "8.3.3"


def test_rke2_commands(pulumi_stack):
    """Test RKE2 server and agent command generation."""
    server = pulumi_stack.server_command("test-token", "203.0.113.20")
    agent = pulumi_stack.agent_command("test-token", "10.0.0.10")
    assert "INSTALL_RKE2_VERSION=v1.34.1+rke2r1" in server
    assert "sudo install -m 600 /dev/null /etc/rancher/rke2/config.yaml" in server
    assert "tls-san:" in server
    assert "203.0.113.20" in server
    assert 'write-kubeconfig-mode: "0600"' in server
    assert "sudo tee /etc/rancher/rke2/config.yaml >/dev/null" in server
    assert "rke2-server.service" in server
    assert "sudo install -m 600 /dev/null /etc/rancher/rke2/config.yaml" in agent
    assert "server: https://%s:9345" in agent
    assert "10.0.0.10" in agent
    assert "sudo tee /etc/rancher/rke2/config.yaml >/dev/null" in agent
    assert "rke2-agent.service" in agent


@pulumi.runtime.test
def test_argocd_provider_kubeconfig(pulumi_stack):
    """Test the Kubernetes provider uses the rewritten RKE2 kubeconfig."""
    return pulumi_stack.argocd_provider.kubeconfig.apply(
        assert_argocd_provider_kubeconfig
    )


def assert_argocd_provider_kubeconfig(kubeconfig):
    """Assert the Kubernetes provider is pointed at the public API endpoint."""
    assert "https://203.0.113.10:6443" in kubeconfig
    assert "127.0.0.1" not in kubeconfig


@pulumi.runtime.test
def test_argocd_release_values(pulumi_stack):
    """Test the Argo CD Helm release values."""
    return pulumi.Output.all(
        pulumi_stack.argocd_release.version,
        pulumi_stack.argocd_release.values,
        pulumi_stack.argocd_release.namespace,
    ).apply(check_argocd_release_values)


def check_argocd_release_values(values):
    """Assert the Argo CD Helm release configuration."""
    version, release_values, namespace = values
    assert version == "8.3.3"
    assert namespace == "argocd"
    assert release_values == {
        "crds": {"install": True},
        "server": {"service": {"type": "ClusterIP"}},
    }


@pulumi.runtime.test
def test_argocd_repository_secret(pulumi_stack):
    """Test the optional Argo CD bootstrap repository secret."""
    return pulumi.Output.all(
        pulumi_stack.argocd_bootstrap_repo.metadata,
        pulumi_stack.argocd_bootstrap_repo.string_data,
        pulumi_stack.argocd_bootstrap_repo.type,
    ).apply(check_argocd_repository_secret)


def check_argocd_repository_secret(values):
    """Assert the repository secret metadata and credentials."""
    metadata, string_data, secret_type = values
    assert metadata["name"] == "bootstrap-repo"
    assert metadata["namespace"] == "argocd"
    assert metadata["labels"] == {"argocd.argoproj.io/secret-type": "repository"}
    assert string_data == {
        "type": "git",
        "url": "https://github.com/pasmon/pulumi-oci-rke.git",
        "username": "git",
        "password": "test-password",
    }
    assert secret_type == "Opaque"


@pulumi.runtime.test
def test_argocd_root_application_spec(pulumi_stack):
    """Test the bootstrap root Application spec."""
    return pulumi_stack.argocd_root_application.spec.apply(
        check_argocd_root_application_spec
    )


def check_argocd_root_application_spec(spec):
    """Assert the seeded root Application configuration."""
    assert spec["project"] == "default"
    assert spec["source"] == {
        "repoURL": "https://github.com/pasmon/pulumi-oci-rke.git",
        "targetRevision": "main",
        "path": "gitops/bootstrap",
    }
    assert spec["destination"] == {
        "server": "https://kubernetes.default.svc",
        "namespace": "argocd",
    }
    assert spec["syncPolicy"] == {
        "automated": {"prune": True, "selfHeal": True},
        "syncOptions": ["CreateNamespace=true"],
    }


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


@pulumi.runtime.test
def test_rke2_ingress_rules(pulumi_stack):
    """Test the RKE2-specific ingress rule ports, protocols, and source CIDRs."""

    def check_rules(values):
        (
            rule3_protocol,
            rule3_source,
            rule3_tcp_options,
            rule4_protocol,
            rule4_source,
            rule4_tcp_options,
            rule5_protocol,
            rule5_source,
            rule5_tcp_options,
            rule6_protocol,
            rule6_source,
            rule6_udp_options,
        ) = values

        assert rule3_protocol == 6
        assert rule3_source == "10.0.0.0/16"
        assert rule3_tcp_options["destination_port_range"] == {"min": 9345, "max": 9345}

        assert rule4_protocol == 6
        assert rule4_source == "10.0.0.0/16"
        assert rule4_tcp_options["destination_port_range"] == {
            "min": 10250,
            "max": 10250,
        }

        assert rule5_protocol == 6
        assert rule5_source == "10.0.0.0/16"
        assert rule5_tcp_options["destination_port_range"] == {"min": 2379, "max": 2380}

        assert rule6_protocol == 17
        assert rule6_source == "10.0.0.0/16"
        assert rule6_udp_options["destination_port_range"] == {"min": 8472, "max": 8472}

    return pulumi.Output.all(
        pulumi_stack.security_group_security_rule3.protocol,
        pulumi_stack.security_group_security_rule3.source,
        pulumi_stack.security_group_security_rule3.tcp_options,
        pulumi_stack.security_group_security_rule4.protocol,
        pulumi_stack.security_group_security_rule4.source,
        pulumi_stack.security_group_security_rule4.tcp_options,
        pulumi_stack.security_group_security_rule5.protocol,
        pulumi_stack.security_group_security_rule5.source,
        pulumi_stack.security_group_security_rule5.tcp_options,
        pulumi_stack.security_group_security_rule6.protocol,
        pulumi_stack.security_group_security_rule6.source,
        pulumi_stack.security_group_security_rule6.udp_options,
    ).apply(check_rules)
