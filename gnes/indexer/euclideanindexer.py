#  Tencent is pleased to support the open source community by making GNES available.
#
#  Copyright (C) 2019 THL A29 Limited, a Tencent company. All rights reserved.
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

# pylint: disable=low-comment-ratio


from typing import List, Tuple

import numpy as np

from .base import BaseIndexer
from ..helper import batching


class EuclideanIndexer(BaseIndexer):
    def __init__(self, ef=32, *args, **kwargs):
        super().__init__()
        self._num_dim = None
        self._hnsw = None
        self._all_vectors = None
        self._doc_ids = None
        self._ef = ef
        self._count = 0

    @batching(batch_size=2048)
    def add(self, doc_ids: List[int], vectors: np.ndarray, *args, **kwargs):
        import faiss

        if len(vectors) != len(doc_ids):
            raise ValueError("vectors length should be equal to doc_ids")

        if vectors.dtype != np.float32:
            raise ValueError("vectors should be ndarray of float32")

        if self._num_dim is None:
            self._num_dim = vectors.shape[1]
            self._hnsw = faiss.IndexHNSWFlat(self._num_dim, self._ef)
        elif self._num_dim != vectors.shape[1]:
            raise ValueError("vectors dimension is not consistent")

        self._hnsw.add(vectors)

        doc_ids = np.array(doc_ids).astype(np.uint32)
        cur_len = doc_ids.shape[0]
        if self._doc_ids is None:
            self._doc_ids = doc_ids
            self._all_vectors = vectors
            self._count += cur_len
        else:
            if self._doc_ids.shape[0] < self._count + len(doc_ids):
                empty_ids = np.zeros([cur_len * 20], dtype=np.uint32)
                empty_vecs = np.zeros([cur_len * 20, self._num_dim],
                                      dtype=np.float32)
                self._doc_ids = np.concatenate(
                    [self._doc_ids, empty_ids], axis=0)
                self._all_vectors = np.concatenate(
                    [self._all_vectors, empty_vecs], axis=0)

            self._doc_ids[self._count: (self._count + cur_len)] = doc_ids
            self._all_vectors[self._count: (self._count + cur_len)] = vectors
            self._count += len(doc_ids)

    def query(self, keys: np.ndarray, top_k: int, *args, **kwargs) -> List[List[Tuple[int, float]]]:
        if keys.dtype != np.float32:
            raise ValueError("vectors should be ndarray of float32")

        score, ids = self._hnsw.search(keys, top_k)
        ret = []
        for _id, _score in zip(ids, score):
            ret_i = []
            for _id_i, _score_i in zip(_id, _score):
                ret_i.append((int(self._doc_ids[_id_i]), _score_i))
            ret.append(ret_i)

        return ret

    def __getstate__(self):
        d = super().__getstate__()
        del d['_hnsw']
        return d

    def __setstate__(self, d):
        super().__setstate__(d)
        self._count = 0
        self._hnsw = None
        self._num_dim = None
        if self._doc_ids is not None:
            self.add(self._doc_ids, self._all_vectors)
