import streamlit as st
import pandas as pd
import requests
import re
import io

# --- OpenRouter API Setup ---
OPENROUTER_KEY=st.secrets["api"]["openrouter_key"]
API_URL = "https://openrouter.ai/api/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {OPENROUTER_KEY}",
    "HTTP-Referer": "https://yourdomain.com",  # Required by OpenRouter
    "Content-Type": "application/json"
}

# --- Function to extract merchant name using GPT-3.5
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

# --- Streamlit App UI ---
st.set_page_config(page_title="Merchant Extractor (GPT via OpenRouter)", layout="wide")
st.title("🧾 Merchant Name Extractor using GPT-3.5 (Free via OpenRouter)")

uploaded_file = st.file_uploader("📤 Upload your Excel file", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df = df.astype(str)  # Fix Arrow errors
    st.write("📊 Preview of uploaded data:")
    st.dataframe(df.head())

    selected_column = st.selectbox("🧩 Select the Payee Column", df.columns)

    if st.button("🚀 Extract Merchant Names"):
        with st.spinner("Calling GPT via OpenRouter... extracting..."):
            df["Merchant Name"] = df[selected_column].apply(extract_merchant)

        st.success("✅ Extraction Complete!")
        st.dataframe(df[[selected_column, "Merchant Name"]].head())

        # Export Excel
        df_export = df.astype(str)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_export.to_excel(writer, index=False, sheet_name="Merchant Names")

        st.download_button(
            "📥 Download Excel with Merchant Names",
            output.getvalue(),
            file_name="merchant_names_openrouter.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
