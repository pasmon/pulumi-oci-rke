![Pipeline Status](https://github.com/pasmon/pulumi-oci-rke/actions/workflows/ci-pipeline.yml/badge.svg)
# Provision Kubernetes Cluster To Oracle Cloud Infrastructure

## Requirements

- Oracle Cloud Infrastructure or something else for 2 instances
  - Docker in instances
- Python
- Pulumi

## Install Rancher Kubernetes Engine (RKE)

1. Create account to OCI for free, don't go for Stockholm region as currently there is no free instances available:
   https://www.oracle.com/cloud/free/

2. Create SSH keys in PEM format, either manually or letting OCI create them:
   https://ocikb.com/create-keys-in-pem-format

3. Modify `~/.oci/config` to correct path of your private SSH key

4. Create 2 instances, and get their IP addresses

5. Install and configure Docker:
https://docs.docker.com/engine/install/

6. Open firewall ports for RKE, both in OCI security list and in instances:
https://rancher.com/docs/rke/latest/en/os/#ports

7. Install Pulumi:
https://www.pulumi.com/docs/get-started/install/

8. Install Python packages with pipenv (https://pipenv.pypa.io/en/latest/install/#installing-pipenv):

    `pipenv install`

9. Activate Python virtual environment:

    `pipenv shell`

10. Set the IP addresses and path to your private SSH key with Pulumi:
```
pulumi config set master_public_ip <master public IP>
pulumi config set master_internal_ip <master internal IP>
pulumi config set worker_public_ip <master public IP>
pulumi config set worker_internal_ip <master internal IP>
pulumi config set ssh_key_path <master public IP>
```

11. Deploy RKE with Pulumi:

    `pulumi up`

### Ramblings

OCI instance creation should've been automated with Pulumi but couldn't get it to work:
https://github.com/pulumi-oci/pulumi-oci

Was going to use RKE2 but no dice with ARM currently:
https://github.com/rancher/rke2/issues/817
