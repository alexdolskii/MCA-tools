"""Shared Fiji version and runtime settings, following FIA and UMA."""

import os

FIJI_ENDPOINT = "sc.fiji:fiji:2.14.0"
# Bio-Formats declares this official repository. Register it directly so
# fresh Fiji installs can resolve legacy artifacts such as woolz:JWlz.
FIJI_REPOSITORIES = {
    "ome.public": "https://artifacts.openmicroscopy.org/artifactory/maven/"
}


def configure_runtime():
    """Use the command's temporary directory without overriding JVM options."""
    import scyjava

    scyjava.config.add_repositories(FIJI_REPOSITORIES)
    if os.environ.get("MCA_RUN_TMP"):
        scyjava.config.add_option(
            "-Djava.io.tmpdir=" + os.environ["MCA_RUN_TMP"]
        )
