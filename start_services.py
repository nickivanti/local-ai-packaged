#!/usr/bin/env python3
"""
start_services.py

This script starts the Supabase stack first, waits for it to initialize, and then starts
the local AI stack. Both stacks use the same Docker Compose project name ("localai")
so they appear together in Docker Desktop.
"""

import os
import subprocess
import shutil
import time
import argparse
import sys
import secrets
from datetime import datetime

def run_command(cmd, cwd=None):
    """Run a shell command and print it."""
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def ensure_docker_available():
    """Fail fast if Docker CLI or daemon is unavailable."""
    if shutil.which("docker") is None:
        raise RuntimeError(
            "Docker CLI was not found in PATH. Install Docker and ensure the `docker` command is available."
        )

    try:
        subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(
            "Docker daemon is not reachable. Start Docker Desktop or the Docker service, then rerun the script."
            + (f"\nDocker output: {details}" if details else "")
        ) from exc


def _git_porcelain_status(cwd: str) -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _git_has_local_changes(cwd: str) -> bool:
    return bool(_git_porcelain_status(cwd))

def clone_supabase_repo():
    """Clone the Supabase repository using sparse checkout if not already present."""
    if not os.path.exists("supabase"):
        print("Cloning the Supabase repository...")
        run_command([
            "git", "clone", "--filter=blob:none", "--no-checkout",
            "https://github.com/supabase/supabase.git"
        ])
        os.chdir("supabase")
        run_command(["git", "sparse-checkout", "init", "--cone"])
        run_command(["git", "sparse-checkout", "set", "docker"])
        run_command(["git", "checkout", "master"])
        os.chdir("..")
    else:
        print("Supabase repository already exists, updating...")
        supabase_dir = os.path.join(os.getcwd(), "supabase")
        stashed = False
        try:
            if _git_has_local_changes(supabase_dir):
                ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                print("Detected local changes in supabase repository.")
                print("Stashing changes so the update can proceed...")
                run_command([
                    "git",
                    "stash",
                    "push",
                    "-u",
                    "-m",
                    f"start_services.py auto-stash {ts}",
                ], cwd=supabase_dir)
                stashed = True

            run_command(["git", "pull"], cwd=supabase_dir)

            if stashed:
                print(
                    "Supabase update complete. Your previous local changes were stashed. "
                    "To re-apply them later, run: git -C supabase stash list && git -C supabase stash pop"
                )
        except subprocess.CalledProcessError:
            print("Error updating the Supabase repository.")
            print("To recover manually:")
            print("  - Inspect changes: git -C supabase status")
            print("  - Stash changes:  git -C supabase stash -u")
            print("  - OR reset hard:  git -C supabase reset --hard && git -C supabase clean -fd")
            raise

def prepare_supabase_env():
    """Copy .env to .env in supabase/docker."""
    env_path = os.path.join("supabase", "docker", ".env")
    env_example_path = os.path.join(".env")
    print("Copying .env in root to .env in supabase/docker...")
    shutil.copyfile(env_example_path, env_path)

def stop_existing_containers(profile=None, pg_version="15"):
    print("Stopping and removing existing containers for the unified project 'localai'...")
    cmd = ["docker", "compose", "-p", "localai"]
    if profile and profile != "none":
        cmd.extend(["--profile", profile])
    cmd.extend(["-f", "docker-compose.yml"])
    if pg_version == "15":
        cmd.extend(["-f", "supabase/docker/docker-compose.pg15.yml"])
    cmd.extend(["down"])
    run_command(cmd)

def start_supabase(environment=None, pg_version="15"):
    """Start the Supabase services (using its compose file)."""
    print("Starting Supabase services...")
    cmd = ["docker", "compose", "-p", "localai", "-f", "supabase/docker/docker-compose.yml"]
    if pg_version == "15":
        cmd.extend(["-f", "supabase/docker/docker-compose.pg15.yml"])
    if environment and environment == "public":
        cmd.extend(["-f", "docker-compose.override.public.supabase.yml"])
    cmd.extend(["up", "-d"])
    run_command(cmd)

def start_local_ai(profile=None, environment=None, pg_version="15"):
    """Start the local AI services (using its compose file)."""
    print("Starting local AI services...")
    cmd = ["docker", "compose", "-p", "localai"]
    if profile and profile != "none":
        cmd.extend(["--profile", profile])
    cmd.extend(["-f", "docker-compose.yml"])
    if pg_version == "15":
        cmd.extend(["-f", "supabase/docker/docker-compose.pg15.yml"])
    if environment and environment == "private":
        cmd.extend(["-f", "docker-compose.override.private.yml"])
    if environment and environment == "public":
        cmd.extend(["-f", "docker-compose.override.public.yml"])
    cmd.extend(["up", "-d"])
    run_command(cmd)

