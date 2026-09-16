"""
dataset_analyzer.py

A dataset profiling/analysis module for the "prep" stage of a generalized
AutoML pipeline focused on categorical data.

Two ways to use it:

1. In-memory (small/medium data) — same as before:
    analyzer = DatasetAnalyzer(df, target='label')
    report = analyzer.analyze()
    analyzer.print_report()

2. Chunked / streaming (large data — CSV files, generators, anything that
   doesn't comfortably fit in memory). Peak memory stays bounded regardless
   of row count; only a capped number of distinct values per column is
   tracked.
    analyzer = DatasetAnalyzer(target='label')
    for chunk in pd.read_csv('huge.csv', chunksize=100_000):
        analyzer.update(chunk)
    report = analyzer.analyze()

   or, as a one-liner that also handles CSV paths / DataFrames / chunk
   iterables for you:
    report = analyze_dataset('huge.csv', target='label', chunksize=100_000)

Both paths produce the exact same report shape (a plain dict), so downstream
pipeline stages can consume it the same way either way.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

@dataclass
class AnalyzerConfig:
    # A column is treated as categorical if dtype is object/category/bool/
    # string, OR it's numeric but has <= max_numeric_categories unique values.
    max_numeric_categories: int = 15

    # Cardinality thresholds used for encoding recommendations.
    low_cardinality_max: int = 10          # -> one-hot
    mid_cardinality_max: int = 50          # -> target/frequency encoding
    # above mid_cardinality_max -> hashing / embedding / target encoding

    # A category is "rare" if its frequency share is below this.
    rare_category_threshold: float = 0.01

    # Column is flagged near-constant if the dominant category share exceeds this.
    near_constant_threshold: float = 0.98

    # Column is flagged (near-)unique / ID-like if unique ratio exceeds this.
    id_like_unique_ratio: float = 0.95

    # Missingness thresholds.
    high_missing_threshold: float = 0.40      # -> consider dropping
    moderate_missing_threshold: float = 0.05  # -> impute + missing-indicator

    # Correlation threshold above which two categorical features are flagged
    # as redundant (Cramer's V).
    redundancy_cramers_v: float = 0.85

    # Target-association threshold above which a feature is flagged as a
    # possible leakage risk.
    leakage_cramers_v: float = 0.95

    # --- Streaming / memory-bound settings -------------------------------
    # Max distinct values tracked per categorical column (per-column Counter
    # cap). Columns that exceed this are still profiled, but n_unique is
    # reported as an approximate lower bound (">cap") rather than exact.
    max_tracked_categories: int = 50_000

    # Max distinct (a, b) joint keys tracked per column-pair, used for
    # streaming Cramer's V (redundancy + target association).
    max_pair_keys: int = 5_000

    # Pairwise redundancy checking is O(k^2) in the number of categorical
    # columns. If more pairs than this would need tracking, redundancy
    # checking is skipped in streaming mode (a warning is emitted).
    max_pairs_for_redundancy: int = 300

    # Whether to track exact-duplicate row counts in streaming mode (uses a
    # bounded set of row hashes — O(n_rows) memory, ~small per row).
    track_duplicates: bool = True


# --------------------------------------------------------------------------- #
# Internal accumulators (streaming-safe, bounded memory)
# --------------------------------------------------------------------------- #

class _DistinctTracker:
    """Counter of distinct values with a hard cap on how many it will track."""

    __slots__ = ("counts", "cap", "capped")

    def __init__(self, cap: int):
        self.counts: Counter = Counter()
        self.cap = cap
        self.capped = False

    def add_value_counts(self, vc: pd.Series) -> None:
        if self.capped:
            return
        for k, v in vc.items():
            self.counts[k] += int(v)
        if len(self.counts) > self.cap:
            self.capped = True

    @property
    def n_unique(self) -> Optional[int]:
        return None if self.capped else len(self.counts)


class _CatColumnAcc:
    """Accumulator for a categorical (object/category/bool/string) column."""

    def __init__(self, cap: int):
        self.count = 0
        self.missing = 0
        self.tracker = _DistinctTracker(cap)

    def add(self, s: pd.Series) -> None:
        self.missing += int(s.isna().sum())
        valid = s.dropna()
        self.count += len(valid)
        if len(valid):
            try:
                vc = valid.value_counts()
            except TypeError:
                # Unhashable entries (e.g. lists stored in an object column)
                vc = valid.astype(str).value_counts()
            self.tracker.add_value_counts(vc)


class _NumColumnAcc:
    """
    Accumulator for a numeric column. Tracks enough to decide, at finalize
    time, whether it should really be treated as categorical (low
    cardinality) -- reproducing the exact same rule as the in-memory path:
    `nunique <= max_numeric_categories` -> categorical.
    """

    def __init__(self, small_cap: int, big_cap: int):
        self.count = 0
        self.missing = 0
        self.sum = 0.0
        self.sumsq = 0.0
        self.min = math.inf
        self.max = -math.inf
        # small_cap == max_numeric_categories: as soon as we see more
        # distinct values than this, the column is definitively numeric.
        self.small_tracker = _DistinctTracker(small_cap)
        self.big_tracker: Optional[_DistinctTracker] = None
        self.big_cap = big_cap

    def add(self, s: pd.Series) -> None:
        self.missing += int(s.isna().sum())
        valid = s.dropna()
        n = len(valid)
        self.count += n
        if n == 0:
            return
        arr = valid.to_numpy(dtype=float)
        self.sum += float(arr.sum())
        self.sumsq += float((arr * arr).sum())
        mn, mx = float(arr.min()), float(arr.max())
        self.min = min(self.min, mn)
        self.max = max(self.max, mx)

        if not self.small_tracker.capped:
            vc = valid.value_counts()
            self.small_tracker.add_value_counts(vc)
            if self.small_tracker.capped:
                # Just crossed the categorical threshold -> definitely
                # numeric. Switch to a cheap approx-unique tracker (keys
                # only, no frequencies needed) for reporting purposes.
                self.big_tracker = _DistinctTracker(self.big_cap)
                for k in self.small_tracker.counts.keys():
                    self.big_tracker.counts[k] = 1
        elif self.big_tracker is not None and not self.big_tracker.capped:
            for v in pd.unique(valid):
                if v not in self.big_tracker.counts:
                    self.big_tracker.counts[v] = 1
                    if len(self.big_tracker.counts) > self.big_tracker.cap:
                        self.big_tracker.capped = True
                        break

    @property
    def is_categorical(self) -> bool:
        return not self.small_tracker.capped

    @property
    def approx_n_unique(self) -> Optional[int]:
        if self.big_tracker is None:
            return None
        return None if self.big_tracker.capped else len(self.big_tracker.counts)


class _PairCatAcc:
    """Joint-count accumulator for a pair of categorical columns (redundancy
    or categorical-vs-categorical target association)."""

    def __init__(self, cap: int):
        self.joint: Counter = Counter()
        self.cap = cap
        self.capped = False

    def add(self, a: pd.Series, b: pd.Series) -> None:
        if self.capped:
            return
        both = pd.DataFrame({"a": a, "b": b}).dropna()
        if both.empty:
            return
        vc = both.groupby(["a", "b"], observed=True).size()
        for (av, bv), cnt in vc.items():
            self.joint[(av, bv)] += int(cnt)
        if len(self.joint) > self.cap:
            self.capped = True

    def cramers_v(self) -> Optional[float]:
        if self.capped or not self.joint:
            return None
        rows = sorted({k[0] for k in self.joint})
        cols = sorted({k[1] for k in self.joint})
        r_idx = {v: i for i, v in enumerate(rows)}
        c_idx = {v: i for i, v in enumerate(cols)}
        table = np.zeros((len(rows), len(cols)), dtype=float)
        for (av, bv), cnt in self.joint.items():
            table[r_idx[av], c_idx[bv]] += cnt
        return _cramers_v_from_table(table)


class _CatNumAcc:
    """Accumulator for categorical-feature vs numeric-target (or vice versa)
    association, used to compute the correlation ratio (eta)."""

    def __init__(self, cap: int):
        self.groups: Dict[Any, List[float]] = {}  # category -> [count, sum, sumsq]
        self.grand_n = 0
        self.grand_sum = 0.0
        self.grand_sumsq = 0.0
        self.cap = cap
        self.capped = False

    def add(self, cats: pd.Series, vals: pd.Series) -> None:
        both = pd.DataFrame({"cat": cats, "val": vals}).dropna()
        if both.empty:
            return
        arr = both["val"].to_numpy(dtype=float)
        self.grand_n += len(arr)
        self.grand_sum += float(arr.sum())
        self.grand_sumsq += float((arr * arr).sum())
        if self.capped:
            return
        g = both.groupby("cat", observed=True)["val"].agg(["count", "sum"])
        sumsq = both.groupby("cat", observed=True)["val"].apply(lambda x: float((x ** 2).sum()))
        for cat in g.index:
            c, s = float(g.loc[cat, "count"]), float(g.loc[cat, "sum"])
            sq = float(sumsq.loc[cat])
            if cat not in self.groups and len(self.groups) >= self.cap:
                self.capped = True
                continue
            prev = self.groups.get(cat, [0.0, 0.0, 0.0])
            self.groups[cat] = [prev[0] + c, prev[1] + s, prev[2] + sq]

    def correlation_ratio(self) -> Optional[float]:
        if self.capped or self.grand_n < 2:
            return None
        ss_total = self.grand_sumsq - (self.grand_sum ** 2) / self.grand_n
        if ss_total <= 0:
            return 0.0
        ss_between = sum((s ** 2) / c for c, s, _ in self.groups.values() if c > 0)
        ss_between -= (self.grand_sum ** 2) / self.grand_n
        return float(math.sqrt(max(0.0, ss_between) / ss_total))


class _NumNumAcc:
    """Accumulator for numeric-feature vs numeric-target Pearson correlation."""

    def __init__(self):
        self.n = 0
        self.sx = self.sy = self.sxy = self.sx2 = self.sy2 = 0.0

    def add(self, x: pd.Series, y: pd.Series) -> None:
        both = pd.DataFrame({"x": x, "y": y}).dropna()
        if both.empty:
            return
        xa = both["x"].to_numpy(dtype=float)
        ya = both["y"].to_numpy(dtype=float)
        self.n += len(xa)
        self.sx += float(xa.sum())
        self.sy += float(ya.sum())
        self.sxy += float((xa * ya).sum())
        self.sx2 += float((xa * xa).sum())
        self.sy2 += float((ya * ya).sum())

    def pearson(self) -> Optional[float]:
        if self.n < 2:
            return None
        cov = self.sxy / self.n - (self.sx / self.n) * (self.sy / self.n)
        varx = self.sx2 / self.n - (self.sx / self.n) ** 2
        vary = self.sy2 / self.n - (self.sy / self.n) ** 2
        denom = math.sqrt(max(varx, 0.0) * max(vary, 0.0))
        if denom == 0:
            return 0.0
        return float(cov / denom)


# --------------------------------------------------------------------------- #
# Standalone stats helpers
# --------------------------------------------------------------------------- #

def _chi2_stat(observed: np.ndarray) -> float:
    """Chi-square statistic, no scipy dependency."""
    observed = observed.astype(float)
    row_sums = observed.sum(axis=1, keepdims=True)
    col_sums = observed.sum(axis=0, keepdims=True)
    total = observed.sum()
    if total == 0:
        return 0.0
    expected = row_sums @ col_sums / total
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = np.where(expected > 0, (observed - expected) ** 2 / expected, 0.0)
    return float(terms.sum())


def _cramers_v_from_table(table: np.ndarray) -> float:
    if table.size == 0 or table.shape[0] < 2 or table.shape[1] < 2:
        return 0.0
    chi2 = _chi2_stat(table)
    n = table.sum()
    if n <= 1:
        return 0.0
    phi2 = chi2 / n
    r, k = table.shape
    phi2_corr = max(0.0, phi2 - ((k - 1) * (r - 1)) / (n - 1))
    r_corr = r - ((r - 1) ** 2) / (n - 1)
    k_corr = k - ((k - 1) ** 2) / (n - 1)
    denom = min(k_corr - 1, r_corr - 1)
    if denom <= 0:
        return 0.0
    return float(math.sqrt(phi2_corr / denom))


_NAN_SENTINEL = object()


def _canon(v: Any) -> Any:
    """Canonicalize a scalar for hashing. Needed because Python (3.10+)
    hashes float NaN by object identity, not value -- two NaN cells with the
    same 'missing' meaning would otherwise hash differently and break
    duplicate-row detection. Replace any float NaN with a single shared
    sentinel so equal rows always hash equal."""
    if isinstance(v, float) and v != v:
        return _NAN_SENTINEL
    return v


def _infer_dtype_kind(s: pd.Series) -> str:
    """dtype-only classification, doesn't need the data volume to decide."""
    if pd.api.types.is_bool_dtype(s):
        return "categorical"
    if isinstance(s.dtype, pd.CategoricalDtype):
        return "categorical"
    if pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s):
        return "categorical"
    if pd.api.types.is_numeric_dtype(s):
        return "numeric_tentative"   # may flip to categorical if low-cardinality
    if pd.api.types.is_datetime64_any_dtype(s):
        return "datetime"
    return "other"


