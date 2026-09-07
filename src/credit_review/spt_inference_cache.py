"""Reuse exact structural features and batch the unchanged v0.17 classifier."""
from functools import lru_cache
import json
import numpy as np
from .vendor.spt017 import StructuralBuilder


class BatchedClassifier:
    def __init__(self, model):
        self.model=model
        self.rows={}

    def predict_proba(self, features):
        keys=[tuple(row) for row in features]
        missing=list(dict.fromkeys(key for key in keys if key not in self.rows))
        if missing:
            predictions=self.model.predict_proba(missing)
            self.rows.update((key,row.copy()) for key,row in zip(missing,predictions))
        return np.asarray([self.rows[key] for key in keys])


class CachedStructuralBuilder(StructuralBuilder):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._candidate_cache={}
        # All normalization remains the original implementation. Per-instance
        # caches cannot leak one document's mutable table structures into another.
        original_clean=self._clean
        cached_clean=lru_cache(maxsize=65536)(original_clean)
        self._clean=lambda value:cached_clean(str(value or ''))
        for name in ['_numeric','_value_kind','_value_kind_v015','_content_type']:
            original=getattr(self,name)
            cached=lru_cache(maxsize=65536)(original)
            def normalized(value,_cached=cached):
                return _cached(self._clean(value))
            setattr(self,name,normalized)
        original_region=self._region_stats
        cached_region=lru_cache(maxsize=16384)(original_region)
        self._region_stats=lambda values:list(cached_region(tuple(self._clean(x) for x in values)))

    def _candidate_rows(self,matrix,merges=None,allow_full_header=False):
        key=json.dumps([matrix,merges or []],ensure_ascii=False,separators=(',',':'),sort_keys=True)
        if key not in self._candidate_cache:
            self._candidate_cache[key]=super()._candidate_rows(matrix,merges,allow_full_header=True)
        candidates=self._candidate_cache[key]
        return candidates if allow_full_header else [row for row in candidates if row[0]<len(matrix)]

    def _prepare_boundary_model(self,tables=None):
        bundle,info=super()._prepare_boundary_model(tables)
        classifier=BatchedClassifier(bundle['joint_model'])
        features=[]
        for table in tables or []:
            if table['column_count']>1 and table['row_count']:
                merges=self._restore_merge_spans(table)
                features.extend(row[2] for row in self._candidate_rows(table['matrix'],merges,True))
        if features: classifier.predict_proba(features)
        return {**bundle,'joint_model':classifier},info
