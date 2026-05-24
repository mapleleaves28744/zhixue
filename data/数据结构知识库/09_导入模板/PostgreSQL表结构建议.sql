-- 数据结构课程知识库表结构建议

CREATE TABLE ds_concept (
    concept_id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    module VARCHAR(128) NOT NULL,
    definition TEXT NOT NULL,
    difficulty VARCHAR(32),
    tags TEXT
);

CREATE TABLE ds_kb_chunk (
    chunk_id VARCHAR(32) PRIMARY KEY,
    title VARCHAR(256) NOT NULL,
    module VARCHAR(128),
    concepts TEXT,
    content TEXT NOT NULL,
    tags TEXT,
    difficulty VARCHAR(32),
    embedding VECTOR
);

CREATE TABLE ds_question (
    question_id VARCHAR(32) PRIMARY KEY,
    type VARCHAR(32) NOT NULL,
    module VARCHAR(128),
    concept VARCHAR(128),
    stem TEXT NOT NULL,
    options_json TEXT,
    answer TEXT,
    analysis TEXT,
    difficulty VARCHAR(32),
    tags TEXT
);

CREATE TABLE ds_kg_triple (
    triple_id VARCHAR(32) PRIMARY KEY,
    head VARCHAR(64) NOT NULL,
    relation VARCHAR(64) NOT NULL,
    tail VARCHAR(64) NOT NULL,
    evidence TEXT,
    weight FLOAT
);
