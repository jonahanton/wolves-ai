from __future__ import annotations

import logging

import boto3

from wolves.config import Settings

logger = logging.getLogger(__name__)


def ensure_table(*, table_name: str, region: str, endpoint_url: str | None = None) -> bool:
    """Create the single table if absent; return True when newly created."""
    client = boto3.client("dynamodb", region_name=region, endpoint_url=endpoint_url)
    try:
        client.create_table(
            TableName=table_name,
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
    except client.exceptions.ResourceInUseException:
        return False
    client.get_waiter("table_exists").wait(TableName=table_name)
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings()
    created = ensure_table(
        table_name=settings.dynamo_table,
        region=settings.aws_region,
        endpoint_url=settings.dynamo_endpoint or None,
    )
    logger.info("table %s %s", settings.dynamo_table, "created" if created else "already exists")


if __name__ == "__main__":
    main()
