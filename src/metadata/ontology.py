"""L3 · Metadata & Ontology

Entidades y relaciones para el catálogo de conocimiento gobernado.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List

from .schema import (
    AuthorityLevel,
    ClassificationTag,
    KnowledgeAsset,
    KnowledgeChunk,
    Revision,
    Source,
    ValidityStatus,
)


class RelationType(Enum):
    """Tipos de relaciones ontológicas"""
    DERIVED_FROM = "DERIVED_FROM"      # Chunk derivado de documento
    SUPERSEDES = "SUPERSEDES"          # Versión nueva reemplaza anterior
    REFERENCES = "REFERENCES"          # Cita o referencia cruzada
    VALIDATES = "VALIDATES"            # Evidencia valida claim
    CONTRADICTS = "CONTRADICTS"        # Claim contradice otro
    GENERATED_BY = "GENERATED_BY"      # Asset generado por agente/proceso
    AUTHORIZES = "AUTHORIZES"          # Permiso autoriza ejecución
    GENERATES = "GENERATES"            # Ejecución genera evidencia
    SERVES = "SERVES"                  # Proveedor sirve modelo
    REQUIRES = "REQUIRES"              # Componente requiere permiso
    BELONGS_TO = "BELONGS_TO"          # Chunk pertenece a documento
    IMPLEMENTS = "IMPLEMENTS"          # Código implementa contrato
    CONFLICTS_WITH = "CONFLICTS_WITH"  # Conflicto con canonical state


@dataclass
class OntologyRelation:
    """Relación entre entidades ontológicas"""
    relation_id: str
    relation_type: RelationType
    source_id: str  # ID de entidad origen
    target_id: str  # ID de entidad destino
    confidence: float = 1.0  # 0-1, para relaciones inferidas
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict = field(default_factory=dict)


@dataclass
class KnowledgeGraph:
    """Grafo de conocimiento con relaciones ontológicas"""
    assets: dict = field(default_factory=dict)  # asset_id -> KnowledgeAsset
    chunks: dict = field(default_factory=dict)  # chunk_id -> KnowledgeChunk
    relations: List[OntologyRelation] = field(default_factory=list)
    sources: dict = field(default_factory=dict)  # source_id -> Source

    def add_asset(self, asset: KnowledgeAsset):
        """Añadir asset al grafo"""
        self.assets[asset.asset_id] = asset

    def add_chunk(self, chunk: KnowledgeChunk):
        """Añadir chunk al grafo"""
        self.chunks[chunk.chunk_id] = chunk

    def add_relation(self, relation: OntologyRelation):
        """Añadir relación al grafo"""
        self.relations.append(relation)

    def get_lineage(self, asset_id: str) -> List[str]:
        """Obtener lineage completo de un asset (relaciones DERIVED_FROM)"""
        lineage = []
        visited = set()
        current_id = asset_id

        while current_id:
            # DERIVED_FROM se expresa como derived asset -> source asset.
            # Conservamos el nodo repetido para que validate_integrity pueda
            # detectar ciclos sin dejar el recorrido en un bucle infinito.
            if current_id in visited:
                lineage.append(current_id)
                break

            visited.add(current_id)
            lineage.append(current_id)
            # Buscar la fuente de la que este asset se deriva.
            derived = next(
                (
                    r
                    for r in self.relations
                    if r.source_id == current_id
                    and r.relation_type == RelationType.DERIVED_FROM
                ),
                None,
            )
            current_id = derived.target_id if derived else None

        return lineage

    def get_superseded_chain(self, asset_id: str) -> List[str]:
        """Obtener cadena de versiones superseded"""
        chain = [asset_id]
        current = self.assets.get(asset_id)

        while current and current.superseded_by:
            chain.append(current.superseded_by)
            current = self.assets.get(current.superseded_by)

        return chain

    def filter_by_authority(self, authority: AuthorityLevel) -> List[KnowledgeAsset]:
        """Filtrar assets por nivel de autoridad"""
        return [a for a in self.assets.values() if a.authority == authority]

    def filter_by_classification(self, tag: ClassificationTag) -> List[KnowledgeAsset]:
        """Filtrar assets por tag de clasificación"""
        return [a for a in self.assets.values() if tag in a.classification]

    def validate_integrity(self) -> List[str]:
        """Validar integridad del grafo - CRIT P0"""
        errors = []

        # Verificar que todas las relaciones referencian assets existentes
        for rel in self.relations:
            if rel.source_id not in self.assets and rel.source_id not in self.chunks:
                errors.append(f"Relation {rel.relation_id}: source {rel.source_id} not found")
            if rel.target_id not in self.assets and rel.target_id not in self.chunks:
                errors.append(f"Relation {rel.relation_id}: target {rel.target_id} not found")

        # Verificar que no hay ciclos en DERIVED_FROM
        for asset_id in self.assets:
            lineage = self.get_lineage(asset_id)
            if len(lineage) != len(set(lineage)):
                errors.append(f"Cycle detected in lineage of {asset_id}")

        return errors
