import streamlit as st
import pandas as pd
import requests
import re
import io

# --- OpenRouter API Setup ---
OPENROUTER_KEY = st.secrets["api"]["openrouter_key"]
API_URL = "https://openrouter.ai/api/v1/chat/completions"
HTTP_REFERER = "https://clouditustoolmerchantextractor.streamlit.app"  # ✅ Your deployed app URL

headers = {
    "Authorization": f"Bearer {OPENROUTER_KEY}",
    "HTTP-Referer": HTTP_REFERER,
    "Content-Type": "application/json"
}

# --- Function to extract merchant name using GPT-3.5 ---
def call_openrouter(prompt):
    data = {
        "model": "openai/gpt-3.5-turbo",
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        response = requests.post(API_URL, headers=headers, json=data)
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        st.error(f"OpenRouter API error: {e}")
        return "[ERROR]"

# --- Extract Merchant Name ---
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

Examples:
- "FACEBK *JL9BAL8\\N72 650-5434800 CA" → Facebook
- "IN *RPM DESIGN WORKS, LLC 360-3050268 WA" → RPM Design Works
- "EXPRESSVPN.COM EXPRESSVPN.CO DE" → ExpressVPN
- "USPS PO 5448160243 LYNDEN WA" → USPS
- "SQ *BHAKTI TATTVA LLC 707-3868277 CA" → Bhakti Tattva

Now return only the extracted merchant name:
"""
    return call_openrouter(prompt)

# --- Infer Expense Category ---
def infer_expense_category(merchant):
    prompt = f"""
Based on the merchant name below, return the most probable expense category from this list:
- Food & Beverages
- Marketing
- Office Supplies
- Software
- Internet Services
- Travel
- Utilities
- Rent
- Other

Merchant: "{merchant}"

Only return the category. No formatting or explanation. If unclear, return: Other.
"""
    return call_openrouter(prompt)

# --- Streamlit App UI ---
st.set_page_config(page_title="CLOUD-IT TOOLS", layout="wide")
st.title("🧾 Merchant Name & Category Extractor")

uploaded_file = st.file_uploader("📤 Upload your Excel file", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df = df.astype(str)
    st.write("📊 Preview of uploaded data:")
    st.dataframe(df.head())

    selected_column = st.selectbox("🧩 Select the Payee Column", df.columns)

    if st.button("🚀 Extract Merchant Names and Categories"):
        with st.spinner("Running AI classification..."):
            df["Merchant Name"] = df[selected_column].apply(extract_merchant)
            df["Expense Category"] = df["Merchant Name"].apply(infer_expense_category)

        st.success("✅ Extraction Complete!")
        st.dataframe(df[[selected_column, "Merchant Name", "Expense Category"]].head())

        # Export Excel
        df_export = df.astype(str)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_export.to_excel(writer, index=False, sheet_name="Results")

        st.download_button(
            "📥 Download Excel",
            output.getvalue(),
            file_name="merchant_category_classified.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
