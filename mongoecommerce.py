import streamlit as st
import datetime
import pandas as pd
import numpy as np
import requests
import json
from pymongo import MongoClient

st.set_page_config(
    page_title="E-Commerce App",
    layout="wide"
)


# ============================================================
# MONGODB CONNECTION
# ============================================================

@st.cache_resource
def get_mongo():
    try:
        client = MongoClient(
            st.secrets["MONGO_URI"],
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=10000,
            tls=True
        )

        # Test MongoDB connection
        client.admin.command("ping")

        # Database
        db = client["ecommerce_db"]

        return db

    except Exception as e:
        st.error("MongoDB connection failed.")
        st.error(str(e))
        st.stop()


db = get_mongo()

# Collections
events_col = db["events"]
orders_col = db["orders"]


# ============================================================
# SESSION STATE
# ============================================================

if "cart" not in st.session_state:
    st.session_state.cart = []

if "user" not in st.session_state:
    st.session_state.user = None

if "client_ip" not in st.session_state:
    st.session_state.client_ip = None

if "ml_model" not in st.session_state:
    st.session_state.ml_model = None


# ============================================================
# PRODUCT CATALOG
# ============================================================

PRODUCTS = [
    {
        "id": 1,
        "name": "Laptop",
        "price": 55000,
        "category": "Computers",
        "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/main/laptop1.jpg"
    },
    {
        "id": 2,
        "name": "iPhone 16",
        "price": 80000,
        "category": "Phones",
        "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/main/iphone16.jpg"
    },
    {
        "id": 3,
        "name": "Keyboard",
        "price": 1500,
        "category": "Accessories",
        "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/main/keyboard.jpg"
    },
    {
        "id": 4,
        "name": "Watch",
        "price": 7000,
        "category": "Wearables",
        "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/main/watch1.jpg"
    },
    {
        "id": 5,
        "name": "Headphone",
        "price": 2500,
        "category": "Audio",
        "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/main/headphone.jpg"
    }
]


# ============================================================
# LOG EVENT
# ============================================================

def log_event(user, pid, pname, action, extra=None):

    try:
        events_col.insert_one({
            "timestamp": datetime.datetime.utcnow(),
            "user": user,
            "product_id": pid,
            "product_name": pname,
            "action": action,
            "extra": extra or {}
        })

    except Exception as e:
        st.warning(
            f"Unable to log event: {e}"
        )


# ============================================================
# IP & GEO
# ============================================================

def get_client_ip():

    try:
        return requests.get(
            "https://api.ipify.org?format=json",
            timeout=5
        ).json()["ip"]

    except Exception:
        return None


def get_geo(ip):

    try:
        return requests.get(
            f"https://ipapi.co/{ip}/json/",
            timeout=5
        ).json()

    except Exception:
        return {}


if st.session_state.client_ip is None:
    st.session_state.client_ip = get_client_ip()


# ============================================================
# CART
# ============================================================

def add_to_cart(p, qty):

    for i in st.session_state.cart:

        if i["id"] == p["id"]:

            i["qty"] += qty
            break

    else:

        st.session_state.cart.append({
            **p,
            "qty": qty
        })

    log_event(
        st.session_state.user or "guest",
        p["id"],
        p["name"],
        "add_to_cart"
    )


# ============================================================
# ANALYTICS DASHBOARD
# ============================================================

def analytics_dashboard():

    st.header(
        "📊 E-Commerce Analytics Dashboard"
    )

    # --------------------------------------------------------
    # Load Orders
    # --------------------------------------------------------

    try:

        orders = list(
            orders_col.find(
                {},
                {"_id": 0}
            )
        )

    except Exception as e:

        st.error(
            f"Unable to load orders: {e}"
        )

        orders = []


    # --------------------------------------------------------
    # Load Events
    # --------------------------------------------------------

    try:

        events = list(
            events_col.find(
                {},
                {"_id": 0}
            )
        )

    except Exception as e:

        st.error(
            f"Unable to load events: {e}"
        )

        events = []


    if not orders and not events:

        st.warning(
            "No data available yet"
        )

        return


    orders_df = (
        pd.DataFrame(orders)
        if orders
        else pd.DataFrame()
    )

    events_df = (
        pd.DataFrame(events)
        if events
        else pd.DataFrame()
    )


    # ========================================================
    # KPI METRICS
    # ========================================================

    st.subheader(
        "🔑 Key Performance Indicators"
    )

    total_orders = len(
        orders_df
    )

    if (
        not orders_df.empty
        and "total" in orders_df.columns
    ):

        total_revenue = orders_df[
            "total"
        ].sum()

    else:

        total_revenue = 0


    total_events = len(
        events_df
    )


    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Total Orders",
        total_orders
    )

    col2.metric(
        "Total Revenue (₹)",
        int(total_revenue)
    )

    col3.metric(
        "User Events Logged",
        total_events
    )

    st.divider()


    # ========================================================
    # ORDERS OVER TIME
    # ========================================================

    if not orders_df.empty:

        st.subheader(
            "📈 Orders Over Time"
        )

        if "timestamp" in orders_df.columns:

            orders_df["date"] = (
                pd.to_datetime(
                    orders_df["timestamp"]
                ).dt.date
            )

            daily_orders = (
                orders_df
                .groupby("date")
                .size()
            )

            st.line_chart(
                daily_orders
            )


    # ========================================================
    # TOP SELLING PRODUCTS
    # ========================================================

    if not orders_df.empty:

        st.subheader(
            "🏆 Top Selling Products"
        )

        product_sales = []


        if "items" in orders_df.columns:

            for _, row in orders_df.iterrows():

                for item in row["items"]:

                    product_sales.append({
                        "product": item["name"],
                        "quantity": item["qty"],
                        "revenue": (
                            item["price"]
                            * item["qty"]
                        )
                    })


        if product_sales:

            sales_df = pd.DataFrame(
                product_sales
            )

            top_products = (
                sales_df
                .groupby("product")["quantity"]
                .sum()
                .sort_values(
                    ascending=False
                )
            )

            st.bar_chart(
                top_products
            )


    # ========================================================
    # MOST VIEWED PRODUCTS
    # ========================================================

    if not events_df.empty:

        st.subheader(
            "👀 Most Viewed Products"
        )

        if "action" in events_df.columns:

            views_df = events_df[
                events_df["action"] == "view"
            ]

            if not views_df.empty:

                view_counts = (
                    views_df[
                        "product_name"
                    ].value_counts()
                )

                st.bar_chart(
                    view_counts
                )


    # ========================================================
    # USER ACTIVITY DISTRIBUTION
    # ========================================================

    if not events_df.empty:

        st.subheader(
            "🧭 User Activity Distribution"
        )

        if "action" in events_df.columns:

            activity_counts = (
                events_df[
                    "action"
                ].value_counts()
            )

            st.bar_chart(
                activity_counts
            )


