import os

import scyjava

from mca_tools.fiji_config import FIJI_REPOSITORIES, configure_runtime


def test_ome_resolution_preserves_existing_maven_and_jvm_options(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("MAVEN_OPTS", "-Xmx512m -Duser.option=keep")
    monkeypatch.setenv("MCA_RUN_TMP", str(tmp_path))
    monkeypatch.setattr(scyjava.config, "_options", ["-Xmx2g"])
    monkeypatch.setattr(scyjava.config, "_repositories", {})

    configure_runtime()
    configure_runtime()

    assert os.environ["MAVEN_OPTS"] == "-Xmx512m -Duser.option=keep"
    assert scyjava.config.get_repositories() == FIJI_REPOSITORIES
    assert "-Xmx2g" in scyjava.config.get_options()
    assert "-Djava.io.tmpdir=" + str(tmp_path) in scyjava.config.get_options()
    assert not scyjava.jvm_started()


def test_configuration_without_owned_temporary_directory(monkeypatch):
    monkeypatch.delenv("MAVEN_OPTS", raising=False)
    monkeypatch.delenv("MCA_RUN_TMP", raising=False)
    monkeypatch.setattr(scyjava.config, "_repositories", {})
    monkeypatch.setattr(scyjava.config, "_options", ["-Xmx2g"])
    configure_runtime()
    assert "MAVEN_OPTS" not in os.environ
    assert scyjava.config.get_options() == ["-Xmx2g"]
