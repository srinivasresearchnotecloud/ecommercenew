import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import datetime
import pandas as pd
import os

st.set_page_config(page_title="Ecommerce App", layout="wide")

if "cart" not in st.session_state:
    st.session_state.cart = []
if "user" not in st.session_state:
    st.session_state.user = None
if "views_local" not in st.session_state:
    st.session_state.views_local = {}
if "adds_local" not in st.session_state:
    st.session_state.adds_local = {}

def get_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(st.secrets["sheets"]["sheet_id"])
    try:
        return sheet.worksheet("views")
    except:
        sheet.add_worksheet(title="views", rows="1000", cols="20")
        return sheet.worksheet("views")

def log_event(user, pid, pname, action):
    try:
        ws = get_sheet()
        t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws.append_row([t, user, pid, pname, action])
    except Exception as e:
        key = f"{pid}_{action}"
        if action == "view":
            st.session_state.views_local[pid] = st.session_state.views_local.get(pid, 0) + 1
        if action == "add_to_cart":
            st.session_state.adds_local[pid] = st.session_state.adds_local.get(pid, 0) + 1

products = [
    {"id": 1, "name": "Laptop", "price": 55000, "category": "Computers", "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/12424c6bdd48450d4060ba93bbb20a532cf46413/laptop1.jpg"},
    {"id": 2, "name": "iPhone 16", "price": 80000, "category": "Phones", "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/12424c6bdd48450d4060ba93bbb20a532cf46413/iphone16.jpg"},
    {"id": 3, "name": "Keyboard", "price": 1500, "category": "Accessories", "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/12424c6bdd48450d4060ba93bbb20a532cf46413/keyboard.jpg"},
    {"id": 4, "name": "Watch", "price": 7000, "category": "Wearables", "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/12424c6bdd48450d4060ba93bbb20a532cf46413/watch1.jpg"},
    {"id": 5, "name": "Headphone", "price": 2500, "category": "Audio", "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/12424c6bdd48450d4060ba93bbb20a532cf46413/headphone.jpg"}
]

local_links_path = "/mnt/data/images link.txt"
if os.path.exists(local_links_path):
    try:
        with open(local_links_path, "r") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        for i, url in enumerate(lines):
            if i < len(products):
                products[i]["img"] = url
    except:
        pass

def add_to_cart(p, qty):
    exists = False
    for it in st.session_state.cart:
        if it["id"] == p["id"]:
            it["qty"] += qty
            exists = True
            break
    if not exists:
        st.session_state.cart.append({"id": p["id"], "name": p["name"], "price": p["price"], "qty": qty, "img": p["img"]})
    user = st.session_state.user if st.session_state.user else "guest"
    log_event(user, p["id"], p["name"], "add_to_cart")

def login():
    st.header("Login")
    u = st.text_input("Username", key="login_user")
    p = st.text_input("Password", type="password", key="login_pass")
    if st.button("Login"):
        if u != "" and p != "":
            st.session_state.user = u
            st.success("Login successful")

def signup():
    st.header("Signup")
    u = st.text_input("Create Username", key="su_user")
    p = st.text_input("Create Password", type="password", key="su_pass")
    if st.button("Create Account"):
        if u != "" and p != "":
            st.session_state.user = u
            st.success("Account created")

def product_page():
    st.header("Products")
    search = st.text_input("Search products", key="search")
    cats = sorted(list({p["category"] for p in products}))
    selected = st.multiselect("Filter by category", options=cats, key="cats")
    sort_opt = st.selectbox("Sort by", ["Default", "Price: Low to High", "Price: High to Low", "Name A-Z", "Name Z-A"], key="sort")
    filtered = products
    if search:
        q = search.lower()
        filtered = [p for p in filtered if q in p["name"].lower() or q in p.get("category","").lower()]
    if selected:
        filtered = [p for p in filtered if p["category"] in selected]
    if sort_opt == "Price: Low to High":
        filtered = sorted(filtered, key=lambda x: x["price"])
    elif sort_opt == "Price: High to Low":
        filtered = sorted(filtered, key=lambda x: -x["price"])
    elif sort_opt == "Name A-Z":
        filtered = sorted(filtered, key=lambda x: x["name"])
    elif sort_opt == "Name Z-A":
        filtered = sorted(filtered, key=lambda x: x["name"], reverse=True)
    cols = st.columns(3)
    for i, p in enumerate(filtered):
        with cols[i % 3]:
            st.image(p["img"], use_column_width=True)
            st.markdown(f"**{p['name']}**")
            st.write("Price:", p["price"])
            st.write("Category:", p["category"])
            qty = st.number_input(f"Qty_{p['id']}", min_value=1, value=1, key=f"qty_{p['id']}")
            if st.button(f"View {p['id']}", key=f"view_{p['id']}"):
                user = st.session_state.user if st.session_state.user else "guest"
                log_event(user, p["id"], p["name"], "view")
                st.success("View logged")
            if st.button(f"Add to Cart {p['id']}", key=f"add_{p['id']}"):
                add_to_cart(p, int(qty))
                st.success("Added to cart")

