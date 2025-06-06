import streamlit as st
import pandas as pd
import requests
import re
import io
from tinydb import TinyDB, Query
# --- OpenRouter API Setup ---
OPENROUTER_KEY = st.secrets["api"]["openrouter_key"]
API_URL = "https://openrouter.ai/api/v1/chat/completions"
HTTP_REFERER = "https://clouditustoolmerchantextractor.streamlit.app"  # ✅ Your deployed app URL

headers = {
    "Authorization": f"Bearer {OPENROUTER_KEY}",
    "HTTP-Referer": HTTP_REFERER,
    "Content-Type": "application/json"
}

# --- TinyDB for Category Storage ---
category_db = TinyDB("categories_db.json")
category_table = category_db.table("categories")

# --- Initialize with Predefined Categories if Empty ---
def initialize_categories():
    if len(category_table) == 0:
        default_categories = [
            "Advertising & Marketing",
            "Bank & Payment Fees",
            "Car & Vehicle Expenses",
            "Charitable Contributions",
            "Computer & Internet Expenses",
            "Consulting & Professional Services",
            "Contractors & Freelancers",
            "Dues & Subscriptions",
            "Education & Training",
            "Employee Benefits",
            "Entertainment & Client Hospitality",
            "Equipment & Furniture",
            "Freight & Courier Charges",
            "Gifts & Donations",
            "Government Fees & Licenses",
            "Insurance (General)",
            "Legal & Accounting Services",
            "Meals & Beverages (Business)",
            "Meals & Beverages (Personal/Employee)",
            "Office Supplies",
            "Payroll Expenses",
            "Postage & Shipping",
            "Printing & Stationery",
            "Rent & Lease Payments",
            "Repairs & Maintenance",
            "Software & SaaS Tools",
            "Taxes (Sales, VAT, GST)",
            "Telecom & Mobile Services",
            "Tools & Small Assets",
            "Travel – Airfare",
            "Travel – Accommodation",
            "Travel – Ground Transport",
            "Utilities (Gas, Water, Electricity)",
            "Unknown / Miscellaneous"
        ]
        for cat in default_categories:
            category_table.insert({"name": cat})

initialize_categories()

# --- Category Functions ---
def get_categories():
    return sorted(set(row['name'] for row in category_table.all()))

def add_category(new_cat):
    if new_cat and new_cat not in get_categories():
        category_table.insert({"name": new_cat})

def delete_category(cat_name):
    category_table.remove(Query().name == cat_name)

# --- OpenRouter Call ---
def call_openrouter(prompt):
    data = {
        "model": "openai/gpt-3.5-turbo",
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post(API_URL, headers=headers, json=data, timeout=30)
    response.raise_for_status()
    result = response.json()
    return result["choices"][0]["message"]["content"].strip()

# --- Extract Merchant ---
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

# --- Infer Category ---
def infer_expense_category(merchant):
    category_list = get_categories()
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

# --- Streamlit UI ---
st.set_page_config(page_title="CLOUD-IT TOOLS", layout="wide", initial_sidebar_state="auto")
st.markdown("""
    <style>
    body {
        background-color: #0f111a;
        color: #e1e1e1;
    }
    .stApp {
        background-color: #0f111a;
    }
    .stButton>button {
        background-color: #1a73e8;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 4px;
    }
    .stButton>button:hover {
        background-color: #4285f4 !important;
        color: #ffffff !important;
    }
    .css-1d391kg, .css-1v0mbdj, .css-1lcbmhc, .css-ffhzg2, .css-1q8dd3e {
        color: #e1e1e1;
    }
</style>
""", unsafe_allow_html=True)
st.title("🧾 Merchant Name & Category Extractor")

# --- Category Management ---
with st.expander("⚙️ Manage Categories"):
    current_categories = get_categories()
    st.write("### Current Categories:")
    st.write(current_categories)

    new_cat = st.text_input("➕ Add New Category")
    if st.button("Add Category"):
        add_category(new_cat)
        st.experimental_rerun()

    delete_cat = st.selectbox("🗑️ Delete Category", options=current_categories)
    if st.button("Delete Selected"):
        delete_category(delete_cat)
        st.experimental_rerun()

# --- Upload File ---
uploaded_file = st.file_uploader("📤 Upload your Excel or CSV file", type=["xlsx", "csv"])

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
            merchants = []
            categories = []
            confidences = []
            error_logs = []

            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, text in enumerate(df[selected_column]):
                try:
                    merchant = extract_merchant(text)
                    category, confidence = infer_expense_category(merchant)
                    error_logs.append("")
                except Exception as e:
                    merchant = "ERROR"
                    category = "Unknown / Miscellaneous"
                    confidence = ""
                    error_logs.append(str(e))
                    st.warning(f"Error in row {i+1}: {e}")

                merchants.append(merchant)
                categories.append(category)
                confidences.append(confidence)

                progress = (i + 1) / total_rows
                progress_bar.progress(progress)
                status_text.text(f"Processed {i+1} of {total_rows} rows ({int(progress * 100)}%)")

            df["Merchant Name"] = merchants
            df["Expense Category"] = categories
            df["Confidence"] = confidences
            df["Error Log"] = error_logs

        st.success("✅ Extraction Complete!")
        st.dataframe(df[[selected_column, "Merchant Name", "Expense Category", "Confidence", "Error Log"]].head())

        if any(df["Error Log"]):
            st.subheader("⚠️ Errors Detected")
            st.dataframe(df[df["Error Log"] != ""][["Merchant Name", "Error Log"]])

        df_export = df.astype(str)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_export.to_excel(writer, index=False, sheet_name="Results")

        output.seek(0)
        download_clicked = st.download_button(
            "📥 Download Excel",
            data=output.getvalue(),
            file_name="merchant_category_classified.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        if download_clicked:
            st.toast("✅ File downloaded successfully!")
