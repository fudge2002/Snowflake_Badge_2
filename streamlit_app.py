import streamlit as st
from snowflake.snowpark.functions import col
import requests

# Get Snowpark session inside SniS app
cnx = st.connection("snowflake")
session = cnx.session()

st.set_page_config(page_title="Smoothie Maker", page_icon="🥤", layout="centered")
st.title("🥤 Smoothie Maker")

st.write(
    "Create smoothie orders and write them to **SMOOTHIES.PUBLIC.ORDERS**. "
    "The **order of fruits matters** for the lab grader."
)

# --- Helpers -----------------------------------------------------------------

def load_fruits():
    # Pull available fruits from FRUIT_OPTIONS (sorted for a nice UX)
    rows = session.sql("""
        SELECT FRUIT_NAME
        FROM SMOOTHIES.PUBLIC.FRUIT_OPTIONS
        ORDER BY FRUIT_NAME
    """).collect()
    return [r[0] for r in rows]

def format_ingredients(selected):
    """
    Format exactly like typical workshop solutions:
      - 0 items: ''
      - 1 item : 'Apple'
      - 2 items: 'Apple and Banana'
      - >=3    : 'Apple, Banana, ... and Mango'
    """
    if not selected:
        return ""
    if len(selected) == 1:
        return selected[0]
    if len(selected) == 2:
        return f"{selected[0]} and {selected[1]}"
    return f"{', '.join(selected[:-1])} and {selected[-1]}"

def insert_order(name: str, ingredients: str, filled: bool):
    # Escape single quotes for a simple SQL insert in this lab context
    name_sql = name.replace("'", "''")
    ing_sql  = ingredients.replace("'", "''")
    filled_sql = "TRUE" if filled else "FALSE"
    session.sql(f"""
        INSERT INTO SMOOTHIES.PUBLIC.ORDERS
        (NAME_ON_ORDER, INGREDIENTS, ORDER_FILLED, ORDER_TS)
        VALUES ('{name_sql}', '{ing_sql}', {filled_sql}, CURRENT_TIMESTAMP())
    """).collect()

def fetch_orders():
    return session.sql("""
        SELECT
          NAME_ON_ORDER,
          INGREDIENTS,
          ORDER_FILLED,
          ORDER_TS,
          HASH(INGREDIENTS) AS HASH_VALUE
        FROM SMOOTHIES.PUBLIC.ORDERS
        ORDER BY ORDER_TS DESC
    """).to_pandas()

# --- UI ----------------------------------------------------------------------

with st.form("order-form", clear_on_submit=True):
    name = st.text_input("Name on order", help="Enter the person's name (e.g., Kevin, Divya, Xi)")
    fruits = load_fruits()

    st.caption("Select fruits **in the order you want them recorded**.")
    selected = st.multiselect(
        "Choose fruits (order matters)",
        fruits,
        default=[],
        help="Pick in the exact order required by the lab."
    )

    order_filled = st.checkbox("Mark order as FILLED", value=False)
    submitted = st.form_submit_button("Submit Order")

    if submitted:
        if not name.strip():
            st.error("Please provide a name on the order.")
        elif len(selected) == 0:
            st.error("Please select at least one fruit.")
        else:
            # Multi-select preserves selection order, so we use it as-is
            ingredients_str = format_ingredients(selected)
            insert_order(name.strip(), ingredients_str, order_filled)
            st.success(f"Order saved for **{name.strip()}** → *{ingredients_str}* "
                       f"({'FILLED' if order_filled else 'NOT filled'})")

#new sectin api
smoothiefroot_response = requests.get("https://my.smoothiefroot.com/api/fruit/watermelon")
sf_df = st.dataframe(data=smoothiefroot_response.json(),use_container_width=True)


st.subheader("📦 Current Orders")
orders_df = fetch_orders()
st.dataframe(
    orders_df,
    use_container_width=True,
    hide_index=True
)

#grader looking for
with st.expander("What does the grader check?"):
    st.markdown("""
- **Kevin**: *Apples, Lime and Ximenia* — **NOT filled**
- **Divya**: *Dragon Fruit, Guava, Figs, Jackfruit and Blueberries* — **FILLED**
- **Xi**: *Vanilla Fruit and Nectarine* — **FILLED**

The grader compares `HASH(INGREDIENTS)` for those exact strings and flags pass/fail.
""")
