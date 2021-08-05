from ray.experimental.data.deltacat.storage.model import list_result as lr
from ray.experimental.data.deltacat.storage import interface as unimplemented_deltacat_storage


def run_all(dc_storage = unimplemented_deltacat_storage):
    """
    Run all examples.
    """

    """
    Example list_namespaces() result containing a single namespace:
    {
        'items': [
            {
                'namespace': 'TestNamespace',
            }
        ],
        'pagination_key': 'dmVyc2lvbmVkVGFibGVOYW1l'
    }
    """
    page_key = ""
    namespaces = []
    while page_key is not None:
        namespaces_list_result = dc_storage.list_namespaces(pagination_key=page_key)
        namespaces.extend(lr.get_items(namespaces_list_result))
        page_key = lr.get_pagination_key(namespaces_list_result)
    print(f"All Namespaces: {namespaces}")

    """
    Example list_tables() result containing a single table:
    {
        'items': [
            {
                'id': {
                    'namespace': 'TestNamespace',
                    'tableName': 'TestTable'
                },
                'description': 'Test table description.',
                'properties': {
                    'testPropertyOne': 'testValueOne',
                    'testPropertyTwo': 'testValueTwo'
                }
            }
        ],
       'pagination_key': 'dmVyc2lvbmVkVGFibGVOYW1l'
    }
    """
    page_key = ""
    test_tables = []
    while page_key is not None:
        tables_list_result = dc_storage.list_tables(
            "TestNamespace",
            pagination_key=page_key,
        )
        test_tables.extend(lr.get_items(tables_list_result))
        page_key = lr.get_pagination_key(tables_list_result)
    print(f"All 'TestNamespace' Tables: {test_tables}")

    """
    Example list_partitions() result containing a single partition:
    {
        'items': [
            {
                'partitionKeyValues': ['1', '2017-08-31T00:00:00.000Z']
            }
        ],
        'pagination_key': 'dmVyc2lvbmVkVGFibGVOYW1l'
    }
    """
    # Partitions will automatically be returned for the latest active version of
    # the specified table.
    page_key = ""
    table_partitions = []
    while page_key is not None:
        partitions_list_result = dc_storage.list_partitions(
            "TestNamespace",
            "TestTable",
            pagination_key=page_key
        )
        table_partitions.extend(lr.get_items(partitions_list_result))
        page_key = lr.get_pagination_key(partitions_list_result)
    print(f"All Table Partitions: {table_partitions}")

    """
    Example list_deltas result containing a single delta:
    {
        'items': [
            {
                'type': 'upsert',
                'locator": {
                    'streamPosition': 1551898425276,
                    'partitionLocator': {
                        'partitionId': 'de75623a-7adf-4cf0-b982-7b514502be82'
                        'partitionValues': ['1', '2018-03-06T00:00:00.000Z'],
                        'streamLocator': {
                            'namespace': 'TestNamespace',
                            'tableName': 'TestTable',
                            'tableVersion': '1',
                            'streamId': 'dbcbbf56-4bcb-4b94-8cf2-1c6d57ccfe74',
                            'storageType': 'AwsGlueCatalog'
                        }
                    }
                },
                'properties': {
                    'parent_stream_position': '1551898423165'
                },
                'meta': {
                    'contentLength': 9423157342,
                    'fileCount': 117,
                    'recordCount': 188463146,
                    'sourceContentLength': 37692629368,
                }
            }
        ],
        'paginationKey': 'enQzd3mqcnNkQIFkaHQ1ZW2m'
    }
    """
    # Deltas will automatically be returned for the latest active version of the
    # specified table.
    page_key = ""
    partition_deltas = []
    while page_key is not None:
        deltas_list_result = dc_storage.list_deltas(
            "TestNamespace",
            "TestTable",
            ["1", "2018-03-06T00:00:00.000Z"],
            pagination_key=page_key,
        )
        partition_deltas.extend(lr.get_items(deltas_list_result))
        page_key = lr.get_pagination_key(deltas_list_result)
    print(f"All Partition Deltas: {partition_deltas}")


if __name__ == '__main__':
    run_all()
