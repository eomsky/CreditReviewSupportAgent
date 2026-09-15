"""Application retrieval default: persistent vectors plus original lexical search."""
import threading


class DefaultEvidenceStore:
    def __init__(self, original, index_path, factory=None):
        self.original = original
        self.index_path = index_path
        self._factory = factory
        self._retriever = None
        self._lock = threading.RLock()

    def __getattr__(self, name):
        # Registration, manifests and source access remain in the document store.
        return getattr(self.original, name)

    def select(self, terms, manifest, budget=16000, limit=24):
        with self._lock:
            if self._retriever is None:
                factory = self._factory
                if factory is None:
                    from runtime_vector_store import RuntimePageStore
                    factory = RuntimePageStore
                # Do not silently replace the requested vector path with keyword-only search.
                self._retriever = factory(self.original, self.index_path)
            return self._retriever.select(terms, manifest, budget=budget, limit=limit)

    def close(self):
        with self._lock:
            if self._retriever is not None:
                self._retriever.vector.client.close()
                self._retriever = None
