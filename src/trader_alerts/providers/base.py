from __future__ import annotations

from abc import ABC, abstractmethod

from ..constants import IndicatorId
from ..models import Observation


class Provider(ABC):
    @abstractmethod
    def fetch(self, indicator_ids: list[IndicatorId]) -> list[Observation]:
        raise NotImplementedError