def show_cart():
    st.header("Cart")
    if len(st.session_state.cart) == 0:
        st.write("Cart is empty")
        return
    df = pd.DataFrame(st.session_state.cart)
    df["subtotal"] = df["price"] * df["qty"]
    st.table(df[["name", "price", "qty", "subtotal"]])
    st.markdown(f"**Total: ₹{df['subtotal'].sum()}**")
    if st.button("Clear Cart"):
        st.session_state.cart = []
        st.experimental_rerun()

def checkout_page():
    st.header("Checkout")
    if len(st.session_state.cart) == 0:
        st.write("Cart empty")
        return
    total = sum([i["price"] * i["qty"] for i in st.session_state.cart])
    st.write("Total amount:", total)
    name = st.text_input("Full name", value=st.session_state.user if st.session_state.user else "")
    address = st.text_area("Shipping address")
    if st.button("Place Order"):
        user = st.session_state.user if st.session_state.user else "guest"
        for item in st.session_state.cart:
            log_event(user, item["id"], item["name"], "order")
        st.success("Order placed (demo)")
        st.session_state.cart = []

def admin_page():
    st.header("Admin Dashboard")
    st.write("Total Products:", len(products))
    st.write("Total Cart Items:", sum([i["qty"] for i in st.session_state.cart]))
    st.write("Logged in user:", st.session_state.user)
    if st.checkbox("Add new product"):
        sku = st.text_input("Name for new product", key="new_name")
        price = st.number_input("Price", min_value=0.0, key="new_price")
        cat = st.text_input("Category", key="new_cat")
        img_file = st.text_input("Image URL (raw github or http)", key="new_img")
        if st.button("Add product now"):
            if sku and img_file:
                new_id = max([p["id"] for p in products]) + 1
                products.append({"id": new_id, "name": sku, "price": price, "category": cat or "Uncategorized", "img": img_file})
                st.success("Product added")
                st.experimental_rerun()

def analytics_page():
    st.header("Analytics Dashboard")
    try:
        ws = get_sheet()
        rows = ws.get_all_records()
        df = pd.DataFrame(rows)
    except:
        df = pd.DataFrame(columns=["timestamp", "user", "product_id", "product_name", "action"])
    if df.empty:
        st.write("No analytics recorded yet")
    else:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        st.subheader("Raw Logs")
        st.dataframe(df.sort_values("timestamp", ascending=False).reset_index(drop=True))
        st.subheader("Aggregations")
        views = df[df["action"] == "view"].groupby("product_name").size().reset_index(name="views")
        adds = df[df["action"] == "add_to_cart"].groupby("product_name").size().reset_index(name="adds")
        orders = df[df["action"] == "order"].groupby("product_name").size().reset_index(name="orders")
        agg = pd.merge(views, adds, on="product_name", how="outer").merge(orders, on="product_name", how="outer").fillna(0)
        st.dataframe(agg)
        st.subheader("Views Chart")
        if not views.empty:
            st.bar_chart(views.set_index("product_name")["views"])
        st.subheader("Adds to Cart Chart")
        if not adds.empty:
            st.bar_chart(adds.set_index("product_name")["adds"])
        st.subheader("User-specific Analytics")
        users = sorted(df["user"].unique().tolist())
        sel_user = st.selectbox("Select user", options=users)
        if sel_user:
            udf = df[df["user"] == sel_user]
            st.write("Events for user:", sel_user)
            st.dataframe(udf.sort_values("timestamp", ascending=False))

menu = ["Home", "Products", "Cart", "Checkout", "Login", "Signup", "Admin", "Analytics"]
choice = st.sidebar.selectbox("Menu", menu)
if choice == "Home":
    st.title("Ecommerce App")
    st.write("Simple Streamlit Ecommerce Demo with analytics")
    if st.button("Log Home Visit"):
        user = st.session_state.user if st.session_state.user else "guest"
        log_event(user, 0, "home", "visit")
        st.success("Home visit logged")
elif choice == "Products":
    product_page()
elif choice == "Cart":
    show_cart()
elif choice == "Checkout":
    checkout_page()
elif choice == "Login":
    login()
elif choice == "Signup":
    signup()
elif choice == "Admin":
    admin_page()
elif choice == "Analytics":
    analytics_page()
