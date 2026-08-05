from dataclasses import dataclass


@dataclass
class CustomerHandoff:
    customer_unique_id: str
    related_order_ids: list[str]


@dataclass
class OrderProductHandoff:
    item_ids: list[str]
    seller_ids: list[str]
    product_ids: list[str]
    category_names: list[str]
    item_count: int
    seller_count: int
    category_count: int
    item_total_brl: float
    freight_total_brl: float
    has_items: bool


@dataclass
class PaymentHandoff:
    payment_ids: list[str]
    payment_types: list[str]
    payment_count: int
    payment_total_brl: float
    expected_total_brl: float | None
    difference_brl: float | None
    reconciled: bool | None

@dataclass
class SellerHandoff:
    seller_id: str
    shipping_limit_at: str | None
    handoff_variance_hours: float | None
    late_handoff: bool

@dataclass
class DeliveryHandoff:
    delivered_at: str | None
    estimated_delivery_at: str | None
    carrier_handoff_at: str | None
    delivery_variance_hours: float | None
    seller_handoff_analysis: list[SellerHandoff]
    late_handoff_seller_ids: list[str]

@dataclass
class RankedCause:
    cause_code: str
    rank: int

@dataclass
class ResponsibleParty:
    party_type: str
    party_id: str

@dataclass
class PolicyDecision:
    primary_issue: str
    secondary_issues: list[str]
    case_status: str
    confidence: float
    ranked_causes: list[RankedCause]
    responsible_parties: list[ResponsibleParty]
    recommended_refund_brl: float
    resolution_actions: list[str]