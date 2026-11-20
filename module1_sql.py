from pathlib import Path
import sqlite3
import pandas as pd


CREATE_ORDERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    city TEXT NOT NULL,
    order_date TEXT NOT NULL,
    total_amount REAL NOT NULL,
    status TEXT NOT NULL
);
"""

INSERT_ORDERS_SQL = """
INSERT OR REPLACE INTO orders (
    order_id,
    customer_id,
    customer_name,
    city,
    order_date,
    total_amount,
    status
) VALUES (?, ?, ?, ?, ?, ?, ?);
"""

TOP_CUSTOMERS_SQL = """
SELECT
    customer_id,
    customer_name,
    city,
    COUNT(order_id) AS orders_count,
    SUM(total_amount) AS total_spent
FROM orders
WHERE status = ? AND city = ?
GROUP BY customer_id, customer_name, city
ORDER BY total_spent DESC
LIMIT 5;
"""


def init_database(conn: sqlite3.Connection) -> None:
    with conn:
        conn.execute(CREATE_ORDERS_TABLE_SQL)


def load_orders_dataframe(source_path: Path) -> pd.DataFrame:
    suffix = source_path.suffix.lower()
    if suffix == ".xlsx":
        return pd.read_excel(source_path)
    if suffix == ".csv":
        return pd.read_csv(source_path)
    raise ValueError(f"Непідтримуваний формат файлу: {source_path.suffix}")


def import_orders_from_file(conn: sqlite3.Connection, source_path: Path) -> int:
    df_orders = load_orders_dataframe(source_path).copy()
    df_orders["total_amount_num"] = pd.to_numeric(
        df_orders["total_amount"], errors="coerce"
    ).fillna(0.0)

    rows: list[tuple[str, str, str, str, str, float, str]] = [
        (
            str(row.order_id).strip(),
            str(row.customer_id).strip(),
            str(row.customer_name).strip(),
            str(row.city).strip(),
            str(row.order_date)[:10].strip(),
            float(row.total_amount_num),
            str(row.status).strip(),
        )
        for row in df_orders.itertuples(index=False)
    ]

    with conn:
        conn.executemany(INSERT_ORDERS_SQL, rows)

    return len(rows)


def build_top_customers_report(
    conn: sqlite3.Connection,
    city: str = "Київ",
    status: str = "completed",
) -> pd.DataFrame:
    df_report = pd.read_sql_query(
        TOP_CUSTOMERS_SQL,
        conn,
        params=(status, city),
    )

    if not df_report.empty:
        df_report["avg_check"] = (
            df_report["total_spent"] / df_report["orders_count"]
        ).round(2)
    else:
        df_report["avg_check"] = pd.Series(dtype="float64")

    return df_report

def save_and_verify_report(
    conn: sqlite3.Connection,
    df_report: pd.DataFrame,
    table_name: str = "top_customers_report",
) -> pd.DataFrame:
    df_report.to_sql(
        name=table_name,
        con=conn,
        if_exists="replace",
        index=False,
    )
    return pd.read_sql_query(f"SELECT * FROM {table_name};", conn)

def main() -> None:
    base_dir = Path(__file__).resolve().parent
    xlsx_path = base_dir / "module1_ecommerce_orders.xlsx"
    csv_path = base_dir / "module1_ecommerce_orders.csv"
    db_path = base_dir / "ecommerce.db"

    if xlsx_path.exists():
        input_path = xlsx_path
    elif csv_path.exists():
        input_path = csv_path
    else:
        raise FileNotFoundError(
            f"Не знайдено вхідний файл у {base_dir} (.xlsx або .csv)"
        )

    with sqlite3.connect(db_path) as conn:
        init_database(conn)
        imported_count = import_orders_from_file(conn, input_path)

        total_in_db = conn.execute("SELECT COUNT(*) FROM orders;").fetchone()[0]
        print(f"Імпортовано рядків із файлу ({input_path.name}): {imported_count}")
        print(f"Усього записів у таблиці orders: {total_in_db}\n")

        top_customers = build_top_customers_report(
            conn=conn,
            city="Київ",
            status="completed",
        )
        verified_df = save_and_verify_report(
            conn=conn,
            df_report=top_customers,
            table_name="top_customers_report",
        )

        print("Контрольна вибірка з таблиці top_customers_report:")
        print(verified_df.head().to_string(index=False))


if __name__ == "__main__":
    main()