import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime
from pymongo import MongoClient

# =====================================
# PAGE CONFIG
# =====================================
st.set_page_config(page_title="E-Commerce App", layout="wide")

# =====================================
# MONGODB CONNECTION
# =====================================
@st.cache_resource
def get_mongo_db():
    client = MongoClient(st.secrets["MONGO_URI"])
    return client["ecommerce_db"]

db = get_mongo_db()
events_col = db["events"]
orders_col = db["orders"]

# =====================================
# SESSION STATE
# =====================================
if "cart" not in st.session_state:
    st.session_state.cart = []
if "user" not in st.session_state:
    st.session_state.user = "guest"
if "client_ip" not in st.session_state:
    st.session_state.client_ip = None

# =====================================
# PRODUCT CATALOG
# =====================================
PRODUCTS = [
    {"id": 1, "name": "Laptop", "price": 55000, "category": "Computers",
     "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/main/laptop1.jpg"},
    {"id": 2, "name": "iPhone 16", "price": 80000, "category": "Phones",
     "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/main/iphone16.jpg"},
    {"id": 3, "name": "Keyboard", "price": 1500, "category": "Accessories",
     "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/main/keyboard.jpg"},
    {"id": 4, "name": "Watch", "price": 7000, "category": "Wearables",
     "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/main/watch1.jpg"},
    {"id": 5, "name": "Headphone", "price": 2500, "category": "Audio",
     "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/main/headphone.jpg"},
]

# =====================================
# HELPER FUNCTIONS
# =====================================
def get_client_ip():
    try:
        r = requests.get("https://api.ipify.org?format=json", timeout=5)
        return r.json().get("ip")
    except Exception:
        return None

def log_event(user, pid, pname, action, extra=None):
    doc = {
        "timestamp": datetime.datetime.utcnow(),
        "user": user,
        "product_id": pid,
        "product_name": pname,
        "action": action,
        "extra": extra or {},
    }
    events_col.insert_one(doc)

# Capture IP once
if st.session_state.client_ip is None:
    st.session_state.client_ip = get_client_ip()

# =====================================
# CART FUNCTIONS
# =====================================
def add_to_cart(product, qty):
    for item in st.session_state.cart:
        if item["id"] == product["id"]:
            item["qty"] += qty
            break
    else:
        st.session_state.cart.append({**product, "qty": qty})

    log_event(st.session_state.user, product["id"], product["name"], "add_to_cart")

# =====================================
# UI PAGES
# =====================================
def home():
    log_event(st.session_state.user, "-", "-", "home_view")
    st.title("🛒 Welcome to the E-Commerce App")
    st.write("Cloud-based online shopping application using Streamlit and MongoDB Atlas.")

def products_page():
    log_event(st.session_state.user, "-", "-", "products_view")
    st.header("Products")

    search = st.text_input("Search products")
    categories = sorted({p["category"] for p in PRODUCTS})
    selected = st.multiselect("Filter by category", categories)

    prods = PRODUCTS
    if search:
        prods = [p for p in prods if search.lower() in p["name"].lower()]
    if selected:
        prods = [p for p in prods if p["category"] in selected]

    cols = st.columns(3)
    for i, p in enumerate(prods):
        with cols[i % 3]:
            st.image(p["img"], use_column_width=True)
            st.subheader(p["name"])
            st.write("₹", p["price"])
            qty = st.number_input(f"Qty_{p['id']}", min_value=1, value=1)
            if st.button(f"Add to Cart {p['id']}"):
                add_to_cart(p, int(qty))
                st.success("Added to cart")
                log_event(st.session_state.user, p["id"], p["name"], "view")

def cart_page():
    log_event(st.session_state.user, "-", "-", "cart_view")
    st.header("Cart")

    if not st.session_state.cart:
        st.info("Cart is empty")
        return

    df = pd.DataFrame(st.session_state.cart)
    df["subtotal"] = df["price"] * df["qty"]
    st.table(df)
    st.subheader(f"Total: ₹{df['subtotal'].sum()}")

def checkout_page():
    st.header("Checkout")

    if not st.session_state.cart:
        st.info("Cart empty")
        return

    name = st.text_input("Name")
    address = st.text_area("Address")

    if st.button("Place Order"):
        order_doc = {
            "user": st.session_state.user,
            "items": st.session_state.cart,
            "total": sum(i["price"] * i["qty"] for i in st.session_state.cart),
            "address": address,
            "timestamp": datetime.datetime.utcnow(),
        }
        orders_col.insert_one(order_doc)

        for i in st.session_state.cart:
            log_event(st.session_state.user, i["id"], i["name"], "order")

        st.session_state.cart = []
        st.success("✅ Order placed successfully")

def analytics_page():
    log_event(st.session_state.user, "-", "-", "analytics_view")
    st.header("Analytics Dashboard")

    data = list(events_col.find({}, {"_id": 0}))
    if not data:
        st.info("No analytics data yet")
        return

    df = pd.DataFrame(data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    st.subheader("Event Logs")
    st.dataframe(df.sort_values("timestamp", ascending=False))

    st.subheader("Events by Type")
    st.bar_chart(df["action"].value_counts())

    st.subheader("Top Products (Views)")
    views = df[df["action"] == "view"]
    if not views.empty:
        st.bar_chart(views["product_name"].value_counts())

# =====================================
# NAVIGATION
# =====================================
st.sidebar.title("Navigation")
choice = st.sidebar.radio("Go to", ["Home", "Products", "Cart", "Checkout", "Analytics"])

if choice == "Home":
    home()
elif choice == "Products":
    products_page()
elif choice == "Cart":
    cart_page()
elif choice == "Checkout":
    checkout_page()
elif choice == "Analytics":
    analytics_page()
