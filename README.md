![Pipeline Status](https://github.com/pasmon/pulumi-oci-rke/actions/workflows/ci-pipeline.yml/badge.svg)
# Provision Kubernetes Cluster (RKE2) To Oracle Cloud Infrastructure

This project provisions a two-node RKE2 cluster directly on Oracle Cloud
Infrastructure ARM instances. The previous RKE1 cluster was disposable and is
replaced by this deployment rather than upgraded in place.

## Requirements

- Oracle Cloud Infrastructure account
- Python
  - uv
- Pulumi

## Install Rancher Kubernetes Engine 2 (RKE2)

1. Create account to Oracle Cloud for free:

   https://www.oracle.com/cloud/free/

2. Setup OCI credentials:

   https://docs.oracle.com/en-us/iaas/Content/API/Concepts/apisigningkey.htm#Required_Keys_and_OCIDs

3. Install Pulumi:

   https://www.pulumi.com/docs/get-started/install/

4. Install uv (https://docs.astral.sh/uv/getting-started/installation/) and the Python dependencies:

    `uv sync --locked`

5. Activate the virtual environment created by uv:

    `source .venv/bin/activate`

6. Set the OCI compartment ID, SSH key paths, an RKE2 release, and a private
   cluster join token with Pulumi:

   `pulumi login --local`

   `pulumi stack`

   `pulumi stack select`

   `pulumi config set ssh-key-path <path to your private SSH key>`

   `pulumi config set ssh-public-key-path <path to your public SSH key>`

   `pulumi config set --secret compartment-id <your OCI compartment ID>`

   `pulumi config set rke2-version <pinned RKE2 release>`

   `pulumi config set --secret rke2-token <long random cluster token>`

7. Launch 2 free tier ARM instances to Oracle Cloud and deploy RKE2 with Pulumi:

    `pulumi up`

Your Kubernetes configuration file should be available in `out/rke2_kubeconfig`
so you can use commands like `KUBECONFIG=out/rke2_kubeconfig kubectl ...`.

The first ARM instance runs the RKE2 server, control plane, and embedded etcd.
The second instance runs an RKE2 agent. The deployment is intentionally
destroy/recreate because the previous RKE1 cluster had no workloads to migrate.
The generated server certificate includes the server's public IP, allowing
kubectl clients and GUI tools such as FreeLens to verify the API endpoint.

RKE2 releases are listed in the [Rancher RKE2 releases](https://github.com/rancher/rke2/releases).
