"""Own Fiji initialization and shutdown at the command boundary."""

import os
import sys
from contextlib import contextmanager

FIJI_ENDPOINT = "sc.fiji:fiji:2.14.0"


def shutdown_workers():
    import scyjava

    if scyjava.jvm_started():
        pool = scyjava.jimport("ij.util.ThreadUtil").threadPoolExecutor
        pool.shutdown()
        seconds = scyjava.jimport("java.util.concurrent.TimeUnit").SECONDS
        if not pool.awaitTermination(5, seconds):
            pool.shutdownNow()
            if not pool.awaitTermination(5, seconds):
                raise RuntimeError("ImageJ worker threads did not stop")


@contextmanager
def session(logger):
    import imagej
    import scyjava

    scyjava.config.set_java_constraints(fetch="never")
    if os.environ.get("MCA_RUN_TMP"):
        scyjava.config.add_option(
            "-Djava.io.tmpdir=" + os.environ["MCA_RUN_TMP"]
        )
    logger.info("Initializing %s", FIJI_ENDPOINT)
    instance = None
    try:
        instance = imagej.init(FIJI_ENDPOINT, mode="headless")
        logger.info("IMAGEJ_READY | %s", instance.getVersion())
        yield instance
    finally:
        failed = sys.exc_info()[0] is not None
        try:
            shutdown_workers()
        except Exception:
            logger.exception("Could not stop ImageJ workers")
            if not failed:
                raise
        finally:
            if instance is not None:
                try:
                    instance.context().dispose()
                except Exception:
                    logger.exception("Could not dispose ImageJ context")
                    if not failed:
                        raise
            logger.info("ImageJ context closed")
