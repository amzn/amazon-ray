import json
import logging
import pyarrow as pa
import ray
import s3fs
import time
import pyarrow.compute as pc
import numpy as np
from ray import cloudpickle

from ray.experimental.data.deltacat import logs
from collections import defaultdict
from itertools import repeat
from ray.experimental.data.deltacat.storage.model.types import DeltaType
from ray.experimental.data.deltacat.utils.common import sha1_digest
from ray.experimental.data.deltacat.aws import s3u as s3_utils
from ray.experimental.data.deltacat.aws.redshift.model import manifest as rsm, manifest_meta as rsmm
from ray.experimental.data.deltacat.types.media import ContentType, ContentEncoding
from ray.experimental.data.deltacat.types.tables import get_table_writer, get_table_slicer
from ray.experimental.data.deltacat.compute.compactor.model import delta_file_envelope as dfe, \
    dedupe_result as dr
from ray.experimental.data.deltacat.compute.compactor.utils.system_columns import \
    project_delta_file_metadata_on_table
from ray.experimental.data.deltacat.compute.compactor.utils import system_columns as sc
from ray.experimental.data.deltacat.storage.model import partition_locator as pl
from typing import Any, Dict, List, Optional, Tuple

logger = logs.configure_application_logger(logging.getLogger(__name__))


def _get_pk_index_s3_key(
        compacted_partition_locator: Dict[str, Any],
        hb_index: int,
        pk_index_version: int) -> str:

    partition_locator_hexdigest = pl.hexdigest(compacted_partition_locator)
    return f"{partition_locator_hexdigest}/{pk_index_version}/{hb_index}"


def _get_pk_index_s3_url_base(
        s3_bucket: str,
        compacted_partition_locator: Dict[str, Any],
        hash_bucket_index: int,
        pk_index_version: int) -> str:

    s3_key = _get_pk_index_s3_key(
        compacted_partition_locator,
        hash_bucket_index,
        pk_index_version,
    )
    return "s3://{}/{}".format(s3_bucket, s3_key)


def _get_pk_index_manifest_s3_url(pk_index_s3_url_base: str) -> str:
    return f"{pk_index_s3_url_base}.json"


def _write_primary_key_index_files(
        table: pa.Table,
        pk_index_s3_url_base: str,
        records_per_index_file: int) -> Dict[str, int]:

    s3_file_system = s3fs.S3FileSystem(
        anon=False,
        s3_additional_kwargs={
            "ContentType": ContentType.PARQUET.value,
            "ContentEncoding": ContentEncoding.IDENTITY.value,
        }
    )
    manifest_entries = s3_utils.upload_sliced_table(
        table,
        pk_index_s3_url_base,
        s3_file_system,
        records_per_index_file,
        get_table_writer(table),
        get_table_slicer(table),
    )
    manifest = rsm.of(manifest_entries)
    s3_utils.upload(
        _get_pk_index_manifest_s3_url(pk_index_s3_url_base),
        str(json.dumps(manifest))
    )
    return dr.of(
        len(manifest_entries),
        table.nbytes,
        rsmm.get_content_length(manifest),
        len(table),
    )


