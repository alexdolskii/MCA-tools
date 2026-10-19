"""MCA image export and calibrated SHG measurements."""

from importlib.metadata import PackageNotFoundError, version


def package_version() -> str:
    """Read the installed package version without scientific imports."""
    try:
        return version("mca-tools")
    except PackageNotFoundError:
        return "not installed"
