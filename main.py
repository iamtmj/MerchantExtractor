# --- Imports ---
import streamlit as st
import pandas as pd
import requests
import re
import io
from tinydb import TinyDB, Query

# --- OpenRouter API Setup ---
OPENROUTER_KEY = st.secrets["api"]["openrouter_key"]
API_URL = "https://openrouter.ai/api/v1/chat/completions"
HTTP_REFERER = "https://clouditustoolmerchantextractor.streamlit.app"
headers = {
    "Authorization": f"Bearer {OPENROUTER_KEY}",
    "HTTP-Referer": HTTP_REFERER,
    "Content-Type": "application/json"
}

# --- TinyDB Setup ---
category_db = TinyDB("categories_db.json")
category_table = category_db.table("categories")

def initialize_categories():
    if len(category_table) == 0:
        default_categories = [
            "Advertising & Marketing", "Bank & Payment Fees", "Car & Vehicle Expenses",
            "Charitable Contributions", "Computer & Internet Expenses", "Consulting & Professional Services",
            "Contractors & Freelancers", "Dues & Subscriptions", "Education & Training",
            "Employee Benefits", "Entertainment & Client Hospitality", "Equipment & Furniture",
            "Freight & Courier Charges", "Gifts & Donations", "Government Fees & Licenses",
            "Insurance (General)", "Legal & Accounting Services", "Meals & Beverages (Business)",
            "Meals & Beverages (Personal/Employee)", "Office Supplies", "Payroll Expenses",
            "Postage & Shipping", "Printing & Stationery", "Rent & Lease Payments",
            "Repairs & Maintenance", "Software & SaaS Tools", "Taxes (Sales, VAT, GST)",
            "Telecom & Mobile Services", "Tools & Small Assets", "Travel – Airfare",
            "Travel – Accommodation", "Travel – Ground Transport", "Utilities (Gas, Water, Electricity)",
            "Unknown / Miscellaneous"
        ]
        for cat in default_categories:
            category_table.insert({"name": cat})

initialize_categories()

def get_categories():
    return sorted(set(row['name'] for row in category_table.all()))

def add_category(new_cat):
    if new_cat and new_cat not in get_categories():
        category_table.insert({"name": new_cat})

def delete_category(cat_name):
    category_table.remove(Query().name == cat_name)

def call_openrouter(prompt):
    data = {
        "model": "openai/gpt-3.5-turbo",
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post(API_URL, headers=headers, json=data, timeout=30)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()

def extract_merchant(text):
    clean_text = re.sub(r'[^\w\s]', ' ', str(text))
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()

    prompt = f"""
You are a data cleanup assistant trained to extract merchant names from bank transaction descriptions.

Given the following transaction line:
"{clean_text}"

Extract only the **merchant or business name**. Follow these rules strictly:
- ✅ Remove phone numbers, zip codes, state abbreviations (like WA, CA), timestamps, and numeric codes.
- ✅ Do not include locations, descriptors (e.g., 'LLC', 'INVOICE', 'AUTH'), or additional context.
- ✅ Do not guess — if no valid merchant can be found, return: UNKNOWN.
- ❌ Do not include explanations or formatting.
- ❌ Never return phrases like "The merchant is..."

Now return only the extracted merchant name:
"""
    return call_openrouter(prompt)

def infer_expense_category(merchant, custom_list=None):
    category_list = custom_list if custom_list else get_categories()
    if not category_list:
        category_list = ["Unknown / Miscellaneous"]
    joined_list = "\n- " + "\n- ".join(category_list)
    prompt = f"""
Based on the merchant name below, return the most probable expense category from this list:{joined_list}

Merchant: "{merchant}"

Only return the single best-matching category. If unclear, return: "Unknown / Miscellaneous".
Also include a confidence score between 0 and 1 in parentheses next to the category.
No formatting. No explanation. Example output: Office Supplies (0.85)
"""
    response = call_openrouter(prompt)
    if "(" in response and ")" in response:
        parts = response.rsplit("(", 1)
        category = parts[0].strip()
        try:
            confidence = round(float(parts[1].replace(")", "").strip()) * 100, 2)
        except:
            confidence = ""
    else:
        category = response.strip()
        confidence = ""
    return category, confidence

# --- Streamlit UI Setup ---
st.set_page_config(page_title="CLOUD-IT TOOLS", layout="wide")
st.title("🧾 Merchant Name & Category Extractor")

st.subheader("📂 Custom Category Mapping (Optional)")
use_custom_category = st.radio("Would you like to attach the company's sample category sheet?", ["No", "Yes"], index=0)

custom_categories = []
if use_custom_category == "Yes":
    uploaded_category_file = st.file_uploader("📤 Upload your Category Mapping Sheet", type=["csv", "xlsx"], key="category_sheet")
    if uploaded_category_file:
        try:
            if uploaded_category_file.name.endswith(".csv"):
                cat_df = pd.read_csv(uploaded_category_file)
            else:
                cat_df = pd.read_excel(uploaded_category_file)

            cat_column = st.selectbox("📑 Select the column containing categories", cat_df.columns)
            if cat_column:
                custom_categories = sorted(set(cat_df[cat_column].dropna().astype(str).unique()))
                st.success(f"✅ {len(custom_categories)} categories loaded from uploaded sheet.")
        except Exception as e:
            st.error(f"Category sheet error: {e}")

with st.expander("⚙️ Manage Categories"):
    current_categories = get_categories()
    st.write(current_categories)
    new_cat = st.text_input("➕ Add New Category")
    if st.button("Add Category"):
        add_category(new_cat)
        st.rerun()
    delete_cat = st.selectbox("🗑️ Delete Category", options=current_categories)
    if st.button("Delete Selected"):
        delete_category(delete_cat)
        st.rerun()

uploaded_file = st.file_uploader("📤 Upload your Transaction File", type=["xlsx", "csv"])

if uploaded_file:
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"File read error: {e}")
        st.stop()

    df = df.astype(str)
    st.write("📊 Preview of uploaded data:")
    st.dataframe(df.head())

    selected_column = st.selectbox("🧩 Select the Payee Column", df.columns)

    if st.button("🚀 Extract Merchant Names and Categories"):
        with st.spinner("Running AI classification..."):
            total_rows = len(df)
            merchants, categories, confidences, error_logs = [], [], [], []

            for i, text in enumerate(df[selected_column]):
                try:
                    merchant = extract_merchant(text)
                    category, confidence = infer_expense_category(merchant, custom_list=custom_categories)
                    error_logs.append("")
                except Exception as e:
                    merchant, category, confidence = "ERROR", "Unknown / Miscellaneous", ""
                    error_logs.append(str(e))

                merchants.append(merchant)
                categories.append(category)
                confidences.append(confidence)

            df["Merchant Name"] = merchants
            df["Expense Category"] = categories
            df["Confidence"] = confidences
            df["Error Log"] = error_logs

        st.success("✅ Extraction Complete!")
        st.dataframe(df[[selected_column, "Merchant Name", "Expense Category", "Confidence", "Error Log"]].head())

        df_export = df.astype(str)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_export.to_excel(writer, index=False, sheet_name="Results")
        output.seek(0)

        st.download_button("📥 Download Excel", data=output.getvalue(), file_name="merchant_category_classified.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