def generate_searxng_secret_key():
    """Generate a secret key for SearXNG based on the current platform."""
    print("Checking SearXNG settings...")

    # Define paths for SearXNG settings files
    settings_path = os.path.join("searxng", "settings.yml")
    settings_base_path = os.path.join("searxng", "settings-base.yml")

    # Check if settings-base.yml exists
    if not os.path.exists(settings_base_path):
        print(f"Warning: SearXNG base settings file not found at {settings_base_path}")
        return

    # Check if settings.yml exists, if not create it from settings-base.yml
    if not os.path.exists(settings_path):
        print(f"SearXNG settings.yml not found. Creating from {settings_base_path}...")
        try:
            shutil.copyfile(settings_base_path, settings_path)
            print(f"Created {settings_path} from {settings_base_path}")
        except Exception as e:
            print(f"Error creating settings.yml: {e}")
            return
    else:
        print(f"SearXNG settings.yml already exists at {settings_path}")

    if not os.access(settings_path, os.W_OK):
        print(
            f"Cannot write to {settings_path}. Current user does not have permission to update the SearXNG secret key."
        )
        print("Fix the ownership or permissions, then rerun the script.")
        print(f"  - Suggested fix: sudo chown -R $USER:$USER searxng")
        print(f"  - Or: sudo chmod u+w {settings_path}")
        return

    print("Generating SearXNG secret key...")

    try:
        with open(settings_path, 'r', encoding='utf-8') as file:
            content = file.read()

        random_key = secrets.token_hex(32)
        updated_content = content.replace("ultrasecretkey", random_key)

        if updated_content == content:
            print("SearXNG secret key placeholder not found; leaving the existing secret unchanged.")
            return

        with open(settings_path, 'w', encoding='utf-8') as file:
            file.write(updated_content)

        print("SearXNG secret key generated successfully.")

    except Exception as e:
        print(f"Error generating SearXNG secret key: {e}")
        print("You may need to manually set a 64-character hex secret in searxng/settings.yml.")

def check_and_fix_docker_compose_for_searxng():
    """Check and modify docker-compose.yml for SearXNG first run."""
    docker_compose_path = "docker-compose.yml"
    if not os.path.exists(docker_compose_path):
        print(f"Warning: Docker Compose file not found at {docker_compose_path}")
        return

    try:
        # Read the docker-compose.yml file
        with open(docker_compose_path, 'r') as file:
            content = file.read()

        # Default to first run
        is_first_run = True

        # Check if Docker is running and if the SearXNG container exists
        try:
            # Check if the SearXNG container is running
            container_check = subprocess.run(
                ["docker", "ps", "--filter", "name=searxng", "--format", "{{.Names}}"],
                capture_output=True, text=True, check=True
            )
            searxng_containers = container_check.stdout.strip().split('\n')

            # If SearXNG container is running, check inside for uwsgi.ini
            if any(container for container in searxng_containers if container):
                container_name = next(container for container in searxng_containers if container)
                print(f"Found running SearXNG container: {container_name}")

                # Check if uwsgi.ini exists inside the container
                container_check = subprocess.run(
                    ["docker", "exec", container_name, "sh", "-c", "[ -f /etc/searxng/uwsgi.ini ] && echo 'found' || echo 'not_found'"],
                    capture_output=True, text=True, check=False
                )

                if "found" in container_check.stdout:
                    print("Found uwsgi.ini inside the SearXNG container - not first run")
                    is_first_run = False
                else:
                    print("uwsgi.ini not found inside the SearXNG container - first run")
                    is_first_run = True
            else:
                print("No running SearXNG container found - assuming first run")
        except Exception as e:
            print(f"Error checking Docker container: {e} - assuming first run")

        if is_first_run and "cap_drop: - ALL" in content:
            print("First run detected for SearXNG. Temporarily removing 'cap_drop: - ALL' directive...")
            # Temporarily comment out the cap_drop line
            modified_content = content.replace("cap_drop: - ALL", "# cap_drop: - ALL  # Temporarily commented out for first run")

            # Write the modified content back
            with open(docker_compose_path, 'w') as file:
                file.write(modified_content)

            print("Note: After the first run completes successfully, you should re-add 'cap_drop: - ALL' to docker-compose.yml for security reasons.")
        elif not is_first_run and "# cap_drop: - ALL  # Temporarily commented out for first run" in content:
            print("SearXNG has been initialized. Re-enabling 'cap_drop: - ALL' directive for security...")
            # Uncomment the cap_drop line
            modified_content = content.replace("# cap_drop: - ALL  # Temporarily commented out for first run", "cap_drop: - ALL")

            # Write the modified content back
            with open(docker_compose_path, 'w') as file:
                file.write(modified_content)

    except Exception as e:
        print(f"Error checking/modifying docker-compose.yml for SearXNG: {e}")

def main():
    parser = argparse.ArgumentParser(description='Start the local AI and Supabase services.')
    parser.add_argument('--profile', choices=['cpu', 'gpu-nvidia', 'gpu-amd', 'none'], default='gpu-nvidia',
                      help='Profile to use for Docker Compose (default: gpu-nvidia)')
    parser.add_argument('--environment', choices=['private', 'public'], default='private',
                      help='Environment to use for Docker Compose (default: private)')
    parser.add_argument('--supabase-pg', choices=['15', '17'], default='15',
                      help='Supabase PostgreSQL major version (default: 15)')
    args = parser.parse_args()

    print("=" * 72)
    print("Starting local-ai-packaged with these settings:")
    print(f"  profile      : {args.profile}")
    print(f"  environment  : {args.environment}")
    print(f"  supabase-pg  : {args.supabase_pg}")
    print("\nAvailable options:")
    print("  --profile      cpu | gpu-nvidia | gpu-amd | none")
    print("  --environment  private | public")
    print("  --supabase-pg  15 | 17")
    print("=" * 72)

    clone_supabase_repo()
    prepare_supabase_env()

    # Generate SearXNG secret key and check docker-compose.yml
    generate_searxng_secret_key()

    ensure_docker_available()

    check_and_fix_docker_compose_for_searxng()

    stop_existing_containers(args.profile, args.supabase_pg)

    # Start Supabase first
    start_supabase(args.environment, args.supabase_pg)

    # Give Supabase some time to initialize
    print("Waiting for Supabase to initialize...")
    time.sleep(10)

    # Then start the local AI services
    start_local_ai(args.profile, args.environment, args.supabase_pg)

if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(exc)
        sys.exit(1)
