from src.data_repository import OrderBundle
from src.models import (
    CustomerHandoff,
    DeliveryHandoff,
    OrderProductHandoff,
    PaymentHandoff,
    PolicyDecision,
    RankedCause,
    ResponsibleParty,
)

class PolicyAgent:
    def analyze(
        self,
        bundle: OrderBundle,
        customer: CustomerHandoff,
        order_product: OrderProductHandoff,
        payment: PaymentHandoff,
        delivery: DeliveryHandoff,
    ) -> PolicyDecision:
        secondary_issues = self._find_secondary_issues(
            customer=customer,
            order_product=order_product,
            payment=payment,
        )

        primary_issue, cause_code, parties, refund = self._find_primary_issue(
            bundle=bundle,
            order_product=order_product,
            payment=payment,
            delivery=delivery,
        )

        case_status = (
            "action_required"
            if primary_issue
            in {
                "canceled_order_paid",
                "unavailable_order_paid",
                "late_delivery_seller",
                "late_delivery_logistics",
            }
            else "no_action"
        )

        actions = self._build_actions(
            primary_issue=primary_issue,
            secondary_issues=secondary_issues,
            case_status=case_status,
        )

        return PolicyDecision(
            primary_issue=primary_issue,
            secondary_issues=secondary_issues,
            case_status=case_status,
            # Mọi kết luận phía trên đều được dựng trực tiếp từ CSV.
            confidence=0.99,
            ranked_causes=[RankedCause(cause_code=cause_code, rank=1)],
            responsible_parties=parties,
            recommended_refund_brl=round(refund, 2),
            resolution_actions=actions,
        )

    def _find_secondary_issues(
        self,
        customer: CustomerHandoff,
        order_product: OrderProductHandoff,
        payment: PaymentHandoff,
    ) -> list[str]:
        issues = []

        # Thứ tự này bắt buộc theo README.
        if order_product.item_count >= 2:
            issues.append("multi_item_order")

        if order_product.seller_count >= 2:
            issues.append("multi_seller_order")

        if payment.payment_count >= 2:
            issues.append("split_payment")

        if len(customer.related_order_ids) >= 1:
            issues.append("repeat_customer")

        if order_product.category_count >= 2:
            issues.append("multiple_categories")

        return issues

    def _find_primary_issue(
        self,
        bundle: OrderBundle,
        order_product: OrderProductHandoff,
        payment: PaymentHandoff,
        delivery: DeliveryHandoff,
    ) -> tuple[str, str, list[ResponsibleParty], float]:
        order_status = str(bundle.order["order_status"])
        payment_total = payment.payment_total_brl

        delivery_is_late = (
            delivery.delivery_variance_hours is not None
            and delivery.delivery_variance_hours > 0
        )

        # Quan trọng: thứ tự if bên dưới chính là thứ tự ưu tiên EC_POLICY_V2.

        if order_status == "canceled" and payment_total > 0:
            return (
                "canceled_order_paid",
                "ORDER_CANCELED_AFTER_PAYMENT",
                [ResponsibleParty("platform", "OLIST_PLATFORM")],
                payment_total,
            )

        if order_status == "unavailable" and payment_total > 0:
            return (
                "unavailable_order_paid",
                "ORDER_UNAVAILABLE_AFTER_PAYMENT",
                [ResponsibleParty("platform", "OLIST_PLATFORM")],
                payment_total,
            )

        if delivery_is_late and delivery.late_handoff_seller_ids:
            parties = [
                ResponsibleParty("seller", seller_id)
                for seller_id in delivery.late_handoff_seller_ids
            ]
            return (
                "late_delivery_seller",
                "SELLER_HANDOFF_AFTER_LIMIT",
                parties,
                order_product.freight_total_brl,
            )

        if delivery_is_late:
            return (
                "late_delivery_logistics",
                "CARRIER_DELIVERED_AFTER_ESTIMATE",
                [
                    ResponsibleParty(
                        "logistics_provider",
                        "LOGISTICS_PROVIDER",
                    )
                ],
                order_product.freight_total_brl,
            )

        if payment.payment_count >= 2 and payment.reconciled is True:
            return (
                "valid_split_payment",
                "MULTIPLE_PAYMENTS_RECONCILED",
                [],
                0.0,
            )

        if (
            delivery.delivery_variance_hours is not None
            and delivery.delivery_variance_hours <= 0
            and payment.reconciled is True
        ):
            return (
                "unsupported_late_claim",
                "DELIVERY_WITHIN_ESTIMATE",
                [],
                0.0,
            )

        # Không tự gán một issue khi dữ liệu không thỏa bất kỳ rule nào.
        # Nếu gặp lỗi này, kiểm tra input/policy thay vì bịa kết quả.
        raise ValueError(
            f"Order {bundle.order['order_id']} không khớp rule EC_POLICY_V2"
        )

    def _build_actions(
        self,
        primary_issue: str,
        secondary_issues: list[str],
        case_status: str,
    ) -> list[str]:
        primary_action = {
            "canceled_order_paid": "issue_full_refund",
            "unavailable_order_paid": "issue_full_refund",
            "late_delivery_seller": "refund_freight",
            "late_delivery_logistics": "refund_freight",
            "valid_split_payment": "explain_valid_split_payment",
            "unsupported_late_claim": "reject_late_refund",
        }[primary_issue]

        actions = [primary_action]

        # Thứ tự supplementary action cũng bắt buộc theo README.
        if primary_issue == "late_delivery_seller":
            actions.append("review_seller_handoff")
        elif primary_issue == "late_delivery_logistics":
            actions.append("review_carrier_delay")

        if case_status == "action_required":
            actions.append("verify_refund_completion")

        if "multi_seller_order" in secondary_issues:
            actions.append("coordinate_multi_seller_case")

        if (
            "split_payment" in secondary_issues
            and primary_issue != "valid_split_payment"
        ):
            actions.append("verify_payment_allocation")

        return actions