from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.services.wiki_generate_service import WikiGenerateService


def test_filter_material_knowledge_points_excludes_other_materials() -> None:
    material_a = uuid4()
    material_b = uuid4()
    point_a = SimpleNamespace(
        extra_meta={"normalization": {"source_material_ids": [str(material_a)]}}
    )
    point_b = SimpleNamespace(
        extra_meta={"normalization": {"source_material_ids": [str(material_b)]}}
    )
    legacy_point = SimpleNamespace(extra_meta={})

    selected = WikiGenerateService._filter_material_knowledge_points(
        [point_a, point_b, legacy_point],
        material_a,
    )

    assert selected == [point_a]


def test_source_chunks_for_point_uses_normalization_source_ids() -> None:
    first_id = uuid4()
    second_id = uuid4()
    unrelated_id = uuid4()
    point = SimpleNamespace(
        id=uuid4(),
        extra_meta={
            "normalization": {
                "source_chunk_ids": [str(first_id), str(second_id)],
            }
        },
    )
    chunks = [
        SimpleNamespace(id=first_id, knowledge_id=None),
        SimpleNamespace(id=second_id, knowledge_id=None),
        SimpleNamespace(id=unrelated_id, knowledge_id=point.id),
    ]

    selected = WikiGenerateService._source_chunks_for_point(point, chunks)

    assert [chunk.id for chunk in selected] == [first_id, second_id]
