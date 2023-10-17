![Pipeline Status](https://github.com/pasmon/pulumi-oci-rke/actions/workflows/ci-pipeline.yml/badge.svg)
# Provision Kubernetes Cluster (RKE) To Oracle Cloud Infrastructure

## Requirements

- Oracle Cloud Infrastructure account
- Python
  - Pipenv
- Pulumi

## Install Rancher Kubernetes Engine (RKE)

1. Create account to Oracle Cloud for free:

   https://www.oracle.com/cloud/free/

2. Setup OCI credentials:

   https://docs.oracle.com/en-us/iaas/Content/API/Concepts/apisigningkey.htm#Required_Keys_and_OCIDs

3. Install Pulumi:

   https://www.pulumi.com/docs/get-started/install/

4. Install Python packages with pipenv (https://pipenv.pypa.io/en/latest/install/#installing-pipenv):

    `pipenv install`

5. Activate Python virtual environment:

    `pipenv shell`

6. Set the OCI compartment ID, and path to your private and public SSH key with Pulumi:

   `pulumi login --local`

   `pulumi stack`

   `pulumi stack select`

   `pulumi config set ssh-key-path <path to your private SSH key>`

   `pulumi config set ssh-public-key-path <path to your public SSH key>`

   `pulumi config set --secret compartment-id <your OCI compartment ID>`

7. Launch 2 free tier ARM instances to Oracle Cloud and deploy RKE with Pulumi:

    `pulumi up`

Your Kubernetes configuration file should be available in `out/rke_kubeconfig`
so you can use commands like `KUBECONFIG=out/rke_kubeconfig kubectl ...`.

### Ramblings

Was going to use RKE2 but no dice with ARM currently:
https://github.com/rancher/rke2/issues/817
