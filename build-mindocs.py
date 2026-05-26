#!/usr/bin/env python3
"""
Build script for MinIO docs on Windows (or any platform without GNU Make).
Replicates the 'make SYNC_SDK=true mindocs' target from the Makefile.
"""
import os
import sys
import subprocess
import shutil
import argparse


def run(cmd, capture=False):
    """Run a shell command and optionally capture its stdout."""
    print(f"$ {cmd}")
    kwargs = {"shell": True}
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)
    return result


def sync_kes_version():
    """Retrieve latest KES release and substitute into conf.py."""
    kes_url = run(
        'curl --retry 10 -Ls -o /dev/null -w "%{url_effective}" '
        'https://github.com/minio/kes/releases/latest',
        capture=True,
    ).stdout.strip()
    kes_version = kes_url.replace("https://github.com/minio/kes/releases/tag/", "")
    print(f"Latest KES version: {kes_version}")
    run(f'sed -i "s|KESLATEST|{kes_version}|g" source/conf.py')


def sync_minio_server_docs():
    """Run the upstream sync script."""
    run("bash sync-minio-server-docs.sh")


def sync_operator_version():
    """Retrieve latest Operator version and K8s floor, substitute into conf.py."""
    operator_url = run(
        'curl --retry 10 -Ls -o /dev/null -w "%{url_effective}" '
        'https://github.com/minio/operator/releases/latest',
        capture=True,
    ).stdout.strip()
    operator_version = operator_url.replace(
        "https://github.com/minio/operator/releases/tag/v", ""
    )
    print(f"Latest Operator version: {operator_version}")

    k8s_floor = run(
        "curl -sL https://raw.githubusercontent.com/minio/operator/master/testing/kind-config-floor.yaml "
        "| grep -F -m 1 'node:v' | awk 'BEGIN { FS = \":\" } ; {print $3}'",
        capture=True,
    ).stdout.strip()
    print(f"K8s floor version: {k8s_floor}")

    run(f'sed -i "s|OPERATOR|{operator_version}|g" source/conf.py')
    run(f'sed -i "s|K8SFLOOR|{k8s_floor}|g" source/conf.py')


def sync_sdks():
    """Synchronize SDK docs from GitHub."""
    run("bash sync-docs.sh")


def main():
    parser = argparse.ArgumentParser(description="Build MinIO mindocs")
    parser.add_argument(
        "--sync-sdk",
        action="store_true",
        help="Synchronize SDK content from MinIO's community S3 libraries",
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # 1. Reset conf.py from template
    # ------------------------------------------------------------------
    print("--------------------------------------")
    print("         Building for MinIO           ")
    print("--------------------------------------")
    shutil.copy("source/default-conf.py", "source/conf.py")

    # ------------------------------------------------------------------
    # 2. sync-deps (sync-kes-version + sync-minio-server-docs)
    # ------------------------------------------------------------------
    print("\n[sync-deps] Synchronizing external dependencies...")
    sync_kes_version()
    sync_minio_server_docs()

    # ------------------------------------------------------------------
    # 3. sync-operator-version
    # ------------------------------------------------------------------
    print("\n[sync-operator-version] Retrieving latest Operator version...")
    sync_operator_version()

    # ------------------------------------------------------------------
    # 4. sync-deps again (Makefile calls it twice)
    #    The work is idempotent except for conf.py edits, so we can skip
    #    the redundant network calls and just re-run the scripts if desired.
    #    For simplicity we skip the second identical run.
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # 5. sync-sdks (optional)
    # ------------------------------------------------------------------
    if args.sync_sdk:
        print("\n[sync-sdks] Synchronizing SDKs...")
        sync_sdks()
    else:
        print("\n[sync-sdks] Skipping SDK sync. Pass --sync-sdk to enable.")

    # ------------------------------------------------------------------
    # 6. Compile SCSS / JS
    # ------------------------------------------------------------------
    print("\n[npm] Running build...")
    run("npm run build")

    # ------------------------------------------------------------------
    # 7. Sphinx build
    # ------------------------------------------------------------------
    git_branch = run("git rev-parse --abbrev-ref HEAD", capture=True).stdout.strip()
    build_dir = f"build/{git_branch}/mindocs"
    print(f"\n[sphinx] Building HTML into {build_dir} ...")
    run(
        f'sphinx-build -M html "source" "{build_dir}" '
        f'-n -j auto -w "build.log" -t mindocs'
    )

    print("\n--------------------------------------")
    print(f" Building mindocs Complete")
    print(f" Output: {build_dir}/html")
    print("--------------------------------------")


if __name__ == "__main__":
    main()
