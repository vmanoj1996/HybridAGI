from typing import Union, List, Optional, Dict
import json
from uuid import UUID
from collections import OrderedDict
from hybridagi.memory.fact_memory import FactMemory
from hybridagi.core.datatypes import Entity, EntityList, Fact, FactList, Relationship, GraphProgram
from hybridagi.embeddings.embeddings import Embeddings
from .falkordb_memory import FalkorDBMemory

class FalkorDBFactMemory(FalkorDBMemory, FactMemory):
    """
    A class used to manage and store facts using FalkorDB.

    This class extends FalkorDBMemory and implements the FactMemory interface,
    providing a robust solution for storing and managing facts in a graph database.
    It allows for efficient storage, retrieval, and manipulation of entities and
    their relationships (facts) using FalkorDB's graph capabilities.
    """
   
    def __init__(
        self,
        index_name: str,
        graph_index: str = "fact_memory",
        hostname: str = "localhost",
        port: int = 6379,
        username: str = "",
        password: str = "",
        wipe_on_start: bool = False,
    ):
        super().__init__(
            index_name = index_name,
            graph_index = graph_index,
            hostname = hostname,
            port = port,
            username = username,
            password = password,
            wipe_on_start = wipe_on_start,
        )

    def exist(self, entity_or_fact_id: Union[UUID, str]) -> bool:
        """
        Check if a fact or entity exists in the database.

        Args:
            entity_or_fact_id: The ID of the fact or entity to check.

        Returns:
            bool: True if the fact or entity exists, False otherwise.
        """
        result = super().exist(entity_or_fact_id, "Entity")
        if result:
            return result
        else:
            return super().exist_fact(entity_or_fact_id)

    def update(self, entities_or_facts: Union[Entity, EntityList, Fact, FactList]) -> None:
        """
        Update the FalkorDB fact memory with new entities or facts.

        Parameters:
            entities_or_facts (Union[Entity, EntityList, Fact, FactList]): An entity or a list of entities, or a fact or a list of facts to be added to the memory.

        Raises:
            ValueError: If the input is not an Entity, EntityList, Fact, or FactList.
        """
        if not isinstance(entities_or_facts, (Entity, EntityList, Fact, FactList)):
            raise ValueError("Invalid datatype provided must be Entity, EntityList, Fact or FactList")
        if isinstance(entities_or_facts, Entity) or isinstance(entities_or_facts, EntityList):
            if isinstance(entities_or_facts, Entity):
                entities = EntityList()
                entities.entities = [entities_or_facts]
            else:
                entities = entities_or_facts
            for ent in entities.entities:
                ent_id = str(ent.id)
                params = {
                    "id": ent_id,
                    "name": ent.name,
                    "description": ent.description,
                    "vector": list(ent.vector) if ent.vector is not None else None,
                    "metadata": json.dumps(ent.metadata),
                }
                self._graph.query(
                    " ".join([
                    "MERGE (e:Entity,",
                    str(ent.label),
                    "{id: $id})",
                    "SET",
                    "e.name=$name,",
                    "e.description=$description,",
                    "e.metadata=$metadata,",
                    "e.vector=vecf32($vector)"]),
                    params = params,
                )
        else:
            if isinstance(entities_or_facts, Fact):
                facts = FactList()
                facts.facts = [entities_or_facts]
            else:
                facts = entities_or_facts
            for fact in facts.facts:
                fact_id = str(fact.id)
                if not self.exist(fact.subj.id):
                    self.update(fact.subj)
                if not self.exist(fact.obj.id):
                    self.update(fact.obj)
                params = {
                    "id": fact_id,
                    "subject_id": fact.subj.id,
                    "object_id": fact.obj.id,
                    "properties": {
                        "relationship": fact.rel.name,
                        "vector": list(fact.vector) if fact.vector is not None else None,
                        "metadata": json.dumps(fact.metadata),
                    },
                }
                self._graph.query(
                    " ".join([
                        "MATCH (s:Entity {id: $subject_id}),",
                        "(o:Entity {id: $object_id})",
                        "MERGE (s)-[r:FACT {id: $id}]->(o)",
                        "SET r += $properties",
                    ]),
                    params=params,
                )

    def remove(self, id_or_ids: Union[UUID, str, List[Union[UUID, str]]]) -> None:
        """
        Remove entities or facts from the FalkorDB fact memory.

        Parameters:
            id_or_ids (Union[UUID, str, List[Union[UUID, str]]]): A single entity or fact id or a list of entity or fact ids to be removed from the memory.
        """
        if not isinstance(id_or_ids, list):
            entities_ids = [id_or_ids]
        else:
            entities_ids = id_or_ids
        result = EntityList()
        ids = [str(i) for i in id_or_ids]
        self._graph.query(
            " ".join([
                "MATCH (e:Entity) WHERE e.id IN $ids",
                "DETACH DELETE e"]),
            params={"ids": ids}
        )
        self._graph.query(
            " ".join([
                "MATCH ()-[r:FACT {id: $id}]->()",
                "WHERE r.id IN $ids",
                "DELETE r"]),
            params={"ids": ids}
        )

    def get_entities(self, id_or_ids: Union[UUID, str, List[Union[UUID, str]]]) -> EntityList:
        """
        Retrieve entities from the FalkorDB fact memory.

        Parameters:
            id_or_ids (Union[UUID, str, List[Union[UUID, str]]]): A single entity id or a list of entity ids to be retrieved from the memory.

        Returns:
            EntityList: A list of entities that match the input ids.
        """
        if not isinstance(id_or_ids, list):
            entities_ids = [id_or_ids]
        else:
            entities_ids = id_or_ids
        result = EntityList()
        ids = [str(i) for i in id_or_ids]
        query_result = self._graph.query(
            " ".join([
                "MATCH (e:Entity) WHERE e.id IN $ids",
                "RETURN e"]),
            params={"ids": ids}
        )
        for row in query_result.result_set:
            entity_data = row[0]
            try:
                entity_id = UUID(entity_data.properties["id"])
            except Exception:
                entity_id = entity_data.properties["id"]
            entity = Entity(
                id=entity_id,
                name=entity_data.properties["name"],
                label=entity_data.properties["label"],
                description=entity_data.properties["description"],
                vector=entity_data.properties["vector"],
            )
            result.entities.append(entity)
        return result

    def get_facts(self, id_or_ids: Union[UUID, str, List[Union[UUID, str]]]) -> FactList:
        """
        Retrieve facts from the FalkorDB fact memory.

        Parameters:
            id_or_ids (Union[UUID, str, List[Union[UUID, str]]]): A single fact id or a list of fact ids to be retrieved from the memory.

        Returns:
            FactList: A list of facts that match the input ids.
        """
        if not isinstance(id_or_ids, list):
            entities_ids = [id_or_ids]
        else:
            entities_ids = id_or_ids
        result = EntityList()
        ids = [str(i) for i in id_or_ids]
        query_result = self._graph.query(
            " ".join([
                "MATCH (s:Entity)-[r:FACT {id: $id}]->(o:Entity)",
                "WHERE e.id IN $ids",
                "RETURN r, s, o"]),
            params={"ids": ids}
        )
        for row in query_result.result_set:
            fact_data, subject_data, object_data = row
            try:
                subject_id = UUID(subject_data.properties["id"])
            except Exception:
                subject_id = subject_data.properties["id"]
            subj = Entity(
                id=subject_id,
                name=subject_data.properties["name"], 
                label=subject_data.properties["label"],
                description=subject_data.properties["description"], 
                vector=subject_data.properties["vector"],
                metadata=json.loads(subject_data.properties["metadata"]), 
            )
            rel = Relationship(name=fact_data.properties["relationship"])
            try:
                object_id = UUID(object_data.properties["id"])
            except Exception:
                object_id = object_data.properties["id"]
            obj = Entity(
                id=object_id,
                name=object_data.properties["name"], 
                label=object_data.properties["label"],
                description=object_data.properties["description"], 
                vector=object_data.properties["vector"],
                metadata=json.loads(object_data.properties["metadata"]),
            )
            try:
                fact_id = UUID(entity_data.properties["id"])
            except Exception:
                fact_id = entity_data.properties["id"]
            fact = Fact(
                id=fact_id,
                subj=subj,
                rel=rel,
                obj=obj,
                vector=fact_data.properties["vector"],
                metadata=json.loads(fact_data.properties["vector"]),
            )
            result.facts.append(fact)
        return result