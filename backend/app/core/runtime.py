from dataclasses import dataclass

from ..config import Settings
from ..db.session import Database
from ..storage.base import ArtifactStore


@dataclass
class Runtime:
    settings: Settings
    database: Database
    store: ArtifactStore
