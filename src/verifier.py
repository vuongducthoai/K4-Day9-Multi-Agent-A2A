import math
import re
from datetime import datetime
from typing import Any


class OutputVerifier:
    MAX_ITEMS = 5
    MAX_SELLERS = 3
    MAX_PAYMENTS = 5
    MAX_RELATED_ORDERS = 5
    MAX_PRODUCTS = 5
    MAX_CATEGORIES = 5
    MAX_CAUSES = 3
    MAX_PARTIES = 3
    MAX_EVIDENCE = 20
    MAX_ACTIONS = 5

    def validate(self, result: dict[str, Any]) -> None:
        self._validate_top_level(result)
        self._validate_limits(result)
        self._validate_timestamps(result)
        self._validate_confidence(result)
        self._validate_evidence(result)
        self._validate_no_nan(result)

    def _validate_top_level(self, result: dict[str, Any]) -> None:
        required = {
            "case_id",
            "case_assessment",
            "affected_entities",
            "customer_context",
            "product_context",
            "delivery_analysis",
            "payment_reconciliation",
            "root_cause_analysis",
            "evidence_ids",
            "financial_resolution",
            "resolution_actions",
        }

        if set(result) != required:
            raise ValueError("Output thiếu hoặc thừa top-level field")

        if result["case_assessment"]["case_status"] not in {
            "action_required",
            "no_action",
        }:
            raise ValueError("case_status không hợp lệ")

        if result["financial_resolution"]["currency"] != "BRL":
            raise ValueError("currency phải là BRL")

    def _validate_limits(self, result: dict[str, Any]) -> None:
        entities = result["affected_entities"]
        checks = {
            "order_ids": 5,
            "item_ids": self.MAX_ITEMS,
            "seller_ids": self.MAX_SELLERS,
            "payment_ids": self.MAX_PAYMENTS,
        }

        for field, limit in checks.items():
            if len(entities[field]) > limit:
                raise ValueError(f"affected_entities.{field} vượt giới hạn {limit}")

        if len(result["customer_context"]["related_order_ids"]) > self.MAX_RELATED_ORDERS:
            raise ValueError("related_order_ids vượt giới hạn")

        if len(result["product_context"]["product_ids"]) > self.MAX_PRODUCTS:
            raise ValueError("product_ids vượt giới hạn")

        if len(result["product_context"]["category_names"]) > self.MAX_CATEGORIES:
            raise ValueError("category_names vượt giới hạn")

        if len(result["root_cause_analysis"]["ranked_causes"]) > self.MAX_CAUSES:
            raise ValueError("ranked_causes vượt giới hạn")

        if len(result["root_cause_analysis"]["responsible_parties"]) > self.MAX_PARTIES:
            raise ValueError("responsible_parties vượt giới hạn")

        if len(result["evidence_ids"]) > self.MAX_EVIDENCE:
            raise ValueError("evidence_ids vượt giới hạn")

        if len(result["resolution_actions"]) > self.MAX_ACTIONS:
            raise ValueError("resolution_actions vượt giới hạn")

    def _validate_timestamps(self, result: dict[str, Any]) -> None:
        delivery = result["delivery_analysis"]

        for field in [
            "delivered_at",
            "estimated_delivery_at",
            "carrier_handoff_at",
        ]:
            value = delivery[field]
            if value is not None:
                datetime.strptime(value, "%Y-%m-%d %H:%M:%S")

        for seller in delivery["seller_handoff_analysis"]:
            value = seller["shipping_limit_at"]
            if value is not None:
                datetime.strptime(value, "%Y-%m-%d %H:%M:%S")

    def _validate_confidence(self, result: dict[str, Any]) -> None:
        confidence = result["case_assessment"]["confidence"]
        if not isinstance(confidence, (float, int)) or not 0 <= confidence <= 1:
            raise ValueError("confidence phải thuộc đoạn [0, 1]")

    def _validate_evidence(self, result: dict[str, Any]) -> None:
        allowed_patterns = [
            r"^order:[a-f0-9]{32}$",
            r"^item:[a-f0-9]{32}:\d+$",
            r"^payment:[a-f0-9]{32}:\d+$",
            r"^seller:[a-f0-9]{32}$",
            r"^policy:[A-Z_]+$",
        ]

        for evidence_id in result["evidence_ids"]:
            if not any(re.match(pattern, evidence_id) for pattern in allowed_patterns):
                raise ValueError(f"Evidence ID sai định dạng: {evidence_id}")

        if len(set(result["evidence_ids"])) != len(result["evidence_ids"]):
            raise ValueError("evidence_ids bị trùng")

    def _validate_no_nan(self, value: Any) -> None:
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            raise ValueError("Output chứa NaN hoặc Infinity")

        if isinstance(value, dict):
            for child in value.values():
                self._validate_no_nan(child)

        if isinstance(value, list):
            for child in value:
                self._validate_no_nan(child)