import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import llm, workflows
from app.db.types import utcnow
from app.models.audit import AIWorkflowExecution
from app.models.enums import NotificationCategory as Cat
from app.models.enums import NotificationSeverity as Sev
from app.models.enums import WorkflowStatus
from app.models.user import User
from app.services import audit_service
from app.services import notification_service as ns


def run_workflow(db: Session, actor: User, workflow: str, patient_id: int | None) -> tuple[AIWorkflowExecution, dict | None]:
    ex = AIWorkflowExecution(workflow=workflow, input={"patient_id": patient_id}, requested_by=actor.id,
                             provider=llm.provider_status()["provider"])
    db.add(ex)
    db.commit()  # persist "running" so failures are visible even if the workflow raises
    started = time.perf_counter()
    try:
        output = workflows.run(db, workflow, patient_id)
        ex.status, ex.output, ex.used_llm = WorkflowStatus.COMPLETED.value, {
            "headline": output["headline"], "engine": output["engine"], "recommendation_count": len(output["recommendations"]),
            "duration_ms": int((time.perf_counter() - started) * 1000)}, output["used_llm"]
        ex.finished_at = utcnow()
        audit_service.log_action(db, actor, "ai.workflow_run", "ai_workflow", ex.id, {"workflow": workflow, "used_llm": output["used_llm"]})
        db.commit()
        return ex, output
    except Exception as exc:
        db.rollback()
        ex = db.get(AIWorkflowExecution, ex.id)
        ex.status, ex.error, ex.finished_at = WorkflowStatus.FAILED.value, f"{type(exc).__name__}: {str(exc)[:300]}", utcnow()
        ns.create_notification(db, title=f"AI workflow failed: {workflow}", description="See AI execution history for details.",
                               category=Cat.AI, severity=Sev.WARNING, entity_type="ai_workflow", entity_id=ex.id,
                               event_key=f"ai:{ex.id}:failed")
        db.commit()
        raise


def list_executions(db: Session, limit: int = 25) -> list[AIWorkflowExecution]:
    return list(db.scalars(select(AIWorkflowExecution).order_by(AIWorkflowExecution.started_at.desc()).limit(limit)))
