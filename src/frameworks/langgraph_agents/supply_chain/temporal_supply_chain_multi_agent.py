from __future__ import annotations
"""
supply_chain_logistics_agent_temporal.py
LangGraph workflow for a multi-agent Supply Chain & Logistics Management system, revised to use Temporal for durable orchestration.
Handles inventory management, shipping operations, supplier relations, and warehouse optimization through specialized agents orchestrated via Temporal workflows.
The workflow sequences agent steps with retries, persistent state, and failure recovery, ideal for long-running supply chain processes.
"""

import os
import json
from datetime import timedelta
from typing import Annotated, Sequence, TypedDict, Optional, Dict, Any

from temporalio import workflow, activity
from temporalio.common import RetryPolicy

from langchain_openai.chat_models import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.messages.tool import ToolMessage
from langchain_core.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

from langchain_core.tools import tool
from temporalio.client import Client
from temporalio.worker import Worker

from traceloop.sdk import Traceloop
from src.common.observability.loki_logger import log_to_loki

os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4317"
os.environ["OTEL_EXPORTER_OTLP_INSECURE"] = "true"

# Shared tool for all specialists
@tool
def send_logistics_response(operation_id: str = None, message: str = None) -> str:
    """Send logistics updates, recommendations, or status reports to stakeholders."""
    print(f"[TOOL] send_logistics_response → {message}")
    log_to_loki("tool.send_logistics_response", f"operation_id={operation_id}, message={message}")
    return "logistics_response_sent"

# Inventory & Warehouse Specialist Tools
@tool
def manage_inventory(sku: str = None, **kwargs) -> str:
    """Manage inventory levels, stock replenishment, audits, and optimization strategies."""
    print(f"[TOOL] manage_inventory(sku={sku}, kwargs={kwargs})")
    log_to_loki("tool.manage_inventory", f"sku={sku}")
    return "inventory_management_initiated"

@tool
def optimize_warehouse(operation_type: str = None, **kwargs) -> str:
    """Optimize warehouse operations, layout, capacity, and storage efficiency."""
    print(f"[TOOL] optimize_warehouse(operation_type={operation_type}, kwargs={kwargs})")
    log_to_loki("tool.optimize_warehouse", f"operation_type={operation_type}")
    return "warehouse_optimization_initiated"

@tool
def forecast_demand(season: str = None, **kwargs) -> str:
    """Analyze demand patterns, seasonal trends, and create forecasting models."""
    print(f"[TOOL] forecast_demand(season={season}, kwargs={kwargs})")
    log_to_loki("tool.forecast_demand", f"season={season}")
    return "demand_forecast_generated"

@tool
def manage_quality(supplier: str = None, **kwargs) -> str:
    """Manage quality control, defect tracking, and supplier quality standards."""
    print(f"[TOOL] manage_quality(supplier={supplier}, kwargs={kwargs})")
    log_to_loki("tool.manage_quality", f"supplier={supplier}")
    return "quality_management_initiated"

@tool
def scale_operations(scaling_type: str = None, **kwargs) -> str:
    """Scale operations for peak seasons, capacity planning, and workforce management."""
    print(f"[TOOL] scale_operations(scaling_type={scaling_type}, kwargs={kwargs})")
    log_to_loki("tool.scale_operations", f"scaling_type={scaling_type}")
    return "operations_scaled"

@tool
def optimize_costs(cost_type: str = None, **kwargs) -> str:
    """Analyze and optimize transportation, storage, and operational costs."""
    print(f"[TOOL] optimize_costs(cost_type={cost_type}, kwargs={kwargs})")
    log_to_loki("tool.optimize_costs", f"cost_type={cost_type}")
    return "cost_optimization_initiated"

INVENTORY_TOOLS = [manage_inventory, optimize_warehouse, forecast_demand, manage_quality, scale_operations, optimize_costs, send_logistics_response]

# Transportation & Logistics Specialist Tools
@tool
def track_shipments(origin: str = None, **kwargs) -> str:
    """Track shipment status, delays, and coordinate delivery logistics."""
    print(f"[TOOL] track_shipments(origin={origin}, kwargs={kwargs})")
    log_to_loki("tool.track_shipments", f"origin={origin}")
    return "shipment_tracking_updated"

@tool
def arrange_shipping(shipping_type: str = None, **kwargs) -> str:
    """Arrange shipping methods, expedited delivery, and multi-modal transportation."""
    print(f"[TOOL] arrange_shipping(shipping_type={shipping_type}, kwargs={kwargs})")
    log_to_loki("tool.arrange_shipping", f"shipping_type={shipping_type}")
    return "shipping_arranged"

@tool
def coordinate_operations(operation_type: str = None, **kwargs) -> str:
    """Coordinate complex operations like cross-docking, consolidation, and transfers."""
    print(f"[TOOL] coordinate_operations(operation_type={operation_type}, kwargs={kwargs})")
    log_to_loki("tool.coordinate_operations", f"operation_type={operation_type}")
    return "operations_coordinated"

