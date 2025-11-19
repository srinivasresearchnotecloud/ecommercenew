import streamlit as st

st.set_page_config(page_title="Ecommerce App", layout="wide")

if "cart" not in st.session_state:
    st.session_state.cart = []
if "user" not in st.session_state:
    st.session_state.user = None

products = [
    {"id": 1, "name": "Laptop", "price": 55000, "img": "https://via.placeholder.com/200"},
    {"id": 2, "name": "Phone", "price": 30000, "img": "https://via.placeholder.com/200"},
    {"id": 3, "name": "Watch", "price": 7000, "img": "https://via.placeholder.com/200"},
    {"id": 4, "name": "Headphones", "price": 2500, "img": "https://via.placeholder.com/200"},
    {"id": 5, "name": "Keyboard", "price": 1200, "img": "https://via.placeholder.com/200"}
]

def add_to_cart(p):
    st.session_state.cart.append(p)

def show_cart():
    st.title("Cart")
    total = 0
    if len(st.session_state.cart) == 0:
        st.write("Cart is empty")
        return
    for item in st.session_state.cart:
        st.image(item["img"], width=100)
        st.write(item["name"], item["price"])
        total += item["price"]
    st.write("Total:", total)

def login():
    st.title("Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        if u != "" and p != "":
            st.session_state.user = u
            st.success("Login successful")

def signup():
    st.title("Signup")
    u = st.text_input("Create Username")
    p = st.text_input("Create Password", type="password")
    if st.button("Create Account"):
        if u != "" and p != "":
            st.session_state.user = u
            st.success("Account created")

def product_page():
    st.title("Products")
    cols = st.columns(3)
    for i, p in enumerate(products):
        with cols[i % 3]:
            st.image(p["img"])
            st.write(p["name"])
            st.write("Price:", p["price"])
            if st.button("Add to Cart " + str(p["id"])):
                add_to_cart(p)
                st.success("Added")

def checkout_page():
    st.title("Checkout")
    if len(st.session_state.cart) == 0:
        st.write("Cart empty")
        return
    total = sum([i["price"] for i in st.session_state.cart])
    st.write("Total amount:", total)
    if st.button("Pay Now"):
        st.success("Payment successful (demo)")

def admin_page():
    st.title("Admin Dashboard")
    st.write("Total Products:", len(products))
    st.write("Total Cart Items:", len(st.session_state.cart))
    st.write("Logged in user:", st.session_state.user)

menu = ["Home", "Products", "Cart", "Checkout", "Login", "Signup", "Admin"]
choice = st.sidebar.selectbox("Menu", menu)

if choice == "Home":
    st.title("Ecommerce App")
    st.write("Simple Streamlit Ecommerce Demo")
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
