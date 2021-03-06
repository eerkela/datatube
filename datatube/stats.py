from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import pandas.api.types as pdtypes

from datatube import is_video_id
from datatube.check import is_video_id
from datatube.error import error_trace


AVAILABLE_DTYPES = (object, int, float, complex, str, bool, datetime, timedelta)


def check_dtypes(data: pd.DataFrame, **kwargs) -> bool:
    dtype_lookup = {  # order indicates priority in kwargless lookup
        object: pdtypes.is_object_dtype,  # convert_dtypes -> not a str
        int: pdtypes.is_integer_dtype,
        float: pdtypes.is_float_dtype,
        complex: pdtypes.is_complex_dtype,
        # "numeric": pdtypes.is_numeric_dtype,
        str: pdtypes.is_string_dtype,
        bool: pdtypes.is_bool_dtype,
        datetime: pdtypes.is_datetime64_any_dtype,
        timedelta: pdtypes.is_timedelta64_dtype
    }
    # convert_dtypes always emits a ComplexWarning on complex-valued columns
    warnings.simplefilter("ignore", np.ComplexWarning)

    # kwargless
    if len(kwargs) == 0:
        result = {}
        for col_name in data.columns:
            try:
                column = data[col_name].convert_dtypes()
            except TypeError:
                column = data[col_name]
            for typespec, typecheck in dtype_lookup.items():
                if typecheck(column):
                    result[col_name] = typespec
                    break
        return result

    def check_column(col_name, typespec):
        try:
            column = data[col_name].convert_dtypes()
        except TypeError:
            column = data[col_name]
        # single typespec
        if not isinstance(typespec, (tuple, list, set)):
            if typespec == str and dtype_lookup[object](column):
                return False  # column is better described as object
            return dtype_lookup[typespec](column)
        # multiple typespecs
        results = []
        for ts in typespec:
            if ts == str and dtype_lookup[object](column):
                results.append(False)
            else:
                results.append(dtype_lookup[ts](column))
        return any(results)

    return all(check_column(col_name, typespec)
               for col_name, typespec in kwargs.items())


def coerce_dtypes(data: pd.DataFrame, **kwargs) -> pd.DataFrame:
    dtype_lookup = {
        object: np.dtype("O"),
        int: pd.Int64Dtype(),  # numpy: np.dtype(np.int64)  NOT NULLABLE
        float: pd.Float64Dtype(),  # numpy: np.dtype(np.float64)
        complex: np.dtype(np.complex128),
        # "numeric": pd.Float64Dtype(),  # numpy: np.dtype(np.float64)
        str: pd.StringDtype(),  # numpy: np.dtype("O")
        bool: pd.BooleanDtype(),  # numpy: np.dtype("bool")
        datetime: np.dtype("datetime64[ns]"),
        # datetime: pd.DatetimeTZDtype(),
        timedelta: np.dtype("timedelta64[ns]")
    }
    # pd.to_datetime(..., utc=True)

    # kwargless
    if len(kwargs) == 0:
        atomics = [t.__name__ if isinstance(t, type) else str(t)
                   for t in dtype_lookup]
        err_msg = (f"[{error_trace()}] `coerce_dtypes` must be invoked with "
                   f"at least one keyword argument mapping a column in `data` "
                   f"to an atomic data type: {tuple(atomics)}")
        raise RuntimeError(err_msg)

    # kwargs
    result = data.copy()
    for col_name, typespec in kwargs.items():
        if check_dtypes(data, **{col_name: typespec}):
            continue
        try:
            result[col_name] = result[col_name].astype(dtype_lookup[typespec])
        except KeyError as exc:
            atomics = [t.__name__ if isinstance(t, type) else str(t)
                       for t in dtype_lookup]
            err_msg = (f"[{error_trace()}] typespec not recognized: {typespec} "
                       f"(available values: {set(atomics)})")
            raise KeyError(err_msg) from exc
    return result


