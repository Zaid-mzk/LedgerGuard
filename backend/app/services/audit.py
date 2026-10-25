from app.models.entities import AuditEvent


def audit(db, actor_id, action, entity_type, entity_id=None, metadata=None):
    db.add(
        AuditEvent(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata or {},
        )
    )