@tool
def manage_special_handling(product_type: str = None, **kwargs) -> str:
    """Handle special requirements for hazmat, cold chain, and sensitive products."""
    print(f"[TOOL] manage_special_handling(product_type={product_type}, kwargs={kwargs})")
    log_to_loki("tool.manage_special_handling", f"product_type={product_type}")
    return "special_handling_managed"

@tool
def process_returns(returned_quantity: str = None, **kwargs) -> str:
    """Process returns, reverse logistics, and product disposition."""
    print(f"[TOOL] process_returns(returned_quantity={returned_quantity}, kwargs={kwargs})")
    log_to_loki("tool.process_returns", f"returned_quantity={returned_quantity}")
    return "returns_processed"

@tool
def optimize_delivery(delivery_type: str = None, **kwargs) -> str:
    """Optimize delivery routes, last-mile logistics, and sustainability initiatives."""
    print(f"[TOOL] optimize_delivery(delivery_type={delivery_type}, kwargs={kwargs})")
    log_to_loki("tool.optimize_delivery", f"delivery_type={delivery_type}")
    return "delivery_optimization_complete"

@tool
def manage_disruption(disruption_type: str = None, **kwargs) -> str:
    """Manage supply chain disruptions, contingency planning, and risk mitigation."""
    print(f"[TOOL] manage_disruption(disruption_type={disruption_type}, kwargs={kwargs})")
    log_to_loki("tool.manage_disruption", f"disruption_type={disruption_type}")
    return "disruption_managed"

TRANSPORTATION_TOOLS = [track_shipments, arrange_shipping, coordinate_operations, manage_special_handling, process_returns, optimize_delivery, manage_disruption, send_logistics_response]

# Supplier & Compliance Specialist Tools
@tool
def evaluate_suppliers(supplier_name: str = None, **kwargs) -> str:
    """Evaluate supplier performance, conduct audits, and manage supplier relationships."""
    print(f"[TOOL] evaluate_suppliers(supplier_name={supplier_name}, kwargs={kwargs})")
    log_to_loki("tool.evaluate_suppliers", f"supplier_name={supplier_name}")
    return "supplier_evaluation_complete"

@tool
def handle_compliance(compliance_type: str = None, **kwargs) -> str:
    """Manage regulatory compliance, customs, documentation, and certifications."""
    print(f"[TOOL] handle_compliance(compliance_type={compliance_type}, kwargs={kwargs})")
    log_to_loki("tool.handle_compliance", f"compliance_type={compliance_type}")
    return "compliance_handled"

SUPPLIER_TOOLS = [evaluate_suppliers, handle_compliance, send_logistics_response]

Traceloop.init(disable_batch=True, app_name="supply_chain_logistics_agent_temporal")

def build_llm():
    """Build the base chat model per LLM_PROVIDER (env var, default "openai"). Per-role tool bindings are applied by callers."""
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-flash-latest"),
            temperature=0.0,
        )
    return ChatOpenAI(
        model="gpt-4o", temperature=0.0,
        callbacks=[StreamingStdOutCallbackHandler()], verbose=True,
    )

llm = build_llm()

