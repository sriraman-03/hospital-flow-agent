from fastapi import APIRouter, Depends

from app.ai import llm, workflows
from app.api.deps import DB, require
from app.core.errors import ValidationFailed
from app.schemas.operations import AIExecutionOut, AIRunRequest
from app.services import ai_service

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status")
def status(_=Depends(require("ai:use"))):
    return {"llm": llm.provider_status(), "workflows": workflows.WORKFLOWS,
            "note": "Rule-based analysis always works. A configured LLM only adds a narrative summary of database facts."}


@router.post("/workflows/run")
def run_workflow(body: AIRunRequest, db: DB, user=Depends(require("ai:use"))):
    workflow = body.workflow
    if workflow == "ask":
        if not body.question:
            raise ValidationFailed("question is required for workflow 'ask'")
        workflow = workflows.workflow_from_question(body.question)
    execution, output = ai_service.run_workflow(db, user, workflow, body.patient_id)
    return {"execution_id": execution.id, "status": execution.status, **output}


@router.get("/executions", response_model=list[AIExecutionOut])
def executions(db: DB, _=Depends(require("ai:use"))):
    return ai_service.list_executions(db)
