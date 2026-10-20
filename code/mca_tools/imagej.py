"""Own Fiji initialization and shutdown at the command boundary."""

import sys
from contextlib import contextmanager

from .fiji_config import FIJI_ENDPOINT, configure_runtime


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

    configure_runtime()
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
