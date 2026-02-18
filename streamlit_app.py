import streamlit as st
from snowflake.snowpark.functions import col
import requests
from urllib.parse import quote_plus
import pandas as pd   # NEW for Lesson 10 Part 2

st.title("🍹 Customize Your Smoothie!")
st.write("Choose the fruits you want in your custom Smoothie!")
st.write("Choose up to 5 ingredients:")

# Snowpark session inside SiS
cnx = st.connection("snowflake")
session = cnx.session()

# Load FRUIT_OPTIONS with FRUIT_NAME + SEARCH_ON
my_dataframe = session.table("SMOOTHIES.PUBLIC.FRUIT_OPTIONS").select(
    col("FRUIT_NAME"), col("SEARCH_ON")
)

# Convert Snowpark DF → Pandas DF
pd_df = my_dataframe.to_pandas()

# Multiselect uses FRUIT_NAME column
ingredients_list = st.multiselect(
    "Choose up to 5 ingredients:",
    options=pd_df["FRUIT_NAME"].tolist(),
    max_selections=5
)

# Smoothie name
name_on_order = st.text_input("Name on Smoothie:")

# Build ingredient string
ingredients_string = " ".join(ingredients_list) if ingredients_list else ""

st.caption("Ingredients Preview:")
st.code(ingredients_string if ingredients_string else "(no ingredients selected yet)")

# -----------------------------
# 🍏 SmoothieFroot API Lookup using SEARCH_ON
# -----------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_smoothiefroot(fruit_name: str):
    url = f"https://my.smoothiefroot.com/api/fruit/{quote_plus(fruit_name.lower())}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()

if ingredients_list:
    st.subheader("🍏 Nutrition Information")
    for fruit_chosen in ingredients_list:

        # -----------------------------------------
        # 1️⃣ Get SEARCH_ON value from pd_df using .loc[]
        # -----------------------------------------
        if fruit_chosen in pd_df["FRUIT_NAME"].values:
            search_on = pd_df.loc[
                pd_df["FRUIT_NAME"] == fruit_chosen, "SEARCH_ON"
            ].iloc[0]
        else:
            # Fruit not in table → automatically insert it
            search_on = fruit_chosen
            session.sql(f"""
                INSERT INTO SMOOTHIES.PUBLIC.FRUIT_OPTIONS (FRUIT_NAME, SEARCH_ON)
                VALUES ('{fruit_chosen}', '{fruit_chosen}');
            """).collect()

        st.subheader(f"{fruit_chosen} Nutrition Information")

        # -----------------------------------------
        # 2️⃣ Try SmoothieFroot API call
        # -----------------------------------------
        try:
            data = fetch_smoothiefroot(search_on)
            st.dataframe(data, use_container_width=True)

        except requests.HTTPError as http_err:
            # Auto-fix names on 404
            if http_err.response is not None and http_err.response.status_code == 404:

                # Basic plural → singular fallback
                if fruit_chosen.endswith("ies"):
                    fixed = fruit_chosen[:-3] + "y"
                elif fruit_chosen.endswith("s"):
                    fixed = fruit_chosen[:-1]
                else:
                    fixed = fruit_chosen

                st.info(f"Trying alternate API search for '{fixed}'…")

                # Save corrected SEARCH_ON
                session.sql(f"""
                    UPDATE SMOOTHIES.PUBLIC.FRUIT_OPTIONS
                    SET SEARCH_ON = '{fixed}'
                    WHERE FRUIT_NAME = '{fruit_chosen}';
                """).collect()

                try:
                    data = fetch_smoothiefroot(fixed)
                    st.dataframe(data, use_container_width=True)
                except:
                    st.error(f"Still no data for '{fruit_chosen}'.")
            else:
                st.error(f"API error fetching: {fruit_chosen}")

# -----------------------------
# 📝 Submit order
# -----------------------------
submit = st.button("Submit Order")

if submit:
    if not ingredients_list:
        st.error("Please choose at least one ingredient.")
    elif len(ingredients_string) > 200:
        st.error("Ingredients exceed 200 characters.")
    elif not name_on_order.strip():
        st.error("Please provide a name for the smoothie.")
    else:
        safe_ing = ingredients_string.replace("'", "''")
        safe_name = name_on_order.strip().replace("'", "''")

        next_id = session.sql("""
            SELECT COALESCE(MAX(order_uid), 0) + 1 
            FROM SMOOTHIES.PUBLIC.ORDERS
        """).collect()[0][0]

        session.sql(f"""
            INSERT INTO SMOOTHIES.PUBLIC.ORDERS (order_uid, name_on_order, ingredients)
            VALUES ({next_id}, '{safe_name}', '{safe_ing}');
        """).collect()

        st.success(f"🥤 Order #{next_id} placed for **{safe_name}**!", icon="🎉")
