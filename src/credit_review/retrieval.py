from datetime import date
import numpy as np
import hashlib
import json
from .index_cache import cached_index
from sklearn.feature_extraction.text import TfidfVectorizer
from .models import Source
from .table_access import search_text


class Retriever:
    def __init__(self, sources: list[Source], cutoff: date, embedding_model: str = ""):
        self.sources = {s.id: s for s in sources if s.published_at <= cutoff}
        from .section_context import attach_section_context
        self.sources = attach_section_context(self.sources)
        # Table chunks can omit the statement title (notably connected/separate).
        # Carry the actual page opening as labelled context, without mutating the
        # stored extractor artifact or treating an inferred scope as a fact.
        for sid, source in list(self.sources.items()):
            parent = self.sources.get(source.parent_id)
            if source.kind == 'table' and parent and parent.kind == 'page':
                self.sources[sid] = source.model_copy(update={'metadata':{
                    **source.metadata, 'page_opening':{'source_id':parent.id,'page':parent.page,
                    'text':parent.text[:900], 'excerpt_only':len(parent.text)>900}}})
        self.rows = [s for s in self.sources.values() if s.metadata.get("searchable", True)]
        self.model = None
        self.dense = None
        self.vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 4))
        self.sparse = None
        if self.rows and any(s.text.strip() for s in self.rows):
            texts = [search_text(s) or ' ' for s in self.rows]
            key = hashlib.sha256(json.dumps(texts, ensure_ascii=False).encode()).hexdigest()
            def build():
                vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(2, 4))
                return vectorizer, vectorizer.fit_transform(texts)
            self.vectorizer, self.sparse = cached_index(('lexical-v1', key), build)
        if embedding_model and self.rows:
            from sentence_transformers import SentenceTransformer
            dense_key = hashlib.sha256(json.dumps([search_text(s) for s in self.rows], ensure_ascii=False).encode()).hexdigest()
            def build_dense():
                model = SentenceTransformer(embedding_model, device='cpu')
                return model, model.encode(['passage: ' + search_text(s) for s in self.rows], normalize_embeddings=True)
            self.model, self.dense = cached_index(('dense-v1', embedding_model, dense_key), build_dense)
        self.mode = "hybrid_dense_lexical" if self.model else "lexical_only"

    def search(self, query: str, limit: int = 6) -> list[dict]:
        if self.sparse is None:
            return []
        scores = (self.sparse @ self.vectorizer.transform([query]).T).toarray().ravel()
        ranks = np.zeros(len(self.rows))
        for pos, i in enumerate(np.argsort(-scores)):
            if scores[i] > 0:
                ranks[i] += 1 / (60 + pos + 1)
        if self.model:
            dense_scores = self.dense @ self.model.encode("query: " + query, normalize_embeddings=True)
            for pos, i in enumerate(np.argsort(-dense_scores)):
                ranks[i] += 1 / (60 + pos + 1)
        ordered = [int(i) for i in np.argsort(-ranks) if ranks[i] > 0]
        # Avoid all hits coming from duplicate page/paragraph representations.
        hits, per_page = [], {}
        for i in ordered:
            s = self.rows[i]
            key = (s.document_id, s.page)
            if per_page.get(key, 0) >= 2:
                continue
            per_page[key] = per_page.get(key, 0) + 1
            hits.append({"source": s.model_dump(mode="json"), "score": float(ranks[i]), "mode": self.mode})
            if len(hits) >= limit:
                break
        return hits

    def read(self, ids: list[str]) -> list[dict]:
        chosen = {}
        for sid in ids:
            if sid not in self.sources:
                raise ValueError(f"Unknown or future source: {sid}")
            s = self.sources[sid]
            chosen[s.id] = s
            if s.parent_id in self.sources:
                chosen[s.parent_id] = self.sources[s.parent_id]
        return [s.model_dump(mode="json") for s in chosen.values()]
