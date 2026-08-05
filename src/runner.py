import json
from src.audit import TraceLogger, write_metadata
from src.config import AGENT_MODEL_NAME, AGENT_MODEL_PARAMETER_SIZE_B

from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.agents import (
    CustomerAgent,
    DeliveryAgent,
    OrderProductAgent,
    PaymentAgent,
)
from src.data_repository import DataRepository
from src.policy import PolicyAgent
from src.verifier import OutputVerifier


class Coordinator:
    def __init__(
    self,
    data_dir: str | Path = "data",
    trace_logger: TraceLogger | None = None,
    ) -> None:
        self.repository = DataRepository(data_dir)
        self.customer_agent = CustomerAgent()
        self.order_product_agent = OrderProductAgent()
        self.payment_agent = PaymentAgent()
        self.delivery_agent = DeliveryAgent()
        self.policy_agent = PolicyAgent()
        self.verifier = OutputVerifier()
        self.trace_logger = trace_logger

    def _emit(
    self,
    case_id: str,
    event: str,
    payload: dict[str, Any],
    ) -> None:
        if self.trace_logger is not None:
            self.trace_logger.emit(case_id, event, payload)

    def process_case(self, case: dict[str, Any]) -> dict[str, Any]:
        self._validate_input(case)

        case_id = case["case_id"]
        order_id = case["customer_request"]["claimed_order_id"]

        self._emit(
            case_id,
            "case_received",
            {"claimed_order_id": order_id},
        )

        bundle = self.repository.get_order_bundle(order_id)

        self._emit(
            case_id,
            "data_loaded",
            {
                "order_status": str(bundle.order["order_status"]),
                "item_row_count": len(bundle.items),
                "payment_row_count": len(bundle.payments),
            },
        )

        # Handoff giữa các agent.
        customer = self.customer_agent.analyze(bundle)
        order_product = self.order_product_agent.analyze(bundle)
        payment = self.payment_agent.analyze(bundle, order_product)
        delivery = self.delivery_agent.analyze(bundle)

        self._emit(
            case_id,
            "customer_handoff",
            {
                "customer_unique_id": customer.customer_unique_id,
                "related_order_count": len(customer.related_order_ids),
            },
        )
        self._emit(
            case_id,
            "order_product_handoff",
            {
                "item_count": order_product.item_count,
                "seller_count": order_product.seller_count,
                "category_count": order_product.category_count,
                "item_total_brl": order_product.item_total_brl,
                "freight_total_brl": order_product.freight_total_brl,
            },
        )
        self._emit(
            case_id,
            "payment_handoff",
            {
                "payment_count": payment.payment_count,
                "payment_total_brl": payment.payment_total_brl,
                "expected_total_brl": payment.expected_total_brl,
                "difference_brl": payment.difference_brl,
                "reconciled": payment.reconciled,
            },
        )
        self._emit(
            case_id,
            "delivery_handoff",
            {
                "delivery_variance_hours": delivery.delivery_variance_hours,
                "late_handoff_seller_ids": delivery.late_handoff_seller_ids,
            },
        )

        decision = self.policy_agent.analyze(
            bundle=bundle,
            customer=customer,
            order_product=order_product,
            payment=payment,
            delivery=delivery,
        )

        self._emit(
            case_id,
                "policy_decision",
                {
                    "primary_issue": decision.primary_issue,
                    "secondary_issues": decision.secondary_issues,
                    "case_status": decision.case_status,
                    "recommended_refund_brl": decision.recommended_refund_brl,
                    "resolution_actions": decision.resolution_actions,
                },
            )

        result = self._build_output(
            case_id=case_id,
            bundle=bundle,
            customer=customer,
            order_product=order_product,
            payment=payment,
            delivery=delivery,
            decision=decision,
        )

        self.verifier.validate(result)

        self._emit(
            case_id,
            "output_verified",
            {"output_case_id": result["case_id"]},
        )
        return result

    def _validate_input(self, case: dict[str, Any]) -> None:
        if not isinstance(case.get("case_id"), str):
            raise ValueError("Input thiếu case_id")

        request = case.get("customer_request", {})
        if not isinstance(request.get("claimed_order_id"), str):
            raise ValueError("Input thiếu customer_request.claimed_order_id")

        if case.get("policy_version") != "EC_POLICY_V2":
            raise ValueError("Chỉ hỗ trợ EC_POLICY_V2")

    def _build_output(
        self,
        case_id,
        bundle,
        customer,
        order_product,
        payment,
        delivery,
        decision,
    ) -> dict[str, Any]:
        order_id = str(bundle.order["order_id"])

        # Dùng danh sách đã cắt để mọi phần output/evidence nhất quán.
        item_ids = order_product.item_ids[:5]
        seller_ids = order_product.seller_ids[:3]
        payment_ids = payment.payment_ids[:5]
        product_ids = order_product.product_ids[:5]
        category_names = order_product.category_names[:5]
        related_order_ids = customer.related_order_ids[:5]

        responsible_parties = [
            asdict(party) for party in decision.responsible_parties[:3]
        ]
        ranked_causes = [
            asdict(cause) for cause in decision.ranked_causes[:3]
        ]

        seller_handoff_analysis = [
            asdict(handoff)
            for handoff in delivery.seller_handoff_analysis[:3]
        ]
        late_handoff_seller_ids = delivery.late_handoff_seller_ids[:3]

        evidence_ids = self._build_evidence(
            order_id=order_id,
            item_ids=item_ids,
            payment_ids=payment_ids,
            responsible_parties=responsible_parties,
            cause_code=ranked_causes[0]["cause_code"],
        )

        return {
            "case_id": case_id,
            "case_assessment": {
                "primary_issue": decision.primary_issue,
                "secondary_issues": decision.secondary_issues,
                "case_status": decision.case_status,
                "confidence": decision.confidence,
            },
            "affected_entities": {
                "order_ids": [order_id],
                "item_ids": item_ids,
                "seller_ids": seller_ids,
                "payment_ids": payment_ids,
            },
            "customer_context": {
                "customer_unique_id": customer.customer_unique_id,
                "related_order_ids": related_order_ids,
            },
            "product_context": {
                "product_ids": product_ids,
                "category_names": category_names,
            },
            "delivery_analysis": {
                "delivered_at": delivery.delivered_at,
                "estimated_delivery_at": delivery.estimated_delivery_at,
                "carrier_handoff_at": delivery.carrier_handoff_at,
                "delivery_variance_hours": delivery.delivery_variance_hours,
                "seller_handoff_analysis": seller_handoff_analysis,
                "late_handoff_seller_ids": late_handoff_seller_ids,
            },
            "payment_reconciliation": {
                "currency": "BRL",
                "item_total_brl": order_product.item_total_brl,
                "freight_total_brl": order_product.freight_total_brl,
                "expected_total_brl": payment.expected_total_brl,
                "payment_total_brl": payment.payment_total_brl,
                "difference_brl": payment.difference_brl,
                "reconciled": payment.reconciled,
                "payment_types": payment.payment_types,
            },
            "root_cause_analysis": {
                "ranked_causes": ranked_causes,
                "responsible_parties": responsible_parties,
            },
            "evidence_ids": evidence_ids,
            "financial_resolution": {
                "currency": "BRL",
                "recommended_refund_brl": decision.recommended_refund_brl,
            },
            "resolution_actions": decision.resolution_actions,
        }

    def _build_evidence(
        self,
        order_id: str,
        item_ids: list[str],
        payment_ids: list[str],
        responsible_parties: list[dict[str, str]],
        cause_code: str,
    ) -> list[str]:
        evidence = [f"order:{order_id}"]

        evidence.extend(f"item:{item_id}" for item_id in item_ids)
        evidence.extend(f"payment:{payment_id}" for payment_id in payment_ids)

        # Chỉ seller chịu trách nhiệm mới có seller evidence hợp lệ.
        for party in responsible_parties:
            if party["party_type"] == "seller":
                evidence.append(f"seller:{party['party_id']}")

        evidence.append(f"policy:{cause_code}")
        return evidence[:20]


