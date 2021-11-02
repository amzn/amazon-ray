import ray.experimental.data.deltacat.aws.clients as aws_utils
import logging
import pyarrow as pa
import pandas as pd
import numpy as np
import multiprocessing
import s3fs
from ray.experimental.data.deltacat import logs
from ray.experimental.data.deltacat.aws.redshift.model import manifest as rsm, \
    manifest_entry as rsme, manifest_meta as rsmm
from ray.experimental.data.deltacat.aws.constants import TIMEOUT_ERROR_CODES
from ray.experimental.data.deltacat.types.media import ContentType, ContentEncoding
from ray.experimental.data.deltacat.types.tables import TABLE_TYPE_TO_READER_FUNC, \
    TABLE_CLASS_TO_SIZE_FUNC
from ray.experimental.data.deltacat.types.media import TableType
from ray.experimental.data.deltacat.exceptions import RetryableError, NonRetryableError
from typing import Any, Callable, Dict, List, Optional, Generator, Union
from botocore.client import BaseClient
from botocore.exceptions import ClientError
from functools import partial
from tenacity import Retrying
from tenacity import wait_random_exponential
from tenacity import stop_after_delay
from tenacity import retry_if_exception_type
from uuid import uuid4

logger = logs.configure_application_logger(logging.getLogger(__name__))


class ParsedURL:
    def __init__(
            self,
            url: str):

        from urllib.parse import urlparse

        self._parsed = urlparse(
            url,
            allow_fragments=False  # support '#' in path
        )
        if self._parsed.query:  # support '?' in path
            self.key = \
                f"{self._parsed.path.lstrip('/')}?{self._parsed.query}"
        else:
            self.key = self._parsed.path.lstrip('/')
        self.bucket = self._parsed.netloc
        self.url = self._parsed.geturl()


def parse_s3_url(url: str) -> ParsedURL:
    return ParsedURL(url)


def s3_client_cache(
        region: Optional[str],
        **kwargs) -> BaseClient:

    return aws_utils.client_cache(
        "s3",
        region,
        **kwargs
    )


def get_object_at_url(
        url: str,
        **s3_client_kwargs) -> Dict[str, Any]:

    s3 = s3_client_cache(
        None,
        **s3_client_kwargs)

    parsed_s3_url = parse_s3_url(url)
    return s3.get_object(
        Bucket=parsed_s3_url.bucket,
        Key=parsed_s3_url.key
    )


def filter_objects_by_prefix(
        bucket: str,
        prefix: str,
        **s3_client_kwargs) -> Generator[Dict[str, Any], None, None]:

    s3 = s3_client_cache(
        None,
        **s3_client_kwargs
    )
    params = {"Bucket": bucket, "Prefix": prefix}
    more_objects_to_list = True
    while more_objects_to_list:
        response = s3.list_objects_v2(**params)
        if "Contents" in response:
            for obj in response["Contents"]:
                yield obj
        params["ContinuationToken"] = response.get("NextContinuationToken")
        more_objects_to_list = params["ContinuationToken"] is not None


def read_file(
        s3_url: str,
        content_type: ContentType,
        content_encoding: ContentEncoding = ContentEncoding.IDENTITY,
        table_type: TableType = TableType.PYARROW,
        file_reader_kwargs: Optional[Dict[str, Any]] = None,
        **s3_client_kwargs) \
        -> Union[pa.Table, pd.DataFrame, np.ndarray]:

    reader = TABLE_TYPE_TO_READER_FUNC[table_type.value]
    try:
        table = reader(
            s3_url,
            content_type.value,
            content_encoding.value,
            file_reader_kwargs,
            **s3_client_kwargs
        )
        return table
    except ClientError as e:
        if e.response["Error"]["Code"] in TIMEOUT_ERROR_CODES:
            # Timeout error not caught by botocore
            raise RetryableError(f"Retry table download from: {s3_url}") \
                from e
        raise NonRetryableError(f"Failed table table download from: {s3_url}") \
            from e


def upload_sliced_table(
        table: Union[pa.Table, pd.DataFrame, np.ndarray],
        s3_url_prefix: str,
        s3_file_system: s3fs.S3FileSystem,
        max_records_per_entry: Optional[int],
        s3_table_writer_func: Callable,
        table_slicer_func: Callable,
        s3_table_writer_kwargs: Optional[Dict[str, Any]] = None,
        content_type: ContentType = ContentType.PARQUET,
        **s3_client_kwargs) \
        -> List[Dict[str, Any]]:

    # @retry decorator can't be pickled by Ray, so wrap upload in Retrying
    retrying = Retrying(
        wait=wait_random_exponential(multiplier=1, max=60),
        stop=stop_after_delay(30 * 60),
        retry=retry_if_exception_type(RetryableError)
    )

    manifest_entries = []
    table_record_count = len(table)
    if max_records_per_entry is None or not table_record_count:
        # write the whole table to a single s3 file
        manifest_entry = retrying.call(
            upload_table,
            table,
            f"{s3_url_prefix}/{uuid4()}",
            s3_file_system,
            s3_table_writer_func,
            s3_table_writer_kwargs,
            content_type,
            **s3_client_kwargs
        )
        manifest_entries.append(manifest_entry)
    else:
        # iteratively write table slices
        table_slices = table_slicer_func(
            table,
            max_records_per_entry
        )
        for table_slice in table_slices:
            manifest_entry = retrying.call(
                upload_table,
                table_slice,
                f"{s3_url_prefix}/{uuid4()}",
                s3_file_system,
                s3_table_writer_func,
                s3_table_writer_kwargs,
                **s3_client_kwargs
            )
            manifest_entries.append(manifest_entry)

    return manifest_entries