# ============================================================
# PRODUCT PAGE
# ============================================================

def product_page():

    st.header(
        "Products"
    )

    cols = st.columns(3)

    for i, p in enumerate(PRODUCTS):

        with cols[i % 3]:

            # IMPORTANT:
            # Updated from use_column_width=True
            # to use_container_width=True

            st.image(
                p["img"],
                use_container_width=True
            )

            st.write(
                p["name"],
                "₹",
                p["price"]
            )

            qty = st.number_input(
                f"Qty_{p['id']}",
                min_value=1,
                value=1,
                key=f"qty_{p['id']}"
            )

            if st.button(
                f"Add {p['id']}",
                key=f"add_{p['id']}"
            ):

                add_to_cart(
                    p,
                    int(qty)
                )

                st.success(
                    "Added to cart"
                )

                log_event(
                    st.session_state.user
                    or "guest",
                    p["id"],
                    p["name"],
                    "view"
                )


# ============================================================
# SHOW CART
# ============================================================

def show_cart():

    st.header(
        "Cart"
    )

    if not st.session_state.cart:

        st.info(
            "Cart empty"
        )

        return


    df = pd.DataFrame(
        st.session_state.cart
    )

    df["subtotal"] = (
        df["price"]
        * df["qty"]
    )

    st.table(
        df
    )

    st.write(
        "Total:",
        df["subtotal"].sum()
    )


# ============================================================
# CHECKOUT
# ============================================================

def checkout():

    st.header(
        "Checkout"
    )

    if not st.session_state.cart:

        st.info(
            "Cart empty"
        )

        return


    address = st.text_area(
        "Address"
    )


    if st.button(
        "Place Order"
    ):

        try:

            total = sum(
                i["price"] * i["qty"]
                for i in st.session_state.cart
            )


            orders_col.insert_one({

                "user":
                    st.session_state.user
                    or "guest",

                "items":
                    st.session_state.cart,

                "total":
                    total,

                "address":
                    address,

                "timestamp":
                    datetime.datetime.utcnow()
            })


            # Log order events

            for i in st.session_state.cart:

                log_event(
                    st.session_state.user
                    or "guest",

                    i["id"],

                    i["name"],

                    "order"
                )


            st.session_state.cart = []


            st.success(
                "Order placed successfully"
            )


        except Exception as e:

            st.error(
                f"Unable to place order: {e}"
            )


# ============================================================
# ANALYTICS
# ============================================================

def analytics():

    st.header(
        "Analytics"
    )

    try:

        data = list(
            events_col.find(
                {},
                {"_id": 0}
            )
        )

    except Exception as e:

        st.error(
            f"Unable to load analytics: {e}"
        )

        return


    if not data:

        st.info(
            "No data yet"
        )

        return


    df = pd.DataFrame(
        data
    )


    if "timestamp" in df.columns:

        df["timestamp"] = pd.to_datetime(
            df["timestamp"]
        )

        df = df.sort_values(
            "timestamp",
            ascending=False
        )


    st.dataframe(
        df,
        use_container_width=True
    )


    if "action" in df.columns:

        st.bar_chart(
            df["action"].value_counts()
        )


# ============================================================
# NAVIGATION
# ============================================================

st.sidebar.title(
    "Navigation"
)


choice = st.sidebar.radio(
    "Go to",
    [
        "Home",
        "Products",
        "Cart",
        "Analytics"
    ]
)


# ============================================================
# PAGE SELECTION
# ============================================================

if choice == "Home":

    st.header(
        "Welcome to the E-Commerce App"
    )


elif choice == "Products":

    product_page()


elif choice == "Cart":

    show_cart()
    checkout()


elif choice == "Analytics":

    analytics_dashboard()
