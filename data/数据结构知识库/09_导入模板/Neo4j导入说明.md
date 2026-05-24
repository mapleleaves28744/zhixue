# Neo4j 导入示例

以下 Cypher 仅作为模板，路径需按你的 Neo4j import 目录调整。

```cypher
LOAD CSV WITH HEADERS FROM 'file:///entities.csv' AS row
MERGE (e:Entity {id: row.entity_id})
SET e.name = row.name,
    e.type = row.entity_type,
    e.description = row.description,
    e.difficulty = row.difficulty,
    e.tags = split(row.tags, '|');

LOAD CSV WITH HEADERS FROM 'file:///triples.csv' AS row
MATCH (h:Entity {id: row.head})
MATCH (t:Entity {id: row.tail})
CALL apoc.create.relationship(h, row.relation, {evidence: row.evidence, weight: toFloat(row.weight), triple_id: row.triple_id}, t)
YIELD rel
RETURN count(rel);
```

若未安装 APOC，可按关系类型分批导入，或在后端读取 triples.csv 后调用 Neo4j Driver 创建关系。
