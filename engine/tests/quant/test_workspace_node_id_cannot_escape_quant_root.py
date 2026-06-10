import pytest

from wolves.quant.workspace import QuantWorkspace


@pytest.mark.parametrize("node_id", ["..", "../evil", "/etc", "a/../../b", ""])
def test_llm_authored_node_id_stays_inside_quant_root(tmp_path, node_id):
    quant_root = tmp_path / "quant"
    workspace = QuantWorkspace(quant_root, node_id)
    assert quant_root.resolve() in workspace.dir.resolve().parents
