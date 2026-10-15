import streamlit as st

from utils.auth import can_input_data, current_user

user = current_user()

if user is None:
    pg = st.navigation(
        [st.Page("views/login.py", title="Masuk")],
        position="hidden",
    )
else:
    halaman = [
        st.Page("pages/1_Welcome.py", title="Welcome", icon="👋", default=True),
        st.Page("pages/2_Dashboard_Overall.py", title="Dashboard Overall", icon="📊"),
        st.Page("pages/7_Dashboard_Income.py", title="Dashboard Income", icon="💵"),
        st.Page("pages/8_Dashboard_Expense.py", title="Dashboard Expense", icon="💸"),
        st.Page("pages/9_Dashboard_Investment.py", title="Dashboard Investment", icon="🏦"),
    ]
    if can_input_data(user):
        halaman.append(
            st.Page("pages/3_Input_Data_Master.py", title="Input Data Master", icon="🗂️")
        )
        halaman.append(
            st.Page("pages/4_Input_Data_Income.py", title="Input Data Income", icon="📝")
        )
        halaman.append(
            st.Page("pages/5_Input_Data_Expense.py", title="Input Data Expense", icon="🧾")
        )
        halaman.append(
            st.Page("pages/6_Input_Data_Investment.py", title="Input Data Investment", icon="📈")
        )
    pg = st.navigation(halaman)

pg.run()