def union_primary_key_indices(
        s3_bucket: str,
        compacted_partition_locator: Dict[str, Any],
        prev_compacted_delta_stream_pos: Optional[int],
        hash_bucket_index: int,
        df_envelopes_list,
        pk_index_version: int) -> pa.Table:

    logger.info(f"Reading dedupe input for {len(df_envelopes_list)} "
                f"delta file envelope lists...")
    # read compacted input parquet files first
    # (which implicitly have older stream positions than deltas)
    hb_tables = []
    pk_index_manifest_s3_url = _get_pk_index_manifest_s3_url(
        _get_pk_index_s3_url_base(
            s3_bucket,
            compacted_partition_locator,
            hash_bucket_index,
            pk_index_version,
        )
    )
    result = s3_utils.download(pk_index_manifest_s3_url, False)
    if result:
        logger.info(f"Found existing primary key index manifest at: "
                    f"{pk_index_manifest_s3_url}. Compacted partition: "
                    f"{compacted_partition_locator}")
        pk_index_manifest = json.loads(result["Body"].read().decode("utf-8"))
        tables = s3_utils.download_manifest_entries(pk_index_manifest)
        if tables:
            if prev_compacted_delta_stream_pos is None:
                raise ValueError(f"Unexpected Error: No previous compacted "
                                 f"delta stream position associated with "
                                 f"compacted partition: "
                                 f"{compacted_partition_locator}")
            prior_pk_index_table = pa.concat_tables(tables)
            prior_pk_index_table = sc.append_stream_position_column(
                prior_pk_index_table,
                repeat(
                    prev_compacted_delta_stream_pos,
                    len(prior_pk_index_table),
                ),
            )
            prior_pk_index_table = sc.append_delta_type_col(
                prior_pk_index_table,
                repeat(
                    sc.delta_type_to_field(DeltaType.UPSERT),
                    len(prior_pk_index_table),
                )
            )
            prior_pk_index_table = sc.append_is_source_col(
                prior_pk_index_table,
                repeat(
                    False,
                    len(prior_pk_index_table),
                )
            )
            hb_tables.append(prior_pk_index_table)
        else:
            logger.warn(f"Primary key index manifest is empty at: "
                        f"{pk_index_manifest_s3_url}. Compacted partition: "
                        f"{compacted_partition_locator}")
    else:
        logger.info(f"No existing primary key index manifest found at: "
                    f"{pk_index_manifest_s3_url}. Compacted partition: "
                    f"{compacted_partition_locator}")

    # sort by delta file stream position now instead of sorting every row later
    df_envelopes = [d for dfe_list in df_envelopes_list for d in dfe_list]
    df_envelopes = sorted(
        df_envelopes,
        key=lambda df: (dfe.get_stream_position(df), dfe.get_file_index(df)),
        reverse=False,  # ascending
    )
    for delta_file in df_envelopes:
        hb_tables.append(project_delta_file_metadata_on_table(delta_file))

    hb_table = pa.concat_tables(hb_tables)

    return hb_table


def drop_duplicates_by_primary_key_hash(table: pa.Table) -> pa.Table:
    # TODO: drop all primary key occurrences for DELETE delta types
    value_to_last_row_idx = {}
    row_idx = 0
    for chunk in sc.pk_hash_column(table).iterchunks():
        for val in chunk.to_numpy(zero_copy_only=False):
            value_to_last_row_idx[val] = row_idx
            row_idx += 1
    return table.take(list(value_to_last_row_idx.values()))


