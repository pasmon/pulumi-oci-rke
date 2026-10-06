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

   `Get-Content -Raw <path to SSH private key> | pulumi config set --secret --raw argocd-repo-ssh-private-key`

   Optional GitHub App credentials for a private GitHub repository:

   `pulumi config set argocd-github-app-id <GitHub App ID>`

   `pulumi config set argocd-github-app-installation-id <GitHub App installation ID>`

   `Get-Content -Raw <path to GitHub App PEM private key> | pulumi config set --secret --raw argocd-github-app-private-key`

   `pulumi config set` has no `@file` syntax: passing `@<path>` stores that
   literal string as the value, and Argo CD then fails with
   `Key must be a PEM encoded PKCS1 or PKCS8 key`. Pipe the file instead.

   Configure only one authentication mode for Argo CD repository access:
   HTTPS credentials, SSH private key, or GitHub App credentials.

   Optional Wireguard tunnel to your own router. The entire block is skipped
   unless `wireguard-peer-endpoint` is set:

   `pulumi config set wireguard-peer-endpoint <public IP or DDNS of your router>`

   `pulumi config set wireguard-peer-public-key <router Wireguard public key>`

   `pulumi config set --secret wireguard-private-key <shared node private key>`

   `pulumi config set --secret wireguard-preshared-key <tunnel preshared key>`

   `pulumi config set wireguard-subnet-cidr 10.99.0.0/24`

   `pulumi config set wireguard-listen-port 51820`

   `pulumi config set wireguard-allowed-cidrs '["192.168.88.200/32"]'`

   Generate the shared keys once with `wg genkey` and `wg genpsk` and store
   them in stack config. Pulumi does not generate them so both nodes keep the
   same key across the destroy/recreate this program performs.

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
- `gitops/bootstrap/bootstrap-project.yaml` defines the bootstrap `AppProject` and allows the `argo-apps` repository as a source.
- `gitops/bootstrap/argocd-self-application.yaml` defines the long-term Argo CD
  self-management `Application`, but it is intentionally not auto-synced yet.
- `gitops/bootstrap/argo-apps-application.yaml` creates the `platform-app-of-apps`
  child `Application` from `https://github.com/pasmon/argo-apps.git`, connecting
  the production workload tree after bootstrap.

## Self-management handoff

This repository uses a two-phase handoff so Pulumi and Argo CD do not both try
to own the same Argo CD resources at the same time:

1. Pulumi installs Argo CD and creates the `bootstrap-root` `Application`.
2. Argo CD syncs `gitops/bootstrap`, which creates the `bootstrap` project and
   the `argocd-self` child `Application`.
3. Review `argocd-self`, manually sync it while the Pulumi-managed Argo CD
   release is still installed, and verify it is healthy.
4. After `argocd-self` has taken over, disable or remove the Pulumi-managed
   Argo CD release before enabling automation on `argocd-self`.
5. After the handoff, keep Argo CD's steady-state chart configuration in Git
   and avoid reintroducing the same resources under Pulumi management.

RKE2 releases are listed in the [Rancher RKE2 releases](https://github.com/rancher/rke2/releases).

## Wireguard tunnel

The cluster nodes can hold a Wireguard tunnel to your own router so that
cluster workloads can reach services on your home network without exposing
them publicly. The tunnel is host-level, runs on both RKE2 nodes, and the
nodes initiate the connection to the router.

The Wireguard peer is the router, not the service being reached. The router
terminates the tunnel and forwards traffic onto the LAN normally:

```text
OCI WireGuard peer  <--WireGuard tunnel-->  MikroTik hEX
   10.99.0.2                                    wg: 10.99.0.1
                                                LAN: 192.168.88.1
                                                    |
                                              routed, no SNAT
                                                    v
                                    Raspberry Pi: 192.168.88.200:8443
```

The Pi holds no Wireguard configuration of its own. It is reached as an
ordinary LAN host, so no tunnel is configured on it and nothing about the
cluster is required for it to keep serving the local network.

This is optional. Nothing is created unless `wireguard-peer-endpoint` is set.
Setting the endpoint without a peer public key, a shared private key, or a
preshared key fails validation rather than provisioning a broken tunnel.

### Addressing

The subnet defaults to `10.99.0.0/24` and must not overlap the VCN
(`10.0.0.0/16`), the RKE2 pod network (`10.42.0.0/16`), or the service
network (`10.43.0.0/16`). Addresses are derived from the subnet: the router
takes the first usable address, the master the second, and the worker the
third, so `10.99.0.1`, `10.99.0.2`, and `10.99.0.3` by default.

The nodes carry the same private key, so the router needs a single peer entry
rather than one per node.

### Routed prefixes

`wireguard-allowed-cidrs` lists the prefixes that should be reachable through
the tunnel, for example the Raspberry Pi at `192.168.88.200/32`. They are
appended to the peer's `AllowedIPs` after the tunnel subnet.

This is not only an access-control setting. WireGuard uses `AllowedIPs` as its
crypto-routing table, and the kernel only sends a packet into the tunnel when
its destination matches an entry. A destination missing from `AllowedIPs` falls
through to the default route and leaves through the OCI internet gateway
instead, so every prefix you intend to reach over the tunnel must be listed.

The value is a JSON list. Invalid CIDRs are rejected during `pulumi preview`
rather than failing later when the interface comes up.

### Router configuration

Configure one interface on the router with the shared private key, the
preshared key, and `Endpoint = 0.0.0.0:0` because the nodes dial out rather
than accepting an inbound connection. Set `PersistentKeepalive` on the router
side as well; the OCI nodes are behind NAT, so without it the router cannot
open a return path to them.

Set the router's `AllowedIPs` for this peer to `10.99.0.0/24`, matching the
nodes. That entry is what makes the router decrypt return traffic addressed to
the nodes' tunnel addresses. The routed LAN prefixes belong on the nodes only;
the router already knows how to reach its own LAN directly, and it uses
`AllowedIPs` on this peer solely to identify which source addresses belong to
the cluster.

The router owns routing to the rest of your network, so the nodes add no
routes for your LAN and no OCI route table rule is required.

### Pod traffic

Traffic to the routed prefixes is not masqueraded. The router forwards it
without SNAT, so the Raspberry Pi sees the original tunnel source address
(`10.99.0.2` on the master, `10.99.0.3` on the worker) rather than the router's
LAN address. Set `RADIO_API_WIREGUARD_CIDR=10.99.0.0/24` on the Pi so its
network guard accepts that range.

Pods are the one exception, because their `10.42.0.0/16` addresses fall outside
the tunnel range and would be rejected. The configuration masquerades that
source range on `wg0` only, collapsing pod traffic onto the node's tunnel
address so the Pi's guard still accepts it. Node traffic is unaffected because
its source does not match the pod range.

These rules are applied through `wg-quick` `PostUp`/`PostDown` hooks rather than
cloud-init, so they survive the `iptables -F` in the instance user data and are
restored whenever the interface is brought up.

No additional OCI security list or network security group rule is needed,
because the nodes initiate the connection outbound.