def upload_table(
        table: Union[pa.Table, pd.DataFrame, np.ndarray],
        s3_url: str,
        s3_file_system: s3fs.S3FileSystem,
        s3_table_writer_func: Callable,
        s3_table_writer_kwargs: Optional[Dict[str, Any]],
        content_type: ContentType = ContentType.PARQUET,
        **s3_client_kwargs) -> Dict[str, Any]:
    """
    Writes the given table to an S3 file and returns a Redshift
    manifest entry describing the uploaded file.
    """
    if s3_table_writer_kwargs is None:
        s3_table_writer_kwargs = {}

    s3_table_writer_func(
        table,
        s3_url,
        s3_file_system,
        content_type.value,
        **s3_table_writer_kwargs
    )
    table_size = None
    table_size_func = TABLE_CLASS_TO_SIZE_FUNC.get(type(table))
    if table_size_func:
        table_size = table_size_func(table)
    else:
        logger.warn(f"Unable to estimate '{type(table)}' table size.")
    try:
        return rsme.from_s3_obj_url(
            s3_url,
            len(table),
            table_size,
            **s3_client_kwargs,
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            # s3fs may swallow S3 errors - we were probably throttled
            raise RetryableError(f"Retry table upload to: {s3_url}") \
                from e
        raise NonRetryableError(f"Failed table upload to: {s3_url}") \
            from e


def download_manifest_entry(
        manifest_entry: Dict[str, Any],
        token_holder: Optional[Dict[str, Any]] = None,
        table_type: TableType = TableType.PYARROW,
        file_reader_kwargs: Optional[Dict[str, Any]] = None) -> \
        Union[pa.Table, pd.DataFrame, np.ndarray]:

    s3_client_kwargs = {
        "aws_access_key_id": token_holder["accessKeyId"],
        "aws_secret_access_key": token_holder["secretAccessKey"],
        "aws_session_token": token_holder["sessionToken"]
    } if token_holder else {}
    content_type = rsmm.get_content_type(rsme.get_meta(manifest_entry))
    content_encoding = rsmm.get_content_encoding(rsme.get_meta(manifest_entry))
    s3_url = rsme.get_uri(manifest_entry)
    if s3_url is None:
        s3_url = rsme.get_url(manifest_entry)
    table = read_file(
        s3_url,
        ContentType(content_type),
        ContentEncoding(content_encoding),
        table_type,
        file_reader_kwargs,
        **s3_client_kwargs
    )
    return table


def _download_manifest_entries_in_order(
        manifest: Dict[str, Any],
        token_holder: Optional[Dict[str, Any]] = None,
        table_type: TableType = TableType.PYARROW,
        file_reader_kwargs: Optional[Dict[str, Any]] = None) \
        -> List[Union[pa.Table, pd.DataFrame, np.ndarray]]:

    return [
        download_manifest_entry(e, token_holder, table_type, file_reader_kwargs)
        for e in rsm.get_entries(manifest)
    ]


def _download_manifest_entries_parallel(
        manifest: Dict[str, Any],
        token_holder: Optional[Dict[str, Any]] = None,
        table_type: TableType = TableType.PYARROW,
        max_parallelism: int = 1,
        file_reader_kwargs: Optional[Dict[str, Any]] = None) \
        -> List[Union[pa.Table, pd.DataFrame, np.ndarray]]:

    tables = []
    pool = multiprocessing.Pool(max_parallelism)
    downloader = partial(
        download_manifest_entry,
        token_holder=token_holder,
        table_type=table_type,
        file_reader_kwargs=file_reader_kwargs,
    )
    for table in pool.map(downloader, [e for e in rsm.get_entries(manifest)]):
        tables.append(table)
    return tables


def download_manifest_entries(
        manifest: Dict[str, Any],
        token_holder: Optional[Dict[str, Any]] = None,
        table_type: TableType = TableType.PYARROW,
        max_parallelism: int = 1,
        file_reader_kwargs: Optional[Dict[str, Any]] = None) \
        -> List[Union[pa.Table, pd.DataFrame, np.ndarray]]:

    if max_parallelism <= 1:
        return _download_manifest_entries_in_order(
            manifest,
            token_holder,
            table_type,
            file_reader_kwargs,
        )
    else:
        return _download_manifest_entries_parallel(
            manifest,
            token_holder,
            table_type,
            max_parallelism,
            file_reader_kwargs,
        )


def upload(
        s3_url: str,
        body,
        **s3_client_kwargs):

    # TODO: add tenacity retrying
    parsed_s3_url = parse_s3_url(s3_url)
    s3 = s3_client_cache(**s3_client_kwargs)
    return s3.put_object(
        Body=body,
        Bucket=parsed_s3_url.bucket,
        Key=parsed_s3_url.key,
    )


def download(
        s3_url: str,
        fail_if_not_found: bool = True,
        **s3_client_kwargs):

    # TODO: add tenacity retrying
    parsed_s3_url = parse_s3_url(s3_url)
    s3 = s3_client_cache(**s3_client_kwargs)
    try:
        return s3.get_object(
            Bucket=parsed_s3_url.bucket,
            Key=parsed_s3_url.key,
        )
    except ClientError as e:
        if fail_if_not_found:
            raise
        else:
            if e.response['Error']['Code'] != "404":
                if e.response['Error']['Code'] != 'NoSuchKey':
                    raise
            logger.info(
                f"file not found: {s3_url}")
    except s3.exceptions.NoSuchKey:
        if fail_if_not_found:
            raise
        else:
            logger.info(
                f"file not found: {s3_url}")
    return None