def as_text(content) -> str:
    """Normalize AIMessage.content to plain text (Gemini returns a list of content blocks; OpenAI returns str)."""
    if isinstance(content, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return content

_MESSAGE_TYPES = {"human": HumanMessage, "ai": AIMessage, "system": SystemMessage, "tool": ToolMessage}

def to_message(m):
    """Reconstruct a BaseMessage from its serialized dict (see BaseMessage.dict()) by its own
    "type" field, not blindly as one fixed class — activity/workflow payloads mix human, ai
    and tool messages, and Temporal only carries them as plain dicts across the wire."""
    if not isinstance(m, dict):
        return m
    return _MESSAGE_TYPES.get(m.get("type"), HumanMessage)(**m)

class AgentState(TypedDict):
    operation: Optional[dict]  # Supply chain operation information
    messages: Annotated[Sequence[BaseMessage], "add"]

# Temporal Activities (wrap specialist logic)
@activity.defn
async def supervisor_activity(operation: Dict[str, Any], messages: list) -> Dict[str, Any]:
    """Activity to determine specialist via supervisor."""
    operation_json = json.dumps(operation, ensure_ascii=False)
    
    supervisor_prompt = (
        "You are a supervisor coordinating a team of supply chain specialists.\n"
        "Team members:\n"
        "- inventory: Handles inventory levels, forecasting, quality, warehouse optimization, scaling, and costs.\n"
        "- transportation: Handles shipping tracking, arrangements, operations coordination, special handling, returns, delivery optimization, and disruptions.\n"
        "- supplier: Handles supplier evaluation and compliance.\n"
        "\n"
        "Based on the user query, select ONE team member to handle it.\n"
        "Output ONLY the selected member's name (inventory, transportation, or supplier), nothing else.\n\n"
        f"OPERATION: {operation_json}"
    )

    full = [SystemMessage(content=supervisor_prompt)] + [to_message(m) for m in messages]
    response = llm.invoke(full)
    agent_name = as_text(response.content).strip().lower()
    return {"agent_name": agent_name, "messages": [response.dict()]}

@activity.defn
async def specialist_activity(agent_name: str, operation: Dict[str, Any], messages: list) -> Dict[str, Any]:
    """Activity for specialist processing (inventory, transportation, supplier).

    Builds its own LLM from `agent_name` rather than receiving a live LLM or
    tool object as an argument: Temporal serializes every activity argument
    with its data converter (JSON by default), which can't encode a bound
    LLM client or a StructuredTool.
    """
    if agent_name not in prompts:
        raise ValueError(f"Unknown agent: {agent_name}")

    role_tools = tools_dict[agent_name]
    specialist_llm = build_llm().bind_tools(role_tools)
    tools = {t.name: t for t in role_tools}
    system_prompt = prompts[agent_name]
    
    operation_json = json.dumps(operation, ensure_ascii=False)
    full_prompt = system_prompt + f"\n\nOPERATION: {operation_json}"
    
    full = [SystemMessage(content=full_prompt)] + [to_message(m) for m in messages]

    first = specialist_llm.invoke(full)
    result_messages = [first.dict()]

    if getattr(first, "tool_calls", None):
        for tc in first.tool_calls:
            fn = tools.get(tc['name'])
            if fn:
                out = fn.invoke(tc["args"])
                result_messages.append(ToolMessage(content=str(out), tool_call_id=tc["id"]).dict())

        second = specialist_llm.invoke(full + [to_message(msg) for msg in result_messages])
        result_messages.append(second.dict())

    return {"messages": result_messages}

# Temporal Workflow
@workflow.defn(name="SupplyChainWorkflow")
class SupplyChainWorkflow:
    @workflow.run
    async def run(self, operation: Dict[str, Any], initial_messages: list) -> Dict[str, Any]:
        # Step 1: Supervisor to route
        supervisor_result = await workflow.execute_activity(
            supervisor_activity,
            args=[operation, initial_messages],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        agent_name = supervisor_result["agent_name"]
        updated_messages = initial_messages + supervisor_result["messages"]
        
        # Step 2: Specialist processing
        specialist_result = await workflow.execute_activity(
            specialist_activity,
            args=[agent_name, operation, updated_messages],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        # Compile results (extend for multi-step if needed)
        final_messages = updated_messages + specialist_result["messages"]
        return {
            "agent_name": agent_name,
            "final_messages": final_messages,
            "operation": operation
        }

# Prompts
inventory_prompt = (
    "You are an inventory and warehouse management specialist.\n"
    "When managing:\n"
    "  1) Analyze the inventory/warehouse challenge\n"
    "  2) Call the appropriate tool\n"
    "  3) Follow up with send_logistics_response\n"
    "Consider cost, efficiency, and scalability."
)
transportation_prompt = (
    "You are a transportation and logistics specialist.\n"
    "When managing:\n"
    "  1) Analyze the shipping/delivery challenge\n"
    "  2) Call the appropriate tool\n"
    "  3) Follow up with send_logistics_response\n"
    "Consider efficiency, sustainability, and risk mitigation."
)
supplier_prompt = (
    "You are a supplier relations and compliance specialist.\n"
    "When managing:\n"
    "  1) Analyze the supplier/compliance issue\n"
    "  2) Call the appropriate tool\n"
    "  3) Follow up with send_logistics_response\n"
    "Consider performance, regulations, and relationships."
)

prompts = {
    "inventory": inventory_prompt,
    "transportation": transportation_prompt,
    "supplier": supplier_prompt
}

tools_dict = {
    "inventory": INVENTORY_TOOLS,
    "transportation": TRANSPORTATION_TOOLS,
    "supplier": SUPPLIER_TOOLS
}

async def main():
    client = await Client.connect("localhost:7233")
    # Start worker
    async with Worker(client, task_queue="supply-chain-queue", workflows=[SupplyChainWorkflow], activities=[supervisor_activity, specialist_activity]):
        # Example execution
        example_operation = {"operation_id": "OP-12345", "type": "inventory_management", "priority": "high", "location": "Warehouse A"}
        example_messages = [{"content": "We're running critically low on SKU-12345. Current stock is 50 units but we have 200 units on backorder. What's our reorder strategy?", "type": "human"}]

        result = await client.execute_workflow(
            SupplyChainWorkflow.run,
            args=[example_operation, example_messages],
            id="supply-chain-workflow",
            task_queue="supply-chain-queue"
        )
        print("Workflow result:")
        for m in result["final_messages"]:
            print(m)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