class Stats:

    def __init__(self,
                 data: pd.DataFrame | None = None,
                 interpolate: bool = False):
        expected_columns = {  # col_name: typespec
            "video_id": str,
            "timestamp": datetime,
            "views": int,
            "rating": float,
            "likes": int,
            "dislikes": int
        }

        # naked init
        if data is None:
            df = pd.DataFrame(dict.fromkeys(expected_columns, []))
            self._data = coerce_dtypes(df, **expected_columns)

        else:

            # check type
            if not isinstance(data, pd.DataFrame):
                err_msg = (f"[{error_trace()}] `data` must be a "
                           f"pandas.DataFrame (received object of type: "
                           f"{type(data)})")
                raise TypeError(err_msg)

            # check column names match expected
            if set(data.columns) != set(expected_columns):
                missing_columns = set(expected_columns) - set(data.columns)
                extra_columns = set(data.columns) - set(expected_columns)
                err_msg = f"[{error_trace()}] `data` has unexpected columns"
                if missing_columns and extra_columns:
                    context = (f"(missing: {repr(missing_columns)}, extra: "
                               f"{repr(extra_columns)})")
                elif missing_columns:
                    context = f"(missing: {repr(missing_columns)})"
                else:
                    context = f"(extra: {repr(extra_columns)})"
                raise ValueError(f"{err_msg} {context}")

            # check column dtypes
            for col_name, typespec in expected_columns.items():
                if not check_dtypes(data, **{col_name: typespec}):
                    err_msg = (f"[{error_trace()}] column {repr(col_name)} "
                            f"must contain {typespec} data (received: "
                            f"{check_dtypes(data)[col_name]}, head: "
                            f"{list(data[col_name].head())})")
                    raise TypeError(err_msg)

            # format data and drop duplicates/NAs in required columns
            data = coerce_dtypes(data, **expected_columns)
            data = data[list(expected_columns)]  # reorder columns
            data = data.dropna(subset=["video_id", "timestamp"])
            data = data.drop_duplicates(subset=["video_id", "timestamp"])

            # check video_id and timestamp are as expected
            def check_video_id(video_id):
                if not is_video_id(video_id):
                    err_msg = (f"[{error_trace(stack_index=5)}] bad video id: "
                               f"{repr(video_id)}")
                    raise ValueError(err_msg)

            def check_timestamp(timestamp):
                if timestamp.tzinfo is None:
                    err_msg = (f"[{error_trace(stack_index=5)}] timestamp has "
                               f"no timezone: {repr(timestamp)}")
                    raise ValueError(err_msg)
                current_time = datetime.now(timezone.utc)
                if timestamp > current_time:
                    err_msg = (f"[{error_trace(stack_index=5)}] timestamp is "
                               f"in the future: {timestamp} > {current_time}")

            data["video_id"].apply(check_video_id)
            data["timestamp"].apply(check_timestamp)

            # interpolate missing values and save data
            if not interpolate:
                self._data = data
            else:
                # set timestamp as index and do time-based interpolation
                raise NotImplementedError()


        # expected_types = {k: v[0] for k, v in expected_columns.items()}
        # typename_conv = {
        #     int: "integer",
        #     float: "float",
        #     "numeric": "numeric",
        #     str: "string",
        #     bool: "boolean",
        #     datetime: "datetime",
        #     timedelta: "timedelta"
        # }

        # if data is not None:
        #     # check data is dataframe
        #     if not isinstance(data, pd.DataFrame):
        #         err_msg = (f"[{error_trace()}] `data` must be a "
        #                    f"pandas.DataFrame object (received object of "
        #                    f"type: {type(data)})")
        #         raise TypeError(err_msg)

        #     # check column names match expected
        #     if set(data.columns) != set(expected_columns):  # column mismatch
        #         missing_columns = set(expected_columns) - set(data.columns)
        #         extra_columns = set(data.columns) - set(expected_columns)
        #         err_msg = (f"[{error_trace()}] columns of `data` do not "
        #                    f"match expected")
        #         if len(missing_columns) > 0 and len(extra_columns) > 0 :
        #             context = (f"(missing columns: {repr(missing_columns)}, "
        #                        f"extra columns: {repr(extra_columns)})")
        #         elif len(missing_columns) > 0:
        #             context = (f"(missing columns: {repr(missing_columns)})")
        #         else:
        #             context = (f"(extra columns: {repr(extra_columns)})")
        #         raise ValueError(f"{err_msg} {context}")

        #     # check column types and missing values match expected
        #     for col_name, (typespec, na_allowed) in expected_columns.items():
        #         if not check_dtypes(data, **{col_name: typespec}):
        #             err_msg = (f"[{error_trace()}] column {repr(col_name)} "
        #                        f"must contain {typename_conv[typespec]} data")
        #             raise TypeError(err_msg)
        #         if not na_allowed and data[col_name].hasnans:
        #             err_msg = (f"[{error_trace()}] column {repr(col_name)} "
        #                        f"cannot contain missing values")
        #             raise ValueError(err_msg)

        #     # coerce dtypes and sort into expected order
        #     data = coerce_dtypes(data, **expected_types)
        #     self._data = data[list(expected_columns)]

        # else:  # create new df and set expected dtypes
        #     data = pd.DataFrame(dict.fromkeys(list(expected_columns), []))
        #     self._data = coerce_dtypes(data, **expected_types)

    @classmethod
    def from_csv(cls, csv_path: Path) -> Stats:
        err_msg = (f"[{error_trace(cls)}] `csv_path` must be a Path-like "
                   f"object pointing to a .csv file on local storage")
        if not isinstance(csv_path, Path):
            context = f"(received object of type: {type(csv_path)})"
            raise TypeError(f"{err_msg} {context}")
        if not csv_path.exists():
            context = f"(path does not exist: {csv_path})"
            raise ValueError(f"{err_msg} {context}")
        if not csv_path.is_file() or csv_path.suffix != ".csv":
            context = f"(path does not point to a .csv file: {csv_path})"
            raise ValueError(f"{err_msg} {context}")
        dtypes = {"video_id": str,
                  "views": np.int64,
                  "rating": np.float64,
                  "likes": np.int64,
                  "dislikes": np.int64}
        saved = pd.read_csv(csv_path, parse_dates=["timestamp"], dtype=dtypes)
        return cls(saved)

    @classmethod
    def from_sql(cls, *video_ids: str) -> Stats:
        # load stats from sql database
        raise NotImplementedError()

    @property
    def data(self) -> pd.DataFrame:
        return self._data.copy()

    @property
    def most_recent(self) -> dict[str, dict[str, datetime | int | float]]:
        indices = self._data.groupby("video_id")["timestamp"].idxmax()
        subset = self._data.iloc[indices]
        # if you want to drop timestamp, add .drop("timestamp") to above
        return subset.set_index("video_id").T.to_dict()

    def add_row(self,
                video_id: str,
                timestamp: datetime,
                views: int,
                rating: float | None = None,
                likes: int | None = None,
                dislikes: int | None = None) -> None:
        # video_id errors
        err_msg = (f"[{error_trace()}] `video_id` must be an 11-character "
                   f"video id string")
        if not isinstance(video_id, str):
            context = f"(received object of type: {type(video_id)})"
            raise TypeError(f"{err_msg} {context}")
        if not is_video_id(video_id):
            context = f"(received: {repr(video_id)})"
            raise ValueError(f"{err_msg} {context}")

        # timestamp errors
        err_msg = (f"[{error_trace()}] `timestamp` must be a "
                   f"datetime.datetime object")
        if not isinstance(timestamp, datetime):
            context =  f"(received object of type: {type(timestamp)})"
            raise TypeError(f"{err_msg} {context}")
        current_time = datetime.now()
        if timestamp > current_time:
            context = f"(timestamp in the future: {timestamp} > {current_time})"
            raise ValueError(f"{err_msg} {context}")

        # views errors
        err_msg = f"[{error_trace()}] `views` must be an integer > 0"
        if not isinstance(views, int):
            context = f"(received object of type: {type(views)})"
            raise TypeError(f"{err_msg} {context}")
        if views < 0:
            context = f"(received: {views})"
            raise ValueError(f"{err_msg} {context}")

        # rating errors
        if rating is not None:
            err_msg = (f"[{error_trace()}] `rating` must be a numeric "
                       f"between 0 and 5")
            if not isinstance(rating, (int, float)):
                context = f"(received object of type: {type(rating)})"
                raise TypeError(f"{err_msg} {context}")
            if not 0 <= rating <= 5:
                context = f"(received: {rating})"
                raise ValueError(f"{err_msg} {context}")

        # likes + dislikes errors
        for k, v in {"likes": likes, "dislikes": dislikes}.items():
            if v is not None:
                err_msg = f"[{error_trace()}] `{k}` must be an integer > 0"
                if not isinstance(v, int):
                    context = f"(received object of type: {type(v)})"
                    raise TypeError(f"{err_msg} {context}")
                if v < 0:
                    context = f"(received: {v})"
                    raise ValueError(f"{err_msg} {context}")

        # check if row already exists
        if ((self._data["video_id"] == video_id) &
            (self._data["timestamp"] == timestamp)).any():
            err_msg = (f"[{error_trace()}] duplicate row (video_id: "
                       f"{repr(video_id)}, timestamp: {timestamp})")
            raise ValueError(err_msg)

        # add row and sort
        if rating is None and not (likes is None or dislikes is None):
            rating = 5 * likes / (likes + dislikes)
        row_vals = {
            "video_id": video_id,
            "timestamp": timestamp,
            "views": views,
            "rating": rating,
            "likes": likes,
            "dislikes": dislikes
        }
        new_row = [row_vals[col_name] for col_name in self._data.columns]
        old_dtypes = self._data.dtypes.to_dict()  # record old dtypes
        self._data.loc[len(self._data)] = new_row  # add row
        for k, v in old_dtypes.items():
            self._data[k] = self._data[k].astype(v)  # restore old dtype
        self._data = self._data.sort_values(["video_id", "timestamp"])

    def to_csv(self, csv_path: Path, *video_ids: str) -> None:
        # csv_path errors
        err_msg = (f"[{error_trace()}] `csv_path` must be a Path-like "
                   f"object with a .csv file extension")
        if not isinstance(csv_path, Path):
            context = f"(received object of type: {type(csv_path)})"
            raise TypeError(f"{err_msg} {context}")
        if not csv_path.suffix == ".csv":
            context = f"(path does not end with .csv extension: {csv_path})"
            raise ValueError(f"{err_msg} {context}")

        # video_ids errors
        err_msg = (f"[{error_trace()}] video_id must be an 11-character "
                   f"id string")
        for v_id in video_ids:
            if not isinstance(v_id, str):
                context = f"(received object of type: {type(v_id)})"
                raise TypeError(f"{err_msg} {context}")
            if not is_video_id(v_id):
                context = f"(received: {repr(v_id)})"
                raise ValueError(f"{err_msg} {context}")
            if v_id not in self._data["video_id"].values:
                context = f"(id not in data: {repr(v_id)})"
                raise ValueError(f"{err_msg} {context}")

        if len(video_ids) > 0:
            subset = self._data[self._data["video_id"].isin(video_ids)]
            subset.to_csv(csv_path, index=False)
        else:
            self._data.to_csv(csv_path, index=False)

    def to_sql(self) -> None:
        # add new stats in this stats object to sql database
        raise NotImplementedError()

    def __add__(self, other: Stats) -> Stats:
        # merge data from one stats object into another
        raise NotImplementedError()

    def __len__(self) -> int:
        return len(self._data)

    def __str__(self) -> str:
        return str(self._data)
