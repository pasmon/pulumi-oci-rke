# Repository instructions

## Setup and validation

- Use Python 3.14 and uv. Install the locked development environment with `uv sync --locked`.
- Run the same checks as CI:
-  - Syntax: `uv run python -m py_compile __main__.py tests/*.py`
  - Ruff: `uv run ruff check .`
  - Black: `uv run black --check .`
  - Pylint: `uv run pylint __main__.py tests`
  - Bandit: `uv run bandit -c pyproject.toml -r . -x ./tests -x ./.venv`
  - Tests: `uv run pytest -v`
- Run one test with its pytest node ID, for example:
  `uv run pytest -v tests/test_infra.py::test_user_data_configuration`.
- Pre-commit hooks can be run with `uv run pre-commit run --all-files`. Commit messages are checked for Conventional Commits format.
- This project has no separate build step. Deploy from a selected Pulumi stack with `uv run pulumi up`; the required project config keys are `ssh-key-path`, `ssh-public-key-path`, and secret `compartment-id`.

## Architecture

- `__main__.py` is the complete Pulumi program and executes eagerly when imported. It reads the configured SSH key files, creates the OCI network and two ARM compute instances, waits for cloud-init over SSH, and then installs RKE2 server/agent services across those instances.
- The OCI layer consists of a VCN, internet gateway, default route table, subnet, network security group, and ingress rules. Both instances attach to that subnet and security group.
- Instance cloud-init installs the RKE2 prerequisites and prepares Ubuntu. `pulumi_command.remote.Command` resources wait for `cloud-init status --wait`; the RKE2 server and agent explicitly depend on those commands and on each other.
- The first node runs the RKE2 server, control plane, and embedded etcd; the second runs an RKE2 agent. The deployment is tied to OCI Stockholm AD-1, an Ubuntu ARM image OCID, and the `VM.Standard.A1.Flex` free-tier shape.
- The generated RKE2 kubeconfig is written asynchronously from a Pulumi `Output.apply` callback to `out/rke2_kubeconfig`. Public IPs and the configured RKE2 version are exported as stack outputs.

## Repository conventions

- Preserve Pulumi dependency ordering when changing infrastructure. Resources that require completed host initialization must depend on the remote cloud-init commands rather than only on the compute instances.
- Tests never contact OCI or create infrastructure. The session-scoped `pulumi_stack` fixture creates temporary SSH key files, sets `PULUMI_CONFIG`, installs `pulumi.runtime.Mocks`, and only then dynamically imports `__main__.py`.
- Because the program runs at import time and reads files immediately, any new required config or filesystem input must also be supplied by the test fixture before import.
- Assert ordinary constants and resource presence directly. Assert resolved Pulumi resource properties with `@pulumi.runtime.test` and `Output.apply`.
- Keep the 120-character line length used by Ruff and Pylint. Black, Ruff, Pylint, and Bandit all run in CI; Bandit intentionally excludes `tests`.
- Direct dependencies are declared in `pyproject.toml`; reproducible versions and hashes belong in `uv.lock`. Use uv to update the lockfile.
