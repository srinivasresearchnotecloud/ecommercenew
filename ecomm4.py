import streamlit as st

st.set_page_config(page_title="Ecommerce App", layout="wide")

if "cart" not in st.session_state:
    st.session_state.cart = []
if "user" not in st.session_state:
    st.session_state.user = None

products = [
    {"id": 1, "name": "Laptop", "price": 55000,
     "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/12424c6bdd48450d4060ba93bbb20a532cf46413/laptop1.jpg"},
    {"id": 2, "name": "iPhone 16", "price": 80000,
     "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/12424c6bdd48450d4060ba93bbb20a532cf46413/iphone16.jpg"},
    {"id": 3, "name": "Keyboard", "price": 1500,
     "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/12424c6bdd48450d4060ba93bbb20a532cf46413/keyboard.jpg"},
    {"id": 4, "name": "Watch", "price": 7000,
     "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/12424c6bdd48450d4060ba93bbb20a532cf46413/watch1.jpg"},
    {"id": 5, "name": "Headphone", "price": 2500,
     "img": "https://raw.githubusercontent.com/srinivasresearchnotecloud/ecommercenew/12424c6bdd48450d4060ba93bbb20a532cf46413/headphone.jpg"}
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
