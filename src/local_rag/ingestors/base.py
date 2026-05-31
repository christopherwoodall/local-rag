from __future__ import annotations

from abc import ABC, abstractmethod

from ..schemas import IngestResult


class IngestorRegistry:
    def __init__(self):
        self._ingestors: list[BaseIngestor] = []

    def register(self, ingestor: BaseIngestor):
        self._ingestors.append(ingestor)

    def get_ingestor(self, source: str) -> BaseIngestor:
        for ingestor in self._ingestors:
            if ingestor.can_handle(source):
                return ingestor
        raise ValueError(f"No ingestor found for source: {source}")


registry = IngestorRegistry()


class BaseIngestor(ABC):
    source_type: str

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "__abstractmethods__", None):
            registry.register(cls())

    @abstractmethod
    def can_handle(self, source: str) -> bool: ...

    @abstractmethod
    def ingest(self, source: str, tags: list[str], **kwargs) -> IngestResult: ...