def run_all(
    input_dir: str | Path = "input",
    output_dir: str | Path = "output",
) -> None:
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    input_files = sorted(input_dir.glob("EC_*.json"))
    if not input_files:
        raise FileNotFoundError("Không tìm thấy input/EC_*.json")

    trace = TraceLogger("logging/trace.jsonl")
    coordinator = Coordinator(trace_logger=trace)

    try:
        trace.emit(
            None,
            "run_started",
            {"input_case_count": len(input_files)},
        )

        for input_path in input_files:
            with input_path.open("r", encoding="utf-8") as file:
                case = json.load(file)

            result = coordinator.process_case(case)

            output_path = output_dir / input_path.name
            with output_path.open("w", encoding="utf-8") as file:
                json.dump(
                    result,
                    file,
                    ensure_ascii=False,
                    indent=2,
                    allow_nan=False,
                )

            trace.emit(
                case["case_id"],
                "output_written",
                {"output_file": str(output_path)},
            )
            print(f"Đã tạo: {output_path}")

        trace.emit(
            None,
            "run_completed",
            {"output_case_count": len(input_files)},
        )

    finally:
        trace.close()

    write_metadata(
        path="logging/metadata.json",
        total_cases=len(input_files),
        model_name=AGENT_MODEL_NAME,
        parameter_size_b=AGENT_MODEL_PARAMETER_SIZE_B,
    )


if __name__ == "__main__":
    run_all()