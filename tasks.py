#!/usr/bin/env python
import shutil
import sys
import os
import logging
from invoke import task, Collection, UnexpectedExit, Failure

from policy_sentry.shared.constants import (
    LOCAL_HTML_DIRECTORY_PATH,
    BUNDLED_HTML_DIRECTORY_PATH,
)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, "policy_sentry")))
from policy_sentry.command import initialize

logger = logging.getLogger(__name__)
# Create the necessary collections (namespaces)
ns = Collection()

docs = Collection("docs")
ns.add_collection(docs)

test = Collection("test")
ns.add_collection(test)

integration = Collection("integration")
ns.add_collection(integration)

unit = Collection("unit")
ns.add_collection(unit)

build = Collection("build")
ns.add_collection(build)

docker = Collection("docker")
ns.add_collection(docker)

sanity = Collection("sanity")
ns.add_collection(sanity)


@task
def build_docs(c):
    """Create the documentation files and open them locally"""
    c.run("mkdocs build")


@task
def serve_docs(c):
    """Create the documentation files and open them locally"""
    c.run('mkdocs serve --dev-addr "127.0.0.1:8001"')


@task
def download_latest_aws_docs(c):
    """Download the latest AWS docs, and update the bundled IAM database."""
    c.run("./utils/download_docs.py")


# BUILD
@task
def build_package(c):
    """Build the policy_sentry package from the current directory contents for use with PyPi"""
    c.run("python -m pip install --upgrade setuptools wheel")
    c.run("python setup.py sdist bdist_wheel")


@task(pre=[build_package])
def install_package(c):
    """Install the policy_sentry package built from the current directory contents (not PyPi)"""
    c.run("pip3 install -q dist/policy_sentry-*.whl")


@task
def uninstall_package(c):
    """Uninstall the policy_sentry package"""
    c.run('echo "y" | pip3 uninstall policy_sentry', pty=True)


@task
def upload_to_pypi_test_server(c):
    """Upload the package to the TestPyPi server (requires credentials)"""
    c.run("python -m pip install --upgrade twine")
    c.run("python -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*")
    c.run("python -m pip install --index-url https://test.pypi.org/simple/ --no-deps policy_sentry")


@task
def upload_to_pypi_prod_server(c):
    """Upload the package to the PyPi production server (requires credentials)"""
    c.run("python -m pip install --upgrade twine")
    c.run("python -m twine upload dist/*")
    c.run("python -m pip install policy_sentry")


# INTEGRATION TESTS
@task
def clean_config_directory(c):
    """Runs `rm -rf $HOME/.policy_sentry`"""
    try:
        c.run("rm -rf $HOME/.policy_sentry/")
    except UnexpectedExit as u_e:
        logger.critical(f"FAIL! UnexpectedExit: {u_e}")
        sys.exit(1)
    except Failure as f_e:
        logger.critical(f"FAIL: Failure: {f_e}")
        sys.exit(1)


@task
def create_db(c):
    """Integration testing: Initialize the policy_sentry database"""
    try:
        LOCAL_HTML_DIRECTORY_PATH.mkdir(parents=True, exist_ok=True)
        shutil.copytree(BUNDLED_HTML_DIRECTORY_PATH, LOCAL_HTML_DIRECTORY_PATH, dirs_exist_ok=True)

        initialize.initialize("")
    except UnexpectedExit as u_e:
        logger.critical(f"FAIL! UnexpectedExit: {u_e}")
        sys.exit(1)
    except Failure as f_e:
        logger.critical(f"FAIL: Failure: {f_e}")
        sys.exit(1)


@task
def version_check(c):
    """Print the version"""
    try:
        c.run("./policy_sentry/bin/cli.py --version", pty=True)
    except UnexpectedExit as u_e:
        logger.critical(f"FAIL! UnexpectedExit: {u_e}")
        sys.exit(1)
    except Failure as f_e:
        logger.critical(f"FAIL: Failure: {f_e}")
        sys.exit(1)


@task(pre=[install_package])
def write_policy(c):
    """
    Integration testing: Tests the `write-policy` function.
    """
    try:
        c.run(
            "./policy_sentry/bin/cli.py write-policy --input-file examples/yml/crud.yml",
            pty=True,
        )
        c.run(
            "./policy_sentry/bin/cli.py write-policy --input-file examples/yml/crud.yml",
            pty=True,
        )
        c.run(
            "./policy_sentry/bin/cli.py write-policy --input-file examples/yml/actions.yml",
            pty=True,
        )
    except UnexpectedExit as u_e:
        logger.critical(f"FAIL! UnexpectedExit: {u_e}")
        sys.exit(1)
    except Failure as f_e:
        logger.critical(f"FAIL: Failure: {f_e}")
        sys.exit(1)


