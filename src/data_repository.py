from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class OrderBundle:
    """Toàn bộ dữ liệu nguồn của một claimed order, giữ nguyên thứ tự CSV."""

    order: pd.Series
    customer: pd.Series
    items: pd.DataFrame
    payments: pd.DataFrame
    products: pd.DataFrame
    sellers: pd.DataFrame
    related_orders: pd.DataFrame


class DataRepository:
    def __init__(self, data_dir: str | Path = "data") -> None:
        data_dir = Path(data_dir)

        self.customers = pd.read_csv(data_dir / "olist_customers_dataset.csv")
        self.orders = pd.read_csv(
            data_dir / "olist_orders_dataset.csv",
            parse_dates=[
                "order_purchase_timestamp",
                "order_approved_at",
                "order_delivered_carrier_date",
                "order_delivered_customer_date",
                "order_estimated_delivery_date",
            ],
        )
        self.items = pd.read_csv(
            data_dir / "olist_order_items_dataset.csv",
            parse_dates=["shipping_limit_date"],
        )
        self.payments = pd.read_csv(
            data_dir / "olist_order_payments_dataset.csv"
        )
        self.products = pd.read_csv(data_dir / "olist_products_dataset.csv")
        category_translation = pd.read_csv(
            data_dir / "product_category_name_translation.csv"
        )
        self.products = self.products.merge(
            category_translation,
            on="product_category_name",
            how="left",
            sort=False,
        )
        self.sellers = pd.read_csv(data_dir / "olist_sellers_dataset.csv")

        # Hai bảng này chưa cần cho EC_POLICY_V2.
        # Không tải geolocation vì hơn 1 triệu dòng và không ảnh hưởng kết luận.
        # Không tải reviews vì không có rule nào dùng review.

        self._customer_by_id = self.customers.set_index("customer_id")
        self._product_by_id = self.products.set_index("product_id")
        self._seller_by_id = self.sellers.set_index("seller_id")

        self._orders_with_customer = self.orders.merge(
            self.customers[["customer_id", "customer_unique_id"]],
            on="customer_id",
            how="left",
            sort=False,
        )

    def get_order_bundle(self, order_id: str) -> OrderBundle:
        order_rows = self.orders.loc[
            self.orders["order_id"].eq(order_id)
        ]

        if len(order_rows) != 1:
            raise KeyError(f"Không tìm thấy order_id hợp lệ: {order_id}")

        order = order_rows.iloc[0].copy()

        try:
            customer = self._customer_by_id.loc[order["customer_id"]].copy()
        except KeyError as exc:
            raise ValueError(
                f"Order {order_id} có customer_id không tồn tại"
            ) from exc

        # Chuẩn hóa thứ tự nguồn theo khóa nghiệp vụ: item theo order_item_id,
        # payment theo payment_sequential. Thứ tự dòng trong CSV gốc không ổn
        # định (một số order có payment row nằm đảo 2,1 hoặc 3,1,2), trong khi
        # schema mẫu của đề luôn liệt kê payment:...:1 trước payment:...:2.
        items = (
            self.items.loc[self.items["order_id"].eq(order_id)]
            .sort_values("order_item_id", kind="stable")
            .copy()
        )

        payments = (
            self.payments.loc[self.payments["order_id"].eq(order_id)]
            .sort_values("payment_sequential", kind="stable")
            .copy()
        )

        # drop_duplicates giữ thứ tự product/seller xuất hiện lần đầu trong item CSV.
        product_ids = items["product_id"].drop_duplicates().tolist()
        seller_ids = items["seller_id"].drop_duplicates().tolist()

        products = self._product_by_id.reindex(product_ids).reset_index()
        sellers = self._seller_by_id.reindex(seller_ids).reset_index()

        related_orders = self._orders_with_customer.loc[
            self._orders_with_customer["customer_unique_id"].eq(
                customer["customer_unique_id"]
            )
            & self._orders_with_customer["order_id"].ne(order_id)
        ].copy()

        return OrderBundle(
            order=order,
            customer=customer,
            items=items,
            payments=payments,
            products=products,
            sellers=sellers,
            related_orders=related_orders,
        )