# --------------------------------------------------------------------------- #
# Main analyzer
# --------------------------------------------------------------------------- #

ChunkSource = Union[pd.DataFrame, str, Iterable[pd.DataFrame]]


class DatasetAnalyzer:
    def __init__(
        self,
        df: Optional[pd.DataFrame] = None,
        target: Optional[str] = None,
        config: Optional[AnalyzerConfig] = None,
    ):
        """
        `df` is optional. Pass it for the simple in-memory one-shot usage
        (`DatasetAnalyzer(df, target=...).analyze()`); omit it and call
        `.update(chunk)` repeatedly for streaming usage.
        """
        self.target = target
        self.cfg = config or AnalyzerConfig()

        self._n_rows = 0
        self._columns: List[str] = []
        self._dtype_str: Dict[str, str] = {}
        self._dtype_kind: Dict[str, str] = {}
        self._col_acc: Dict[str, Union[_CatColumnAcc, _NumColumnAcc]] = {}

        self._redundancy_enabled = True
        self._target_kind_for_pairing: Optional[str] = None
        self._pair_acc: Dict[Tuple[str, str], _PairCatAcc] = {}
        self._target_cat_acc: Dict[str, _PairCatAcc] = {}
        self._target_catnum_acc: Dict[str, _CatNumAcc] = {}
        self._target_numnum_acc: Dict[str, _NumNumAcc] = {}

        self._dup_hashes: set = set()
        self._n_duplicates = 0
        self._dup_tracking_ok = True

        self._report: Dict[str, Any] = {}
        self._warnings_from_streaming: List[str] = []

        if df is not None:
            self.update(df)

    # ------------------------------------------------------------------ #
    # Streaming ingestion
    # ------------------------------------------------------------------ #

    def update(self, chunk: pd.DataFrame) -> "DatasetAnalyzer":
        """Feed one chunk (or a whole DataFrame) of rows into the analyzer.
        Can be called any number of times; memory stays bounded by config
        caps regardless of how many rows are fed in total."""
        if not isinstance(chunk, pd.DataFrame):
            raise TypeError("chunk must be a pandas DataFrame")
        if chunk.empty:
            return self

        if not self._columns:
            self._init_from_first_chunk(chunk)
        else:
            missing_cols = set(self._columns) - set(chunk.columns)
            if missing_cols:
                raise ValueError(f"chunk is missing columns seen in a previous chunk: {missing_cols}")

        self._n_rows += len(chunk)

        for col in self._columns:
            s = chunk[col]
            kind = self._dtype_kind[col]
            if kind in ("categorical", "numeric_tentative"):
                self._col_acc[col].add(s)

        hard_cat_cols = [c for c in self._columns if self._dtype_kind[c] == "categorical" and c != self.target]
        for a, b in self._pair_acc:
            self._pair_acc[(a, b)].add(chunk[a], chunk[b])

        if self.target is not None and self.target in self._columns:
            t = chunk[self.target]
            target_kind = self._target_kind_for_pairing
            for col in hard_cat_cols:
                if target_kind == "categorical":
                    self._target_cat_acc[col].add(chunk[col], t)
                else:
                    self._target_catnum_acc[col].add(chunk[col], t)
            for col in self._columns:
                if col == self.target or self._dtype_kind[col] != "numeric_tentative":
                    continue
                if target_kind == "categorical":
                    self._target_catnum_acc[col].add(t, chunk[col])
                else:
                    self._target_numnum_acc[col].add(chunk[col], t)

        if self.cfg.track_duplicates and self._dup_tracking_ok:
            try:
                for row in chunk.itertuples(index=False, name=None):
                    h = hash(tuple(_canon(v) for v in row))
                    if h in self._dup_hashes:
                        self._n_duplicates += 1
                    else:
                        self._dup_hashes.add(h)
            except TypeError:
                self._dup_tracking_ok = False
                self._warnings_from_streaming.append(
                    "Duplicate-row tracking disabled: row contains unhashable values."
                )

        return self

    def _init_from_first_chunk(self, chunk: pd.DataFrame) -> None:
        cfg = self.cfg
        self._columns = list(chunk.columns)
        for col in self._columns:
            s = chunk[col]
            self._dtype_str[col] = str(s.dtype)
            kind = _infer_dtype_kind(s)
            self._dtype_kind[col] = kind
            if kind == "categorical":
                self._col_acc[col] = _CatColumnAcc(cfg.max_tracked_categories)
            elif kind == "numeric_tentative":
                self._col_acc[col] = _NumColumnAcc(cfg.max_numeric_categories, cfg.max_tracked_categories)

        hard_cat_cols = [c for c in self._columns if self._dtype_kind[c] == "categorical" and c != self.target]

        n_possible_pairs = len(hard_cat_cols) * (len(hard_cat_cols) - 1) // 2
        if n_possible_pairs > cfg.max_pairs_for_redundancy:
            self._redundancy_enabled = False
            self._warnings_from_streaming.append(
                f"Pairwise redundancy check skipped: {n_possible_pairs} categorical pairs "
                f"exceeds max_pairs_for_redundancy={cfg.max_pairs_for_redundancy}."
            )
        else:
            for a, b in combinations(hard_cat_cols, 2):
                self._pair_acc[(a, b)] = _PairCatAcc(cfg.max_pair_keys)

        if self.target is not None and self.target in self._columns:
            t_dtype_kind = self._dtype_kind[self.target]
            if t_dtype_kind == "categorical":
                target_kind = "categorical"
            elif t_dtype_kind == "numeric_tentative":
                # Whether a numeric-dtype target is really continuous or a
                # low-cardinality category can only be known for sure once
                # all data is seen -- but the accumulator type has to be
                # fixed up front. Use the first chunk's cardinality as a
                # representative heuristic (same rule as the general
                # numeric-vs-categorical decision, just applied early).
                target_kind = (
                    "categorical"
                    if chunk[self.target].nunique(dropna=True) <= cfg.max_numeric_categories
                    else "numeric"
                )
            else:
                target_kind = "numeric"  # datetime/other: not paired for association
            self._target_kind_for_pairing = target_kind

            for col in hard_cat_cols:
                if target_kind == "categorical":
                    self._target_cat_acc[col] = _PairCatAcc(cfg.max_pair_keys)
                else:
                    self._target_catnum_acc[col] = _CatNumAcc(cfg.max_tracked_categories)
            for col in self._columns:
                if col == self.target or self._dtype_kind[col] != "numeric_tentative":
                    continue
                if target_kind == "categorical":
                    self._target_catnum_acc[col] = _CatNumAcc(cfg.max_tracked_categories)
                else:
                    self._target_numnum_acc[col] = _NumNumAcc()
        else:
            self._target_kind_for_pairing = None

    # ------------------------------------------------------------------ #
    # Bulk / convenience ingestion
    # ------------------------------------------------------------------ #

    @classmethod
    def from_source(
        cls,
        source: ChunkSource,
        target: Optional[str] = None,
        config: Optional[AnalyzerConfig] = None,
        chunksize: int = 50_000,
    ) -> "DatasetAnalyzer":
        """
        Build an analyzer from:
          - a pandas DataFrame (iterated internally in `chunksize` slices)
          - a path to a CSV file (streamed via pandas.read_csv(chunksize=...))
          - a path to a Parquet file (streamed via pyarrow row-group batches
            if pyarrow is available, else loaded and chunked)
          - any iterable of DataFrame chunks (e.g. your own loader/generator)
        """
        analyzer = cls(target=target, config=config)

        if isinstance(source, pd.DataFrame):
            for start in range(0, len(source), chunksize):
                analyzer.update(source.iloc[start:start + chunksize])
            return analyzer

        if isinstance(source, str):
            lower = source.lower()
            if lower.endswith(".csv") or lower.endswith(".csv.gz"):
                for chunk in pd.read_csv(source, chunksize=chunksize):
                    analyzer.update(chunk)
                return analyzer
            if lower.endswith(".parquet"):
                try:
                    import pyarrow.parquet as pq
                    pf = pq.ParquetFile(source)
                    for batch in pf.iter_batches(batch_size=chunksize):
                        analyzer.update(batch.to_pandas())
                except ImportError:
                    df = pd.read_parquet(source)
                    for start in range(0, len(df), chunksize):
                        analyzer.update(df.iloc[start:start + chunksize])
                return analyzer
            raise ValueError(f"Unrecognized file extension for streaming: {source}")

        # Assume an iterable of DataFrame chunks
        for chunk in source:
            analyzer.update(chunk)
        return analyzer

    # ------------------------------------------------------------------ #
    # Finalize / report
    # ------------------------------------------------------------------ #

    def analyze(self) -> Dict[str, Any]:
        cfg = self.cfg
        n = self._n_rows

        columns: Dict[str, Dict[str, Any]] = {}
        for col in self._columns:
            kind = self._dtype_kind[col]
            if kind == "categorical":
                acc: _CatColumnAcc = self._col_acc[col]  # type: ignore
                inferred = "categorical"
                n_unique = acc.tracker.n_unique
                missing = acc.missing
                cardinality_capped = acc.tracker.capped
                top_share, rare_sample, n_rare = self._categorical_stats(acc.tracker, acc.count, cfg)
            elif kind == "numeric_tentative":
                nacc: _NumColumnAcc = self._col_acc[col]  # type: ignore
                missing = nacc.missing
                if nacc.is_categorical:
                    inferred = "categorical"
                    n_unique = nacc.small_tracker.n_unique
                    cardinality_capped = False
                    top_share, rare_sample, n_rare = self._categorical_stats(nacc.small_tracker, nacc.count, cfg)
                else:
                    inferred = "numeric"
                    n_unique = nacc.approx_n_unique
                    cardinality_capped = nacc.big_tracker.capped if nacc.big_tracker else False
                    top_share, rare_sample, n_rare = 0.0, [], 0
            else:
                inferred = kind
                n_unique = None
                missing = 0
                cardinality_capped = False
                top_share, rare_sample, n_rare = 0.0, [], 0

            missing_pct = missing / n if n else 0.0
            unique_ratio = (n_unique / n) if (n_unique is not None and n) else None

            flags: List[str] = []
            if missing_pct >= cfg.high_missing_threshold:
                flags.append("high_missing")
            elif missing_pct >= cfg.moderate_missing_threshold:
                flags.append("moderate_missing")
            if inferred == "categorical" and top_share >= cfg.near_constant_threshold:
                flags.append("near_constant")
            if (
                unique_ratio is not None
                and unique_ratio >= cfg.id_like_unique_ratio
                and (n_unique or 0) > cfg.mid_cardinality_max
            ):
                flags.append("id_like")
            if inferred == "categorical" and n_rare:
                flags.append(f"{n_rare}_rare_categories")
            if cardinality_capped:
                flags.append("cardinality_capped")
            if col == self.target:
                flags.append("target")

            columns[col] = {
                "dtype": self._dtype_str[col],
                "inferred_type": inferred,
                "n_unique": n_unique if n_unique is not None else f">{cfg.max_tracked_categories}",
                "unique_ratio": unique_ratio,
                "missing_count": missing,
                "missing_pct": missing_pct,
                "top_category_share": top_share,
                "n_rare_categories": n_rare,
                "rare_categories_sample": rare_sample,
                "flags": flags,
            }

        cat_cols = [c for c, p in columns.items() if p["inferred_type"] == "categorical"]
        num_cols = [c for c, p in columns.items() if p["inferred_type"] == "numeric"]

        redundant_pairs: List[Tuple[str, str, float]] = []
        for (a, b), pacc in self._pair_acc.items():
            v = pacc.cramers_v()
            if v is not None and v >= cfg.redundancy_cramers_v:
                redundant_pairs.append((a, b, v))

        target_assoc: Dict[str, Dict[str, Any]] = {}
        for col, pacc in self._target_cat_acc.items():
            v = pacc.cramers_v()
            if v is None:
                continue
            target_assoc[col] = {"method": "cramers_v", "score": v, "leakage_risk": v >= cfg.leakage_cramers_v}
        for col, cnacc in self._target_catnum_acc.items():
            r = cnacc.correlation_ratio()
            if r is None:
                continue
            target_assoc[col] = {"method": "correlation_ratio", "score": r, "leakage_risk": r >= cfg.leakage_cramers_v}
        for col, nnacc in self._target_numnum_acc.items():
            p = nnacc.pearson()
            if p is None:
                continue
            score = abs(p)
            target_assoc[col] = {"method": "pearson", "score": score, "leakage_risk": score >= cfg.leakage_cramers_v}

        recommendations = self._build_recommendations(columns, redundant_pairs, target_assoc, cfg)

        overview = {
            "n_rows": n,
            "n_cols": len(self._columns),
            "n_duplicate_rows": self._n_duplicates if self._dup_tracking_ok else None,
        }

        all_warnings = list(self._warnings_from_streaming)
        all_warnings.extend(recommendations["warnings"])
        recommendations["warnings"] = all_warnings

        self._report = {
            "overview": overview,
            "columns": columns,
            "categorical_columns": cat_cols,
            "numeric_columns": num_cols,
            "redundant_pairs": redundant_pairs,
            "target_association": target_assoc,
            "recommendations": recommendations,
        }
        return self._report

    @staticmethod
    def _categorical_stats(
        tracker: _DistinctTracker, count: int, cfg: AnalyzerConfig
    ) -> Tuple[float, List[Any], int]:
        if count == 0 or not tracker.counts:
            return 0.0, [], 0
        total_tracked = sum(tracker.counts.values())
        top_count = max(tracker.counts.values())
        top_share = top_count / count if count else 0.0
        rare = [k for k, v in tracker.counts.items() if (v / count) < cfg.rare_category_threshold]
        return top_share, rare[:10], len(rare)

    # ------------------------------------------------------------------ #
    # Recommendations (same logic as before, operates on the finalized
    # column-profile dict so it's identical for both in-memory & streaming)
    # ------------------------------------------------------------------ #

    def _build_recommendations(
        self,
        profiles: Dict[str, Dict[str, Any]],
        redundant_pairs: List[Tuple[str, str, float]],
        target_assoc: Dict[str, Dict[str, Any]],
        cfg: AnalyzerConfig,
    ) -> Dict[str, Any]:
        drop_columns: Dict[str, str] = {}
        encoding_strategy: Dict[str, str] = {}
        imputation_strategy: Dict[str, str] = {}
        warnings_list: List[str] = []

        for col, p in profiles.items():
            if col == self.target:
                continue

            if "id_like" in p["flags"]:
                drop_columns[col] = "near-unique / ID-like column, no generalizable signal"
                continue
            if "high_missing" in p["flags"]:
                drop_columns[col] = f"{p['missing_pct']*100:.0f}% missing values"
                continue
            if "near_constant" in p["flags"]:
                drop_columns[col] = f"dominant category covers {p['top_category_share']*100:.0f}% of rows"
                continue

            if p["inferred_type"] == "categorical":
                k = p["n_unique"]
                k_num = k if isinstance(k, int) else cfg.mid_cardinality_max + 1  # capped -> treat as high-card
                if k_num <= cfg.low_cardinality_max:
                    strat = "one-hot encoding"
                elif k_num <= cfg.mid_cardinality_max:
                    strat = "target/frequency encoding (with CV to avoid leakage)"
                else:
                    strat = "hashing trick / embedding / target encoding (high cardinality)"
                if p["n_rare_categories"] > 0:
                    strat += f"; bucket rare categories (<{cfg.rare_category_threshold*100:.0f}% freq) into 'OTHER' first"
                if "cardinality_capped" in p["flags"]:
                    strat += f" [exact cardinality exceeded tracking cap of {cfg.max_tracked_categories}]"
                encoding_strategy[col] = strat

            if "moderate_missing" in p["flags"]:
                if p["inferred_type"] == "categorical":
                    imputation_strategy[col] = "impute with mode or dedicated 'MISSING' category + add missing-indicator"
                else:
                    imputation_strategy[col] = "impute with median + add missing-indicator"

        for a, b, v in redundant_pairs:
            warnings_list.append(
                f"'{a}' and '{b}' are highly redundant (Cramer's V={v:.2f}); consider dropping one"
            )

        for col, info in target_assoc.items():
            if info.get("leakage_risk"):
                warnings_list.append(
                    f"'{col}' is almost perfectly associated with the target "
                    f"({info['method']}={info['score']:.2f}) - check for target leakage"
                )

        return {
            "drop_columns": drop_columns,
            "encoding_strategy": encoding_strategy,
            "imputation_strategy": imputation_strategy,
            "warnings": warnings_list,
        }

    # ------------------------------------------------------------------ #
    # Reporting
    # ------------------------------------------------------------------ #

    def print_report(self) -> None:
        if not self._report:
            self.analyze()
        r = self._report
        o = r["overview"]

        print("=" * 70)
        print("DATASET OVERVIEW")
        print("=" * 70)
        dup_str = f"{o['n_duplicate_rows']:,}" if o["n_duplicate_rows"] is not None else "not tracked"
        print(f"Rows: {o['n_rows']:,}   Columns: {o['n_cols']}   Duplicate rows: {dup_str}")
        print(f"Categorical columns: {len(r['categorical_columns'])}   "
              f"Numeric columns: {len(r['numeric_columns'])}")

        print("\n" + "=" * 70)
        print("COLUMN PROFILES")
        print("=" * 70)
        header = f"{'column':25s} {'type':11s} {'nunique':10s} {'missing%':9s} {'top_share%':10s} flags"
        print(header)
        print("-" * len(header))
        for col, p in r["columns"].items():
            flags = ",".join(p["flags"]) if p["flags"] else "-"
            nunique_str = str(p["n_unique"])
            print(f"{col[:25]:25s} {p['inferred_type']:11s} {nunique_str:<10s} "
                  f"{p['missing_pct']*100:8.1f}% {p['top_category_share']*100:9.1f}% {flags}")

        if r["redundant_pairs"]:
            print("\n" + "=" * 70)
            print("REDUNDANT CATEGORICAL PAIRS (Cramer's V above threshold)")
            print("=" * 70)
            for a, b, v in r["redundant_pairs"]:
                print(f"  {a}  <->  {b}   V={v:.3f}")

        if r["target_association"]:
            print("\n" + "=" * 70)
            print(f"ASSOCIATION WITH TARGET '{self.target}'")
            print("=" * 70)
            ranked = sorted(r["target_association"].items(), key=lambda kv: kv[1]["score"], reverse=True)
            for col, info in ranked:
                warn = "  <-- possible leakage" if info.get("leakage_risk") else ""
                print(f"  {col:25s} {info['method']:14s} score={info['score']:.3f}{warn}")

        print("\n" + "=" * 70)
        print("RECOMMENDATIONS")
        print("=" * 70)
        rec = r["recommendations"]
        if rec["drop_columns"]:
            print("Drop columns:")
            for c, why in rec["drop_columns"].items():
                print(f"  - {c}: {why}")
        print("\nEncoding strategy:")
        for c, strat in rec["encoding_strategy"].items():
            print(f"  - {c}: {strat}")
        if rec["imputation_strategy"]:
            print("\nImputation:")
            for c, strat in rec["imputation_strategy"].items():
                print(f"  - {c}: {strat}")
        if rec["warnings"]:
            print("\nWarnings:")
            for w in rec["warnings"]:
                print(f"  ! {w}")