def write_dest_primary_key_index(
        s3_bucket: str,
        new_compacted_partition_locator: Dict[str, Any],
        max_rows_per_index_file: int,
        max_rows_per_mat_file: int,
        num_materialize_buckets: int,
        dedupe_task_index: int,
        deduped_tables: List[Tuple[int, pa.Table]],
        row_counts: Dict[int, Dict[str, Dict[int, int]]],
        pk_index_version: int) -> Dict[str, int]:

    # TODO: move to RecordCountsPendingMaterialize.finalize()?
    file_idx = 0
    prev_file_idx = 0
    dest_file_idx = defaultdict(defaultdict(defaultdict(int)))
    dest_file_row_idx = defaultdict(defaultdict(defaultdict(int)))
    for mat_bucket in sorted(row_counts.keys()):
        mat_bucket_row_idx = 0
        sorted_src_file_ids = sorted(row_counts[mat_bucket].keys())
        for src_file_id in sorted_src_file_ids:
            sorted_dd_tasks = sorted(row_counts[mat_bucket][src_file_id].keys())
            for dd_task_idx in sorted_dd_tasks:
                dest_file_row_idx[mat_bucket][src_file_id][dd_task_idx] = \
                    mat_bucket_row_idx % max_rows_per_mat_file
                file_idx = prev_file_idx + int(
                    mat_bucket_row_idx / max_rows_per_mat_file
                )
                dest_file_idx[mat_bucket][src_file_id][dd_task_idx] = file_idx
                row_count = row_counts[mat_bucket][src_file_id][dd_task_idx]
                mat_bucket_row_idx += row_count
        prev_file_idx = file_idx + 1

    src_file_id_row_counts = defaultdict(int)
    for hb_index, table in deduped_tables:
        stream_pos_col = sc.stream_position_column_np(table)
        file_idx_col = sc.file_index_column_np(table)
        dest_file_idx_col = []
        dest_file_row_idx_col = []
        for row_idx in range(len(table)):
            src_file_id = (
                stream_pos_col[row_idx],
                file_idx_col[row_idx],
            )
            mat_bucket = file_id_to_mat_bucket_index(
                src_file_id,
                num_materialize_buckets,
            )
            dest_file_start_idx = \
                dest_file_idx[mat_bucket][src_file_id][dedupe_task_index]
            dest_file_row_idx_offset = src_file_id_row_counts[src_file_id] + \
                dest_file_row_idx[mat_bucket][src_file_id][dedupe_task_index]
            dest_file_idx_offset = int(
                dest_file_row_idx_offset / max_rows_per_mat_file
            )
            dest_file_idx = dest_file_start_idx + dest_file_idx_offset
            dest_file_idx_col.append(dest_file_idx)
            dest_file_row_idx = dest_file_row_idx_offset % max_rows_per_mat_file
            dest_file_row_idx_col.append(dest_file_row_idx)
            src_file_id_row_counts[src_file_id] += 1
        table = table.drop([
            sc._PARTITION_STREAM_POSITION_COLUMN_NAME,
            sc._ORDERED_FILE_IDX_COLUMN_NAME,
            sc._ORDERED_RECORD_IDX_COLUMN_NAME,
        ])
        table = sc.append_file_idx_column(table, dest_file_idx_col)
        table = sc.append_record_idx_col(table, dest_file_row_idx_col)
        pk_index_s3_url_base = _get_pk_index_s3_url_base(
            s3_bucket,
            new_compacted_partition_locator,
            hb_index,
            pk_index_version,
        )
        return _write_primary_key_index_files(
            table,
            pk_index_s3_url_base,
            max_rows_per_index_file,
        )


def file_id_to_mat_bucket_index(file_id_tuple, materialize_bucket_count):
    file_id_str = f"{file_id_tuple[0]}|{file_id_tuple[1]}|{file_id_tuple[2]}"
    digest = sha1_digest(bytes(file_id_str, "utf-8"))
    return int.from_bytes(digest, "big") % materialize_bucket_count


@ray.remote
class RecordCountsPendingMaterialize:
    def __init__(self, expected_result_count):
        self.record_counts = defaultdict(defaultdict(defaultdict(int)))
        self.expected_result_count = expected_result_count
        self.actual_result_count = 0

    def add_record_counts(self, result_idx, record_counts):
        for mat_bucket, src_file_id_rows in record_counts.items():
            for src_file_id, rows in src_file_id_rows.items():
                self.record_counts[mat_bucket][src_file_id][result_idx] += rows
        self.actual_result_count += 1

    def get_record_counts(self):
        return self.record_counts

    def get_expected_result_count(self):
        return self.expected_result_count

    def get_actual_result_count(self):
        return self.actual_result_count

    def is_finalized(self):
        return self.actual_result_count == self.expected_result_count


