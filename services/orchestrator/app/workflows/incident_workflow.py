from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.activities.enrich import enrich_activity
    from app.activities.ask_llm import ask_llm_activity
    from app.activities.decide import decide_activity
    from app.activities.execute import execute_activity

_RETRY = RetryPolicy(maximum_attempts=3)


@workflow.defn
class IncidentWorkflow:
    def __init__(self):
        self._approved = False

    @workflow.signal
    def approve_action(self):
        self._approved = True

    @workflow.run
    async def run(self, anomaly: dict) -> dict:
        context = await workflow.execute_activity(
            enrich_activity,
            anomaly,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_RETRY,
        )

        llm_response = await workflow.execute_activity(
            ask_llm_activity,
            {**anomaly, "context": context},
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=_RETRY,
        )

        decision = await workflow.execute_activity(
            decide_activity,
            llm_response,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=_RETRY,
        )

        if decision == "pending_approval":
            await workflow.wait_condition(lambda: self._approved)
            decision = "approved"

        result = await workflow.execute_activity(
            execute_activity,
            {**llm_response, "decision": decision},
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_RETRY,
        )

        return {"status": result, "anomaly_id": anomaly.get("anomaly_id")}
