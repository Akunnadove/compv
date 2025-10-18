import streamlit as st
import pytesseract
import PIL.Image
import pandas as pd
import os
import re

# ----------------------- PAGE SETUP -----------------------
st.set_page_config(layout="wide")
st.title("SmartVision Analytics")
st.write("Upload a bank receipt to extract transaction details automatically.")

# ----------------------- CONFIGURATION -----------------------
myconfig = r"--psm 11 --oem 3"
DATA_FILE = "extracted_receipts.csv"

# Load or initialize dataset
if os.path.exists(DATA_FILE):
    df = pd.read_csv(DATA_FILE)
else:
    df = pd.DataFrame(columns=["Bank Name", "Account Name", "Amount Transferred", "Date"])

# ----------------------- UTILITIES -----------------------
def clean_line(line: str) -> str:
    """Clean and trim OCR text lines."""
    if not isinstance(line, str):
        return ""
    line = line.replace("\x0c", "")
    line = re.sub(r"[^\S\r\n]+", " ", line)
    return line.strip()

def is_uppercase_text(line: str) -> bool:
    """Check if a line is fully uppercase (for detecting bank names)."""
    text = re.sub(r"[^A-Za-z]", "", line)
    return text.isupper() and len(text) > 2

def extract_text(image_file):
    """Extract raw text from uploaded receipt image using Tesseract OCR."""
    text = pytesseract.image_to_string(PIL.Image.open(image_file), config=myconfig)
    lines = [clean_line(line) for line in text.split("\n") if clean_line(line)]
    return lines

# ----------------------- PARSING -----------------------
def parse_data(lines):
    """
    Parsing rules:
      - Bank Name = first fully UPPERCASE text before 'Detailed Receipt'
      - Amount Transferred = line containing '$'
      - Account Name = line starting with 'from'
      - Date = first MM/DD/YYYY-like pattern
    """
    bank_name = ""
    account_name = ""
    amount = ""
    date = ""

    # Find "Detailed Receipt" index
    detailed_idx = None
    for i, line in enumerate(lines):
        if "detailed receipt" in line.lower():
            detailed_idx = i
            break

    # 1) Bank Name: scan upwards from "Detailed Receipt" for first uppercase text
    if detailed_idx is not None:
        for j in range(detailed_idx - 1, -1, -1):
            if is_uppercase_text(lines[j]):
                bank_name = lines[j].strip()
                break

    # 2) Amount: first line that contains a $ sign
    for line in lines:
        if "$" in line:
            m = re.search(r"\$\s*[\d,]+(?:\.\d+)?", line)
            if m:
                amount = m.group(0).replace(" ", "")
                break

    # 3) Account name: starts with 'from'
    for line in lines:
        if line.lower().startswith("from"):
            acc = re.sub(r'^[Ff][Rr][Oo][Mm]\s*:?\s*', '', line).strip()
            account_name = acc
            break

    # 4) Date: first MM/DD/YYYY
    for line in lines:
        m = re.search(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", line)
        if m:
            date = m.group(0)
            break

    return {
        "Bank Name": bank_name,
        "Account Name": account_name,
        "Amount Transferred": amount,
        "Date": date
    }

def clean_amount_value(val):
    """Convert $ values to float."""
    if not isinstance(val, str) or "$" not in val:
        return None
    v = re.sub(r"[^\d\.]", "", val)
    try:
        return float(v) if v else None
    except:
        return None

# ----------------------- UPLOAD & PROCESS -----------------------
uploaded_file = st.file_uploader("📤 Select a Receipt", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    st.image(uploaded_file, caption="Uploaded Receipt", use_container_width=True)

    with st.spinner("Extracting data... ⏳"):
        lines = extract_text(uploaded_file)
        st.write("### Extracted Text:")
        st.write(lines)

        parsed = parse_data(lines)

        if any(parsed.values()):
            st.success("✅ Data extracted successfully!")
            st.json(parsed)

            # Append extracted record to dataset
            df = pd.concat([df, pd.DataFrame([parsed])], ignore_index=True)
            df.to_csv(DATA_FILE, index=False)
            st.success("Record added to dataset ✅")
        else:
            st.warning("⚠️ No relevant data extracted. Check the image clarity or text format.")

# ----------------------- DATA DISPLAY -----------------------
st.divider()
st.subheader("📊 Extracted Receipts Dataset")
st.dataframe(df, use_container_width=True)

# Clean and calculate total amount using only $-based entries
try:
    df["Amount Cleaned"] = df["Amount Transferred"].apply(lambda x: clean_amount_value(x) if pd.notnull(x) else None)
    total_amount = df["Amount Cleaned"].dropna().sum()
    st.metric(label="💰 Total Amount Transferred", value=f"${total_amount:,.2f}")
except Exception:
    st.warning("Unable to calculate total — please ensure amounts contain a $ sign.")

# ----------------------- DOWNLOAD BUTTON -----------------------
st.download_button(
    label="📥 Download Dataset as CSV",
    data=df.drop(columns="Amount Cleaned", errors="ignore").to_csv(index=False).encode("utf-8"),
    file_name="extracted_receipts.csv",
    mime="text/csv"
)

st.info("Uploads append to the same dataset. Bank name is detected as the first FULLY UPPERCASE text before 'Detailed Receipt'. Amounts are taken only when a $ is present.")
