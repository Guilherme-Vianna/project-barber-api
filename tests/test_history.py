from app.models import Base


def test_every_entity_has_a_history_table() -> None:
    entities = [mapper.class_ for mapper in Base.registry.mappers]
    assert entities
    for entity in entities:
        history = getattr(entity, "__history_table__", None)
        assert history is not None, f"{entity.__name__} must be decorated with @versioned"
        assert set(entity.__table__.columns.keys()) <= set(history.columns.keys())
