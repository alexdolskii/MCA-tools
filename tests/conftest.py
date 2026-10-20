"""Small, deterministic LIF fixtures read through the real readlif parser."""

import os
import struct
from xml.sax.saxutils import escape

import numpy as np
import pytest


def write_lif(path, pixels, spacing=(0.5, 0.25, 2.0), name="scene/one"):
    """Write the minimal Leica XML/block layout for a single ZYX scene."""
    pixels = np.asarray(pixels)
    nz, height, width = pixels.shape
    dimensions = []
    for dimension, count, step, stride in zip(
        (1, 2, 3),
        (width, height, nz),
        spacing,
        (
            pixels.itemsize,
            width * pixels.itemsize,
            width * height * pixels.itemsize,
        ),
    ):
        length = (count - 1) * step / 1e6 if step is not None else 0
        dimensions.append(
            f'<DimensionDescription DimID="{dimension}" NumberOfElements="{count}" '
            f'Length="{length}" Unit="m" BytesInc="{stride}"/>'
        )
    xml = (
        f'<LMSDataContainerHeader><Element Name="{escape(name)}"><Data><Image>'
        "<ImageDescription><Dimensions>"
        + "".join(dimensions)
        + f'</Dimensions><Channels><ChannelDescription Resolution="{pixels.itemsize * 8}" '
        'BytesInc="0"/></Channels></ImageDescription></Image></Data>'
        f'<Memory Size="{pixels.nbytes}"/></Element></LMSDataContainerHeader>'
    )
    encoded = xml.encode("utf-16-le")
    marker = b"\x70\0\0\0" + struct.pack("<I", 0) + b"\x2a"
    header = marker + struct.pack("<I", len(encoded) // 2) + encoded
    block = (
        marker
        + struct.pack("<I", pixels.nbytes)
        + b"\x2a"
        + struct.pack("<I", 0)
    )
    path.write_bytes(header + block + pixels.tobytes())
    return path


@pytest.fixture
def lif_factory():
    return write_lif


@pytest.fixture(scope="session")
def native_imagej():
    """Use Fiji in CI, or explicitly supplied ImageJ/patcher JARs locally."""
    if os.environ.get("MCA_RUN_IMAGEJ_TESTS") != "1":
        pytest.skip("Set MCA_RUN_IMAGEJ_TESTS=1 for native ImageJ tests")
    jars = os.environ.get("MCA_TEST_IMAGEJ_CLASSPATH")
    if jars:
        import jpype

        jpype.startJVM(
            "-Djava.awt.headless=true",
            "--add-opens=java.base/java.lang=ALL-UNNAMED",
            classpath=jars.split(os.pathsep),
        )
        jpype.JClass("net.imagej.patcher.LegacyInjector").preinit()
        yield
        from mca_tools.imagej import shutdown_workers

        shutdown_workers()
        jpype.shutdownJVM()
    else:
        import logging

        from mca_tools.imagej import session

        with session(logging.getLogger("test.imagej")) as context:
            yield context
