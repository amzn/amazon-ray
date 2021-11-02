import numpy as np
import pyarrow as pa
from fsspec import AbstractFileSystem

from ray.experimental.data.deltacat.types.media import ContentType
from ray.experimental.data.deltacat.utils import pyarrow as pa_utils
from ray.experimental.data.deltacat.utils import pandas as pd_utils
from typing import List, Optional, Dict, Any


def slice_ndarray(
        np_array: np.ndarray,
        max_len: Optional[int]) -> List[np.ndarray]:
    """
    Iteratively creates max_len slices from the first dimension of an ndarray.
    """
    if max_len is None:
        return [np_array]

    # Slice along the first dimension of the ndarray.
    return [np_array[i:i + max_len] for i in range(0, len(np_array), max_len)]


def s3_file_to_ndarray(
        s3_url: str,
        content_type: str,
        content_encoding: str,
        pd_read_func_kwargs: Optional[Dict[str, Any]] = None,
        **s3_client_kwargs) -> np.ndarray:
    # TODO: Compare perf to s3 -> pyarrow -> pandas [Series/DataFrame] -> numpy
    dataframe = pd_utils.s3_file_to_dataframe(
        s3_url,
        content_type,
        content_encoding,
        pd_read_func_kwargs,
        **s3_client_kwargs
    )
    return dataframe.to_numpy()


def ndarray_size(np_array: np.ndarray) -> int:
    return np_array.nbytes


def ndarray_to_file(
        np_array: np.ndarray,
        path: str,
        file_system: AbstractFileSystem,
        content_type: str = ContentType.PARQUET.value,
        **kwargs):
    """
    Writes the given Numpy ndarray to a file.
    """

    # PyArrow only supports 1D ndarrays, so convert to list of 1D arrays
    np_arrays = [array for array in np_array]
    pa_utils.table_to_file(
        pa.table({"data": np_arrays}),
        path,
        file_system,
        content_type,
        **kwargs
    )