# --------------------------------------------------------------------------- #
# Convenience function
# --------------------------------------------------------------------------- #

def analyze_dataset(
    source: ChunkSource,
    target: Optional[str] = None,
    config: Optional[AnalyzerConfig] = None,
    chunksize: int = 50_000,
) -> Dict[str, Any]:
    """One-shot wrapper: build analyzer from `source` (DataFrame, CSV/Parquet
    path, or iterable of chunks), analyze, print, and return the report dict."""
    analyzer = DatasetAnalyzer.from_source(source, target=target, config=config, chunksize=chunksize)
    report = analyzer.analyze()
    analyzer.print_report()
    return report


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    n = 5000
    demo = pd.DataFrame({
        "user_id": [f"u{i}" for i in range(n)],
        "country": rng.choice(["US", "IN", "UK", "DE", "FR"], n, p=[.4, .3, .1, .1, .1]),
        "device": rng.choice(["mobile", "desktop", "tablet"], n),
        "plan": rng.choice(["free", "pro", "enterprise"], n, p=[.85, .1, .05]),
        "signup_channel": rng.choice([f"ch{i}" for i in range(80)], n),
        "is_active": rng.choice([0, 1], n, p=[.98, .02]),
        "age": rng.integers(18, 70, n).astype(float),
        "rating_1to5": rng.integers(1, 6, n),          # low-cardinality numeric -> categorical
    })
    demo.loc[demo.sample(frac=0.08, random_state=1).index, "device"] = np.nan
    demo.loc[demo.sample(frac=0.5, random_state=2).index, "age"] = np.nan
    demo["converted"] = (demo["plan"] != "free").astype(int)
    # duplicate a few rows to exercise duplicate tracking
    demo = pd.concat([demo, demo.iloc[:15]], ignore_index=True)

    print("### ONE-SHOT (in-memory) ###\n")
    report_oneshot = analyze_dataset(demo, target="converted")

    print("\n\n### STREAMING (chunksize=777, same data) ###\n")

    def chunk_iter():
        for start in range(0, len(demo), 777):
            yield demo.iloc[start:start + 777]

    report_stream = analyze_dataset(chunk_iter(), target="converted")

    # sanity check: both paths should agree closely
    assert report_oneshot["overview"]["n_rows"] == report_stream["overview"]["n_rows"]
    assert report_oneshot["overview"]["n_duplicate_rows"] == report_stream["overview"]["n_duplicate_rows"]
    print("\n\nSanity check passed: streaming and in-memory reports agree on row/duplicate counts.")