@ray.remote(num_returns=3)
def dedupe(
        compaction_artifact_s3_bucket: str,
        compacted_partition_locator: Dict[str, Any],
        new_compacted_partition_locator: Dict[str, Any],
        object_ids: List[Any],
        sort_keys: List[Tuple[str, str]],
        max_records_per_index_file: int,
        max_records_per_materialized_file: int,
        num_materialize_buckets: int,
        dedupe_task_index: int,
        record_counts_pending_materialize,
        prev_compacted_delta_stream_position: Optional[int],
        pk_index_version: int):

    logger.info(f"Starting dedupe task...")
    # TODO: there is a risk of running out of memory here in cases of severe
    #  skew of primary key updates
    object_refs = [cloudpickle.loads(obj_id_pkl) for obj_id_pkl in object_ids]
    logger.info(f"Getting delta file envelope groups object refs...")
    delta_file_envelope_groups_list = ray.get(object_refs)
    hb_index_to_delta_file_envelopes_list = defaultdict(list)
    for delta_file_envelope_groups in delta_file_envelope_groups_list:
        for hb_idx in range(len(delta_file_envelope_groups)):
            dfes = delta_file_envelope_groups[hb_idx]
            if dfes is not None:
                hb_index_to_delta_file_envelopes_list[hb_idx].append(dfes)
    src_file_id_to_row_indices = defaultdict(list)
    deduped_tables = []
    logger.info(f"Running {len(hb_index_to_delta_file_envelopes_list)} "
                f"dedupe rounds...")
    for hb_idx, dfe_list in hb_index_to_delta_file_envelopes_list.items():
        table = union_primary_key_indices(
            compaction_artifact_s3_bucket,
            compacted_partition_locator,
            prev_compacted_delta_stream_position,
            hb_idx,
            dfe_list,
            pk_index_version,
        )
        logger.info("Dedupe round input record count: ", len(table))

        # sort by sort keys
        if len(sort_keys):
            # TODO: convert to O(N) dedupe w/ sort keys
            sort_keys.extend([
                (sc._PARTITION_STREAM_POSITION_COLUMN_NAME, "ascending"),
                (sc._ORDERED_FILE_IDX_COLUMN_NAME, "ascending"),
            ])
            table = table.take(pc.sort_indices(table, sort_key=sort_keys))

        # drop duplicates by primary key hash column
        table = drop_duplicates_by_primary_key_hash(table)
        table = table.drop([sc._DELTA_TYPE_COLUMN_NAME])
        logger.info("Dedupe round output record count: ", len(table))

        deduped_tables.append((hb_idx, table))

        stream_position_col = sc.stream_position_column_np(table)
        file_idx_col = sc.file_index_column_np(table)
        row_idx_col = sc.record_index_column_np(table)
        is_source_col = sc.is_source_column_np(table)
        for row_idx in range(len(table)):
            src_file_id = (
                is_source_col[row_idx],
                stream_position_col[row_idx],
                file_idx_col[row_idx],
            )
            # TODO(pdames): merge contiguous record number ranges
            src_file_id_to_row_indices[src_file_id].append(row_idx_col[row_idx])

    logger.info(f"Finished all dedupe rounds...")
    mat_bucket_to_src_file_record_count = defaultdict(dict)
    mat_bucket_to_src_file_records = defaultdict(dict)
    for src_file_id, src_row_indices in src_file_id_to_row_indices.items():
        mat_bucket = file_id_to_mat_bucket_index(
            src_file_id,
            num_materialize_buckets,
        )
        mat_bucket_to_src_file_records[mat_bucket][src_file_id] = np.array(
            src_row_indices,
        )
        mat_bucket_to_src_file_record_count[mat_bucket][src_file_id] = \
            len(src_row_indices)

    mat_bucket_to_dd_idx_obj_id = {}
    object_refs = []
    for mat_bucket, src_file_records in mat_bucket_to_src_file_records.items():
        object_ref = ray.put(src_file_records)
        object_refs.append(object_ref)
        mat_bucket_to_dd_idx_obj_id[mat_bucket] = (
            dedupe_task_index,
            cloudpickle.dumps(object_ref),
        )
    logger.info(f"Count of materialize buckets with object refs: "
                f"{len(mat_bucket_to_dd_idx_obj_id)}")

    record_counts_pending_materialize.add_record_counts(
        dedupe_task_index,
        mat_bucket_to_src_file_record_count,
    )

    # wait for all dedupe tasks to reach this point before continuing
    logger.info(
        f"Waiting for all dedupe tasks to finish writing record counts...")
    finalized = False
    while not finalized:
        finalized = ray.get(
            record_counts_pending_materialize.is_finalized.remote()
        )
        time.sleep(0.25)
    logger.info(f"Writing destination primary key index...")
    dedupe_result = write_dest_primary_key_index(
        compaction_artifact_s3_bucket,
        new_compacted_partition_locator,
        max_records_per_index_file,
        max_records_per_materialized_file,
        num_materialize_buckets,
        dedupe_task_index,
        deduped_tables,
        record_counts_pending_materialize.get_record_counts(),
        1,
    )
    logger.info(f"Finished dedupe task...")
    return mat_bucket_to_dd_idx_obj_id, object_refs, dedupe_result
