import streamlit as st
import pandas as pd

st.set_page_config(page_title="Online Shopping App", layout="wide")

st.title("🛒 Online Shopping Application")

products = [
    {"Product": "Smartphone", "Category": "Electronics", "Price": 15000},
    {"Product": "Laptop", "Category": "Electronics", "Price": 55000},
    {"Product": "T-Shirt", "Category": "Clothing", "Price": 800},
    {"Product": "Shoes", "Category": "Clothing", "Price": 3000},
]

df = pd.DataFrame(products)

if "cart" not in st.session_state:
    st.session_state.cart = []

st.sidebar.header("Filter")
category = st.sidebar.selectbox("Category", ["All"] + list(df.Category.unique()))

if category != "All":
    df = df[df.Category == category]

for i, row in df.iterrows():
    col1, col2 = st.columns(2)
    col1.write(f"**{row.Product}**")
    col2.write(f"₹{row.Price}")
    if st.button("Add to Cart", key=i):
        st.session_state.cart.append(row)

st.subheader("🛍 Shopping Cart")
if st.session_state.cart:
    cart_df = pd.DataFrame(st.session_state.cart)
    st.table(cart_df)
    st.write("Total Amount: ₹", cart_df.Price.sum())
else:
    st.write("Cart is empty")
