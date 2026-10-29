"""Run deployment-script regressions in disposable Linux containers."""

import secrets
import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[2]
    project = "geo-monitor-deploy-check-" + secrets.token_hex(6)
    monitor_image = project + "-monitor"
    runner_image = project + "-runner-image"
    runner = project + "-runner"

    def docker(*args, check=True, capture=True):
        result = subprocess.run(["docker", *args], cwd=root, capture_output=capture, text=True)
        if check and result.returncode:
            if capture:
                print(result.stderr[-5000:])
            raise RuntimeError("isolated deployment regression command failed")
        return result

    try:
        docker("build", "-f", "deploy/server.Dockerfile", "-t", monitor_image, ".")
        print("Production monitor image built.", flush=True)
        docker(
            "build",
            "--build-arg",
            "MONITOR_IMAGE=" + monitor_image,
            "-t",
            runner_image,
            "tests/deployment",
        )
        print("Running Linux Bash and actual Docker deployment regressions.", flush=True)
        command = (
            "mkdir -p /tmp/deploy-tools && "
            "ln -s /usr/local/bin/docker-real /tmp/deploy-tools/docker && "
            "export PATH=/tmp/deploy-tools:$PATH && cd /workspace && "
            "uv run --frozen pytest -q -o cache_dir=/tmp/deploy-pytest-cache "
            "tests/unit/server/test_deploy_script.py"
        )
        docker(
            "run",
            "--rm",
            "--name",
            runner,
            "--mount",
            "type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock",
            "--mount",
            f"type=bind,src={root},dst=/workspace,readonly",
            "--env",
            "UV_PROJECT_ENVIRONMENT=/tmp/deploy-test-environment",
            "--env",
            "UV_LINK_MODE=copy",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            "--env",
            "GEO_DEPLOY_DOCKER_TEST_PROJECT=" + project,
            "--entrypoint",
            "bash",
            runner_image,
            "-c",
            command,
            capture=False,
        )
        print("Deployment script Linux and repeat-deployment checks passed.", flush=True)
    finally:
        # Only this invocation's unguessable project and image names are removed.
        docker("rm", "-f", runner, check=False)
        label = "com.docker.compose.project=" + project
        for kind, listing in (("container", ("ps", "-aq")), ("volume", ("volume", "ls", "-q"))):
            items = docker(*listing, "--filter", "label=" + label, check=False).stdout.split()
            if items:
                docker(kind, "rm", "-f", *items, check=False)
        for network in docker(
            "network", "ls", "-q", "--filter", "label=" + label, check=False
        ).stdout.split():
            docker("network", "rm", network, check=False)
        docker("image", "rm", runner_image, monitor_image, project + "-monitor", check=False)


if __name__ == "__main__":
    main()
