"""AI Operations Assistant workflows.

Pipeline (LangGraph when installed, otherwise an equivalent sequential runner):
    gather_facts -> rule_based_analysis -> (optional) llm_narrative -> validate_output
Facts come only from DB tools. Rule-based recommendations are deterministic. The LLM may only rephrase
the facts into prose; its text is stored separately and labelled as AI-generated.
"""
import logging
from datetime import datetime
from typing import Any, Callable, TypedDict

from sqlalchemy.orm import Session

from app.ai import llm, tools
from app.core.errors import ValidationFailed
from app.services import routing_service

log = logging.getLogger(__name__)

WORKFLOWS = {
    "operations_summary": "Hospital operations summary",
    "bed_availability": "Bed availability summary",
    "capacity_constraints": "Departments with capacity constraints",
    "low_stock": "Low-stock resources",
    "pending_workflows": "Pending transfers and discharges",
    "alert_priorities": "Alert prioritisation",
    "bottlenecks": "Potential operational bottlenecks",
    "explain_routing": "Explain routing recommendation for a patient",
}


class State(TypedDict, total=False):
    db: Session
    workflow: str
    patient_id: int | None
    facts: dict[str, Any]
    recommendations: list[dict]
    headline: str
    narrative: str | None
    used_llm: bool
    errors: list[str]


def gather_facts(state: State) -> State:
    db, wf = state["db"], state["workflow"]
    f: dict[str, Any] = {}
    if wf in ("operations_summary", "bottlenecks"):
        f = {"summary": tools.hospital_summary(db), "beds": tools.bed_availability(db),
             "constraints": tools.capacity_constraints(db), "low_stock": tools.low_stock(db),
             "pending": tools.pending_workflows(db), "alerts": tools.open_alerts(db, 8)}
    elif wf == "bed_availability":
        f = {"beds": tools.bed_availability(db)}
    elif wf == "capacity_constraints":
        f = {"constraints": tools.capacity_constraints(db)}
    elif wf == "low_stock":
        f = {"low_stock": tools.low_stock(db)}
    elif wf == "pending_workflows":
        f = {"pending": tools.pending_workflows(db)}
    elif wf == "alert_priorities":
        f = {"alerts": tools.open_alerts(db, 15)}
    elif wf == "explain_routing":
        if not state.get("patient_id"):
            raise ValidationFailed("patient_id is required for explain_routing")
        f = {"routing": routing_service.recommend(db, state["patient_id"], [])}
    return {**state, "facts": f}


def rule_based_analysis(state: State) -> State:
    f, wf = state["facts"], state["workflow"]
    recs: list[dict] = []
    head = WORKFLOWS[wf]
    if "constraints" in f:
        for c in f["constraints"]:
            recs.append({"priority": "high" if c["level"] == "critical" else "medium", "ref": f"department:{c['department_id']}",
                         "text": f"{c['department']} is at {c['occupancy_pct']}% occupancy with {c['available']} bed(s) free"
                                 f"{' and ' + str(c['incoming_open_transfers']) + ' pending incoming transfer(s)' if c['incoming_open_transfers'] else ''}. "
                                 "Review discharges, cleaning turnaround, or alternative departments."})
    if "low_stock" in f:
        for r in f["low_stock"]:
            recs.append({"priority": "high" if r["level"] == "critical" else "medium", "ref": f"resource:{r['resource_id']}",
                         "text": f"{r['name']} is {r['level']} ({r['quantity']} {r['unit']} at {r['location']}). Consider restocking."})
    if "pending" in f:
        n_t, n_d = len(f["pending"]["transfers"]), len(f["pending"]["discharges"])
        if n_t or n_d:
            recs.append({"priority": "medium", "ref": "workflows",
                         "text": f"{n_t} open transfer(s) and {n_d} open discharge(s) need progress; completed discharges free beds."})
    if "alerts" in f:
        for a in f["alerts"]:
            if a["severity"] in ("critical", "warning") and not a["acknowledged"]:
                recs.append({"priority": "high" if a["severity"] == "critical" else "medium", "ref": f"notification:{a['id']}",
                             "text": f"Unacknowledged {a['severity']} alert: {a['title']}."})
    if "routing" in f:
        r = f["routing"]
        for c in r["candidates"]:
            recs.append({"priority": "info", "ref": f"department:{c['department_id']}",
                         "text": f"{c['department_name']}: {'eligible, score ' + str(c['score']) if c['eligible'] else 'not eligible'}. "
                                 + "; ".join(c["reasons"] + c["blockers"])})
    if "beds" in f and wf == "bed_availability":
        for b in f["beds"]:
            recs.append({"priority": "info", "ref": f"department:{b['department_id']}",
                         "text": f"{b['department']}: {b['available']} available, {b['occupied']} occupied, {b['cleaning']} cleaning."})
    if wf == "operations_summary":
        s = f["summary"]
        head = (f"{s['admitted_patients']} admitted patients; {s['available_beds']} beds available; occupancy {s['occupancy_rate']}%; "
                f"{s['critical_active_alerts']} critical alert(s) active.")
    if wf == "bottlenecks":
        head = "No operational bottlenecks identified from current data." if not recs else f"{len(recs)} potential bottleneck(s) identified."
    if not recs and wf not in ("operations_summary", "bottlenecks"):
        head += ": nothing requiring attention based on current data."
    return {**state, "recommendations": recs, "headline": head}


