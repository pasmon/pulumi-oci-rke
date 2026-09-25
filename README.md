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
   cluster join token with Pulumi. Also configure the Git repository that Argo
   CD should bootstrap from:

   `pulumi login --local`

   `pulumi stack`

   `pulumi stack select`

   `pulumi config set ssh-key-path <path to your private SSH key>`

   `pulumi config set ssh-public-key-path <path to your public SSH key>`

   `pulumi config set --secret compartment-id <your OCI compartment ID>`

   `pulumi config set rke2-version <pinned RKE2 release>`

   `pulumi config set --secret rke2-token <long random cluster token>`

   `pulumi config set argocd-repo-url <https or ssh URL for this repository>`

   `pulumi config set argocd-repo-target-revision <git revision to sync>`

   `pulumi config set argocd-repo-path gitops/bootstrap`

   Optional HTTPS credentials for a private Git repository:

   `pulumi config set argocd-repo-username <git username>`

   `pulumi config set --secret argocd-repo-password <git token or password>`

   Optional SSH credentials for a private Git repository:

   `pulumi config set --secret argocd-repo-ssh-private-key @<path to SSH private key>`

7. Launch 2 free tier ARM instances to Oracle Cloud and deploy RKE2 with Pulumi:

    `pulumi up`

Your Kubernetes configuration file should be available in `out/rke2_kubeconfig`
so you can use commands like `KUBECONFIG=out/rke2_kubeconfig kubectl ...`.

The first ARM instance runs the RKE2 server, control plane, and embedded etcd.
The second instance runs an RKE2 agent. The deployment is intentionally
destroy/recreate because the previous RKE1 cluster had no workloads to migrate.
The generated server certificate includes the server's public IP, allowing
kubectl clients and GUI tools such as FreeLens to verify the API endpoint.

Pulumi also uses the generated RKE2 kubeconfig to bootstrap Argo CD into the
`argocd` namespace with the official Helm chart. The initial Argo CD server
service remains `ClusterIP`, so access is internal-only unless you later expose
it deliberately through Kubernetes networking or additional OCI rules.

## Argo CD bootstrap flow

- Pulumi installs Argo CD after the OCI instances, cloud-init completion, RKE2
  server, RKE2 agent, and kubeconfig retrieval steps have succeeded.
- Pulumi seeds a root Argo CD `Application` named `bootstrap-root` that points
  back to this repository and syncs the `gitops/bootstrap` path automatically.
- `gitops/bootstrap/bootstrap-project.yaml` defines the bootstrap `AppProject`.
- `gitops/bootstrap/argocd-self-application.yaml` defines the long-term Argo CD
  self-management `Application`, but it is intentionally not auto-synced yet.

## Self-management handoff

This repository uses a two-phase handoff so Pulumi and Argo CD do not both try
to own the same Argo CD resources at the same time:

1. Pulumi installs Argo CD and creates the `bootstrap-root` `Application`.
2. Argo CD syncs `gitops/bootstrap`, which creates the `bootstrap` project and
   the `argocd-self` child `Application`.
3. Review `argocd-self`, then disable or remove the Pulumi-managed Argo CD
   release before manually syncing or enabling automation on `argocd-self`.
4. After the handoff, keep Argo CD's steady-state chart configuration in Git
   and avoid reintroducing the same resources under Pulumi management.

RKE2 releases are listed in the [Rancher RKE2 releases](https://github.com/rancher/rke2/releases).
