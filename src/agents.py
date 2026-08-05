import pandas as pd

from src.data_repository import OrderBundle
from src.models import (
    CustomerHandoff,
    DeliveryHandoff,
    OrderProductHandoff,
    PaymentHandoff,
    SellerHandoff,
)


def _stable_unique(values) -> list[str]:
    """Loại trùng nhưng giữ thứ tự dữ liệu nguồn."""
    return list(dict.fromkeys(str(value) for value in values if pd.notna(value)))


def _round_brl(value: float) -> float:
    rounded = round(float(value), 2)
    return 0.0 if rounded == -0.0 else rounded


def _timestamp_to_string(value) -> str | None:
    if pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")


class CustomerAgent:
    def analyze(self, bundle: OrderBundle) -> CustomerHandoff:
        return CustomerHandoff(
            customer_unique_id=str(bundle.customer["customer_unique_id"]),
            related_order_ids=bundle.related_orders["order_id"].astype(str).tolist(),
        )


class OrderProductAgent:
    def analyze(self, bundle: OrderBundle) -> OrderProductHandoff:
        items = bundle.items

        item_ids = [
            f"{row.order_id}:{int(row.order_item_id)}"
            for row in items.itertuples(index=False)
        ]

        seller_ids = _stable_unique(items["seller_id"]) if not items.empty else []
        product_ids = _stable_unique(items["product_id"]) if not items.empty else []

        category_names = []
        if not bundle.products.empty:
            category_names = _stable_unique(
                bundle.products["product_category_name"]
            )

        item_total = _round_brl(items["price"].sum()) if not items.empty else None
        freight_total = (
            _round_brl(items["freight_value"].sum()) if not items.empty else None
        )

        return OrderProductHandoff(
            item_ids=item_ids,
            seller_ids=seller_ids,
            product_ids=product_ids,
            category_names=category_names,
            item_count=len(items),
            seller_count=len(seller_ids),
            category_count=len(category_names),
            item_total_brl=item_total,
            freight_total_brl=freight_total,
            has_items=not items.empty,
        )


class PaymentAgent:
    def analyze(
        self,
        bundle: OrderBundle,
        order_product: OrderProductHandoff,
    ) -> PaymentHandoff:
        payments = bundle.payments

        payment_ids = [
            f"{row.order_id}:{int(row.payment_sequential)}"
            for row in payments.itertuples(index=False)
        ]
        payment_types = (
            _stable_unique(payments["payment_type"]) if not payments.empty else []
        )
        payment_total = _round_brl(payments["payment_value"].sum())

        # Đề bài yêu cầu 3 trường này là null khi order không có item.
        if not order_product.has_items:
            expected_total = None
            difference = None
            reconciled = None
        else:
            expected_total = _round_brl(
                order_product.item_total_brl + order_product.freight_total_brl
            )
            difference = _round_brl(payment_total - expected_total)
            reconciled = abs(difference) <= 0.10

        return PaymentHandoff(
            payment_ids=payment_ids,
            payment_types=payment_types,
            payment_count=len(payments),
            payment_total_brl=payment_total,
            expected_total_brl=expected_total,
            difference_brl=difference,
            reconciled=reconciled,
        )


class DeliveryAgent:
    def analyze(self, bundle: OrderBundle) -> DeliveryHandoff:
        order = bundle.order

        delivered_at = order["order_delivered_customer_date"]
        estimated_at = order["order_estimated_delivery_date"]
        carrier_handoff_at = order["order_delivered_carrier_date"]

        if pd.isna(delivered_at) or pd.isna(estimated_at):
            delivery_variance_hours = None
        else:
            delivery_variance_hours = _round_brl(
                (delivered_at - estimated_at).total_seconds() / 3600
            )

        seller_handoffs = []
        # Carrier chua nhan hang -> khong ton tai su kien handoff de phan tich.
        if not bundle.items.empty and not pd.isna(carrier_handoff_at):
            # Mỗi seller dùng shipping_limit_date sớm nhất của chính seller đó.
            for seller_id, seller_items in bundle.items.groupby(
                "seller_id", sort=False
            ):
                shipping_limit = seller_items["shipping_limit_date"].min()

                if pd.isna(carrier_handoff_at) or pd.isna(shipping_limit):
                    variance = None
                    late_handoff = False
                else:
                    variance = _round_brl(
                        (carrier_handoff_at - shipping_limit).total_seconds() / 3600
                    )
                    late_handoff = variance > 0

                seller_handoffs.append(
                    SellerHandoff(
                        seller_id=str(seller_id),
                        shipping_limit_at=_timestamp_to_string(shipping_limit),
                        handoff_variance_hours=variance,
                        late_handoff=late_handoff,
                    )
                )

        late_seller_ids = [
            handoff.seller_id
            for handoff in seller_handoffs
            if handoff.late_handoff
        ]

        return DeliveryHandoff(
            delivered_at=_timestamp_to_string(delivered_at),
            estimated_delivery_at=_timestamp_to_string(estimated_at),
            carrier_handoff_at=_timestamp_to_string(carrier_handoff_at),
            delivery_variance_hours=delivery_variance_hours,
            seller_handoff_analysis=seller_handoffs,
            late_handoff_seller_ids=late_seller_ids,
        )