def llm_narrative(state: State) -> State:
    import json

    text = llm.generate(f"Workflow: {state['workflow']}\nFACTS (JSON):\n{json.dumps(state['facts'], default=str)[:12000]}")
    return {**state, "narrative": text, "used_llm": text is not None}


def validate_output(state: State) -> State:
    """Guardrails: drop LLM text if it looks like clinical advice; ensure structure."""
    text = state.get("narrative")
    if text:
        lowered = text.lower()
        if any(w in lowered for w in ("diagnos", "prescrib", "dosage", "administer ")):
            return {**state, "narrative": None, "used_llm": False,
                    "errors": state.get("errors", []) + ["LLM narrative discarded by safety validation"]}
    return state


NODES: list[tuple[str, Callable[[State], State]]] = [
    ("gather_facts", gather_facts), ("rule_based_analysis", rule_based_analysis),
    ("llm_narrative", llm_narrative), ("validate_output", validate_output),
]


def _run_langgraph(state: State) -> State | None:
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        return None
    graph = StateGraph(State)
    for name, fn in NODES:
        graph.add_node(name, fn)
    graph.set_entry_point("gather_facts")
    graph.add_edge("gather_facts", "rule_based_analysis")
    graph.add_conditional_edges("rule_based_analysis", lambda s: "llm_narrative" if llm.provider_status()["configured"] else "validate_output",
                                {"llm_narrative": "llm_narrative", "validate_output": "validate_output"})
    graph.add_edge("llm_narrative", "validate_output")
    graph.add_edge("validate_output", END)
    return graph.compile().invoke(state)


def run(db: Session, workflow: str, patient_id: int | None = None) -> dict:
    if workflow not in WORKFLOWS:
        raise ValidationFailed(f"Unknown workflow '{workflow}'")
    state: State = {"db": db, "workflow": workflow, "patient_id": patient_id, "errors": [], "used_llm": False, "narrative": None}
    engine = "langgraph"
    result = _run_langgraph(state)
    if result is None:
        engine = "sequential"
        result = state
        for name, fn in NODES:
            if name == "llm_narrative" and not llm.provider_status()["configured"]:
                continue
            result = fn(result)
    return {
        "workflow": workflow,
        "title": WORKFLOWS[workflow],
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "engine": engine,
        "facts": result["facts"],                       # DATABASE FACTS
        "recommendations": result["recommendations"],   # deterministic rule output (for staff review)
        "headline": result["headline"],
        "ai_narrative": result.get("narrative"),        # AI-GENERATED text (null if no provider)
        "used_llm": bool(result.get("used_llm")),
        "warnings": result.get("errors", []),
        "disclaimer": "Operational support only. Not medical advice. Recommendations require human review; the assistant never changes records.",
    }


KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("bed", "available", "availability", "beds"), "bed_availability"),
    (("capacity", "full", "constraint", "occupancy"), "capacity_constraints"),
    (("stock", "supply", "supplies", "resource", "inventory"), "low_stock"),
    (("transfer", "discharge", "pending"), "pending_workflows"),
    (("alert", "priorit", "urgent"), "alert_priorities"),
    (("bottleneck", "delay", "slow"), "bottlenecks"),
    (("routing", "route", "where should"), "explain_routing"),
]


def workflow_from_question(question: str) -> str:
    """Deterministic intent matching for the chat box (no LLM needed)."""
    q = question.lower()
    for words, wf in KEYWORDS:
        if any(w in q for w in words):
            return wf
    return "operations_summary"
