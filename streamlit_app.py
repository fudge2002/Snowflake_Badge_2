import streamlit as st
from snowflake.snowpark.functions import col
from urllib.parse import quote_plus
import requests

st.title("🍹 Customize Your Smoothie!")
st.write("Choose the fruits you want in your custom Smoothie!")
st.write("Choose up to 5 ingredients:")

# Get Snowpark session inside SniS app
cnx = st.connection("snowflake")
session = cnx.session()


 Load fruit list from Snowflake
fruit_df = session.table("SMOOTHIES.PUBLIC.FRUIT_OPTIONS")  # must contain FRUIT_NAME column
fruit_list = fruit_df.select("FRUIT_NAME").to_pandas()["FRUIT_NAME"].tolist()

# Limit to 5 ingredients
ingredients_list = st.multiselect(
    "Choose up to 5 ingredients:",
    options=fruit_list,
    max_selections=5
)

# Name input
name_on_order = st.text_input("Name on Smoothie (saved as NAME_ON_ORDER)")

# Build space-separated string (no commas, no 'and')
ingredients_string = " ".join(ingredients_list) if ingredients_list else ""

# Preview
st.caption("Ingredients Preview:")
st.code(ingredients_string if ingredients_string else "(no ingredients selected yet)")

# -----------------------------
# 🍊 Nutrition info from SmoothieFroot API
# -----------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_smoothiefroot(fruit_name: str):
    """
    Fetch nutrition info for a single fruit from SmoothieFroot API.
    Returns JSON (dict or list) or raises on HTTP errors.
    """
    url = f"https://my.smoothiefroot.com/api/fruit/{quote_plus(fruit_name.lower())}"
    resp = requests.get(url, timeout=10)
    # Raise for non-2xx so caller can handle 404 nicely
    resp.raise_for_status()
    return resp.json()

if ingredients_list:
    st.divider()
    st.subheader("🍏 Nutrition Information")
    for fruit in ingredients_list:
        st.markdown(f"**{fruit} Nutrition Information**")
        try:
            data = fetch_smoothiefroot(fruit)
            # data can be a dict or a list of dicts; Streamlit handles either
            st.dataframe(data, use_container_width=True)
        except requests.HTTPError as http_err:
            # Many fruits in the lab list won’t exist in the API — show friendly note
            if getattr(http_err, "response", None) and http_err.response.status_code == 404:
                st.info(f"Sorry, **{fruit}** is not in the SmoothieFroot database.")
            else:
                st.error(f"Could not fetch nutrition for **{fruit}** (HTTP error).")
        except Exception as e:
            st.error(f"Unexpected error fetching data for **{fruit}**.")
else:
    st.info("Select one or more fruits above to see their nutrition information.")

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
    elif len(name_on_order.strip()) > 100:
        st.error("Name on order exceeds 100 characters.")
    else:
        # Escape quotes
        safe_ingredients = ingredients_string.replace("'", "''")
        safe_name = name_on_order.strip().replace("'", "''")

        try:
            # Next ORDER_UID without sequences
            next_id = session.sql(
                "SELECT COALESCE(MAX(order_uid), 0) + 1 AS next_id FROM SMOOTHIES.PUBLIC.ORDERS"
            ).collect()[0]["NEXT_ID"]

            insert_sql = f"""
                INSERT INTO SMOOTHIES.PUBLIC.ORDERS (order_uid, name_on_order, ingredients)
                VALUES ({next_id}, '{safe_name}', '{safe_ingredients}');
            """
            session.sql(insert_sql).collect()
            st.success(f"🥤 Order #{next_id} placed for **{safe_name}**!", icon="✅")
        except Exception as e:
            st.error("Something went wrong while placing your order. Please try again.")
            st.exception(e)
