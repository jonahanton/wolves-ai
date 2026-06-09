from __future__ import annotations

from moto import mock_aws

from wolves.store.init import ensure_table


@mock_aws
def test_second_create_is_a_no_op():
    assert ensure_table(table_name="wolves-forecaster", region="eu-west-2") is True
    assert ensure_table(table_name="wolves-forecaster", region="eu-west-2") is False