@task(pre=[install_package])
def query(c):
    """Integration testing: Tests the `query` functionality (querying the IAM database)"""
    try:
        c.run('echo "Querying the action table"', pty=True)
        c.run("./policy_sentry/bin/cli.py query action-table --service ram", pty=True)
        c.run(
            "./policy_sentry/bin/cli.py query action-table --service ram --name tagresource",
            pty=True,
        )
        c.run(
            "./policy_sentry/bin/cli.py query action-table --service ram --access-level permissions-management",
            pty=True,
        )
        c.run(
            "./policy_sentry/bin/cli.py query action-table --service ssm --resource-type parameter",
            pty=True,
        )
        c.run(
            "./policy_sentry/bin/cli.py query action-table --service ssm --access-level write "
            "--resource-type parameter",
            pty=True,
        )
        c.run(
            "policy_sentry query action-table --service ssm --resource-type parameter",
            pty=True,
        )
        c.run(
            "./policy_sentry/bin/cli.py query action-table --service ses --condition ses:FeedbackAddress",
            pty=True,
        )
        c.run('echo "Querying the ARN table"', pty=True)
        c.run("./policy_sentry/bin/cli.py query arn-table --service ssm", pty=True)
        c.run(
            "./policy_sentry/bin/cli.py query arn-table --service cloud9 --name environment",
            pty=True,
        )
        c.run(
            "./policy_sentry/bin/cli.py query arn-table --service cloud9 --list-arn-types",
            pty=True,
        )
        c.run('echo "Querying the condition keys table"', pty=True)
        c.run(
            "./policy_sentry/bin/cli.py query condition-table --service cloud9",
            pty=True,
        )
        c.run(
            "./policy_sentry/bin/cli.py query condition-table --service cloud9 --name cloud9:Permissions",
            pty=True,
        )
    except UnexpectedExit as u_e:
        logger.critical(f"FAIL! UnexpectedExit: {u_e}")
        sys.exit(1)
    except Failure as f_e:
        logger.critical(f"FAIL: Failure: {f_e}")
        sys.exit(1)


@task(pre=[install_package])
def query_with_yaml(c):
    """Integration testing: Tests the `query` functionality (querying the IAM database) - but with yaml"""
    try:
        c.run('echo "Querying the action table with yaml option"')
        c.run('echo "Querying the action table"', pty=True)
        c.run(
            "./policy_sentry/bin/cli.py query action-table --service ram --fmt yaml",
            pty=True,
        )
        c.run(
            "./policy_sentry/bin/cli.py query action-table --service ram --name tagresource --fmt yaml",
            pty=True,
        )
        c.run(
            "./policy_sentry/bin/cli.py query action-table --service ram --access-level permissions-management --fmt yaml",
            pty=True,
        )
        c.run(
            "./policy_sentry/bin/cli.py query action-table --service ses --condition ses:FeedbackAddress --fmt yaml",
            pty=True,
        )
        c.run('echo "Querying the ARN table"', pty=True)
        c.run(
            "./policy_sentry/bin/cli.py query arn-table --service ssm --fmt yaml",
            pty=True,
        )
        c.run(
            "./policy_sentry/bin/cli.py query arn-table --service cloud9 --name environment --fmt yaml",
            pty=True,
        )
        c.run(
            "./policy_sentry/bin/cli.py query arn-table --service cloud9 --list-arn-types --fmt yaml",
            pty=True,
        )
        c.run('echo "Querying the condition keys table"', pty=True)
        c.run(
            "./policy_sentry/bin/cli.py query condition-table --service cloud9 --fmt yaml",
            pty=True,
        )
        c.run(
            "./policy_sentry/bin/cli.py query condition-table --service cloud9 --name cloud9:Permissions --fmt yaml",
            pty=True,
        )
    except UnexpectedExit as u_e:
        logger.critical(f"FAIL! UnexpectedExit: {u_e}")
        sys.exit(1)
    except Failure as f_e:
        logger.critical(f"FAIL: Failure: {f_e}")
        sys.exit(1)


# TEST - type check
@task
def run_mypy(c):
    """Type checking with `mypy`"""
    try:
        c.run("mypy")
    except UnexpectedExit as u_e:
        logger.critical(f"FAIL! UnexpectedExit: {u_e}")
        sys.exit(1)
    except Failure as f_e:
        logger.critical(f"FAIL: Failure: {f_e}")
        sys.exit(1)


# UNIT TESTING
@task
def run_pytest(c):
    """Unit testing: Runs unit tests using `pytest`"""
    c.run('echo "Running Unit tests"')
    try:
        c.run("python -m coverage run -m pytest -v")
        c.run("python -m coverage report -m")
    except UnexpectedExit as u_e:
        logger.critical(f"FAIL! UnexpectedExit: {u_e}")
        sys.exit(1)
    except Failure as f_e:
        logger.critical(f"FAIL: Failure: {f_e}")
        sys.exit(1)


# DOCKER
@task
def build_docker(c):
    """Open HTML docs in Google Chrome locally on your computer"""
    c.run("docker build -t kmcquade/policy_sentry .")


# Sanity checks
@task(post=[uninstall_package])
def validate_wheel(c):
    """Validate the wheel can be installed and works properly"""
    c.run("pip3 install dist/policy_sentry-*.whl")
    c.run("policy_sentry query service-table --fmt csv", pty=True)


@task(post=[uninstall_package])
def validate_sdist(c):
    """Validate the sdist archive can be installed and works properly"""
    c.run("pip3 install dist/policy_sentry-*.tar.gz")
    c.run("policy_sentry query service-table --fmt csv", pty=True)


# Add all testing tasks to the test collection
integration.add_task(clean_config_directory, "clean")
integration.add_task(version_check, "version")
integration.add_task(create_db, "initialize")
integration.add_task(write_policy, "write-policy")
integration.add_task(query, "query")
integration.add_task(query_with_yaml, "query-yaml")

unit.add_task(run_pytest, "pytest")

docs.add_task(build_docs, "build-docs")
docs.add_task(serve_docs, "serve-docs")
docs.add_task(download_latest_aws_docs, "download_latest_aws_docs")

# test.add_task(run_full_test_suite, 'all')
test.add_task(run_mypy, "type-check")

build.add_task(build_package, "build-package")
build.add_task(install_package, "install-package")
build.add_task(uninstall_package, "uninstall-package")
build.add_task(upload_to_pypi_test_server, "upload-test")
build.add_task(upload_to_pypi_prod_server, "upload-prod")
build.add_task(upload_to_pypi_prod_server, "upload-prod")

docker.add_task(build_docker, "build-docker")

sanity.add_task(validate_wheel, "validate-wheel")
sanity.add_task(validate_sdist, "validate-sdist")
