"""Neo4j graph persistence for IntelliGraph documents and relationships."""

from __future__ import annotations

from typing import Any


class Neo4jGraphStore:
    def __init__(self, uri: str | None, user: str | None, password: str | None, database: str = "neo4j"):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.driver: Any | None = None
        self.error: str | None = None
        if uri and user and password:
            self._connect()

    @property
    def available(self) -> bool:
        return self.driver is not None

    def _connect(self) -> None:
        try:
            from neo4j import GraphDatabase

            driver: Any = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self.driver = driver
            driver.verify_connectivity()
        except Exception as exc:  # pragma: no cover - service dependent
            self.error = str(exc)
            self.driver = None

    def sync_document(self, document: dict[str, Any]) -> None:
        if not self.available:
            return
        self.delete_document(document["id"])
        query = """
        MERGE (d:Document {id: $document_id})
        SET d.name = $document_name, d.label = $document_name, d.created_at = $created_at,
            d.extraction_method = $extraction_method
        WITH d
        UNWIND $chunks AS chunk
        MERGE (c:Chunk {id: chunk.id})
        SET c.text = chunk.text, c.index = chunk.index, c.label = chunk.id
        MERGE (d)-[:HAS_CHUNK {document_id: $document_id}]->(c)
        WITH d
        UNWIND $topics AS topic
        MERGE (t:Topic {id: topic.id})
        SET t.label = topic.label, t.score = topic.score
        MERGE (d)-[:HAS_TOPIC {document_id: $document_id}]->(t)
        WITH d
        UNWIND $entities AS entity
        MERGE (e:Entity {id: entity.id})
        SET e.label = entity.label, e.entity_type = entity.entity_type,
            e.description = entity.description, e.aliases = entity.aliases,
            e.extraction_method = entity.extraction_method
        MERGE (d)-[:MENTIONS {document_id: $document_id}]->(e)
        WITH d
        UNWIND $relationships AS relationship
        MATCH (source:Entity {id: relationship.source_id})
        MATCH (target:Entity {id: relationship.target_id})
        MERGE (source)-[r:RELATION {document_id: $document_id, source_id: relationship.source_id, target_id: relationship.target_id, relation: relationship.relation}]->(target)
        SET r.label = relationship.relation, r.evidence = relationship.evidence,
            r.chunk_id = relationship.chunk_id, r.extraction_method = $extraction_method
        """
        params = {
            "document_id": document["id"],
            "document_name": document["name"],
            "created_at": document.get("created_at"),
            "extraction_method": document.get("extraction_method", "heuristic"),
            "chunks": document.get("chunks", []),
            "topics": document.get("topics", []),
            "entities": [
                {
                    "id": self.entity_id(entity["name"]),
                    "label": entity["name"],
                    "entity_type": entity.get("type", "Other"),
                    "description": entity.get("description", ""),
                    "aliases": entity.get("aliases", []),
                    "extraction_method": document.get("extraction_method", "heuristic"),
                }
                for entity in document.get("entities", [])
            ],
            "relationships": [
                {
                    "source_id": self.entity_id(relationship["source"]),
                    "target_id": self.entity_id(relationship["target"]),
                    "relation": relationship["relation"],
                    "evidence": relationship.get("evidence", ""),
                    "chunk_id": relationship.get("chunk_id", ""),
                }
                for relationship in document.get("relationships", [])
            ],
        }
        driver = self.driver
        if driver is not None:
            driver.execute_query(query, parameters_=params, database_=self.database)

    def delete_document(self, document_id: str) -> None:
        if not self.available:
            return
        query = """
        MATCH (d:Document {id: $document_id})
        OPTIONAL MATCH (d)-[r]-(connected)
        DELETE r, d
        WITH collect(connected) AS connected_nodes
        UNWIND connected_nodes AS node
        WITH node WHERE NOT (node)--()
        DELETE node
        """
        driver = self.driver
        if driver is not None:
            driver.execute_query(query, document_id=document_id, database_=self.database)

    @staticmethod
    def entity_id(label: str) -> str:
        import re

        return f"entity:{re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')}"

    def graph(self, document_id: str | None = None) -> dict[str, list[dict[str, Any]]]:
        if not self.available:
            return {"nodes": [], "edges": []}
        query = """
        MATCH (source)-[relationship]->(target)
        WHERE $document_id IS NULL OR relationship.document_id = $document_id
        RETURN source.id AS source_id, source.label AS source_label, source.entity_type AS source_entity_type,
               source.description AS source_description, source.aliases AS source_aliases, source.extraction_method AS source_extraction_method, labels(source) AS source_types,
               target.id AS target_id, target.label AS target_label, target.entity_type AS target_entity_type,
               target.description AS target_description, target.aliases AS target_aliases, target.extraction_method AS target_extraction_method, labels(target) AS target_types,
               relationship.document_id AS document_id, relationship.label AS relation,
               relationship.evidence AS evidence, relationship.chunk_id AS chunk_id, relationship.extraction_method AS extraction_method,
               type(relationship) AS relation_type
        """
        driver = self.driver
        if driver is None:
            return {"nodes": [], "edges": []}
        records, _, _ = driver.execute_query(query, document_id=document_id, database_=self.database)
        nodes: dict[str, dict[str, Any]] = {}
        edges: list[dict[str, Any]] = []
        for record in records:
            source_id = record["source_id"]
            target_id = record["target_id"]
            nodes[source_id] = {
                "id": source_id,
                "label": record["source_label"] or source_id,
                "type": self.node_type(record["source_types"]),
                "entity_type": record["source_entity_type"],
                "description": record["source_description"] or "",
                "aliases": record["source_aliases"] or [],
                "extraction_method": record["source_extraction_method"] or "heuristic",
            }
            nodes[target_id] = {
                "id": target_id,
                "label": record["target_label"] or target_id,
                "type": self.node_type(record["target_types"]),
                "entity_type": record["target_entity_type"],
                "description": record["target_description"] or "",
                "aliases": record["target_aliases"] or [],
                "extraction_method": record["target_extraction_method"] or "heuristic",
            }
            edges.append({
                "id": f"{source_id}|{record['relation'] or record['relation_type']}|{target_id}|{record['document_id']}",
                "source": source_id,
                "target": target_id,
                "label": record["relation"] or record["relation_type"],
                "weight": 1,
                "evidence": record["evidence"] or "",
                "document_id": record["document_id"],
                "chunk_id": record["chunk_id"] or "",
                "extraction_method": record["extraction_method"] or "heuristic",
            })
        return {"nodes": list(nodes.values()), "edges": edges}

    @staticmethod
    def node_type(labels: list[str]) -> str:
        for label in ("Document", "Topic", "Entity", "Chunk"):
            if label in labels:
                return label.lower()
        return "entity"

    def status(self) -> dict[str, Any]:
        return {
            "provider": "neo4j",
            "enabled": bool(self.uri and self.user and self.password),
            "available": self.available,
            "uri": self.uri,
            "database": self.database,
            "error": self.error,
        }

    def close(self) -> None:
        if self.driver is not None:
            self.driver.close()
