






import requests
import pandas as pd
import os
import zipfile
import shutil
import time

# ==========================================
# CONFIGURATION
# ==========================================


BASE_URL = "https://godaddy.api.identitynow.com"

CLIENT_ID = "a8eca91c236043c58d913ad3c2299767"
CLIENT_SECRET = "47f6befc5e6bcb2e159e25b8ac29f03730bf8bb1c6c06cd3ac1f09abd477371d"
TOKEN_URL = f"{BASE_URL}/oauth/token"

# ==========================================
# GENERATE TOKEN
# ==========================================

print("Generating token...")

payload = {
    "grant_type": "client_credentials",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET
}

response = requests.post(
    TOKEN_URL,
    data=payload,
    headers={"Content-Type": "application/x-www-form-urlencoded"}
)

if response.status_code != 200:
    print("Token generation failed")
    print(response.text)
    exit()

access_token = response.json()["access_token"].strip()
print("Token generated successfully")

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

# ==========================================
# INPUT
# ==========================================

campaign_filter = input("Enter Campaign Filter (Example: 2026 Q2): ").strip()
status_filter = input("Enter Campaign Status: ").strip().upper()

# ==========================================
# DOWNLOAD FOLDER
# ==========================================

DOWNLOAD_FOLDER = "downloads"

if os.path.exists(DOWNLOAD_FOLDER):
    shutil.rmtree(DOWNLOAD_FOLDER)

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ==========================================
# FETCH CAMPAIGNS
# ==========================================

print("\nFetching campaigns...")

all_campaigns = []
offset = 0
limit = 250

while True:
    url = f"{BASE_URL}/v3/campaigns?limit={limit}&offset={offset}"
    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        print("Failed to fetch campaigns")
        exit()

    data = res.json()
    if not data:
        break

    all_campaigns.extend(data)
    offset += limit

print(f"\nTotal campaigns found: {len(all_campaigns)}")

# ==========================================
# FILTER
# ==========================================

filtered = []

for c in all_campaigns:
    name = c.get("name", "")
    status = c.get("status", "").upper()
    cid = c.get("id")

    if campaign_filter.lower() not in name.lower():
        continue

    if status != status_filter:
        continue

    filtered.append({"id": cid, "name": name, "status": status})

print(f"Matching campaigns: {len(filtered)}")

# ==========================================
# HOLDER
# ==========================================

status_data = []

# ==========================================
# DOWNLOAD FUNCTION
# ==========================================

def download_status(report_id, folder):
    url = f"{BASE_URL}/v2025/reports/{report_id}?fileFormat=csv"

    path = os.path.join(folder, "status.csv")

    r = requests.get(url, headers=headers)

    if r.status_code != 200 or not r.content:
        return None

    with open(path, "wb") as f:
        f.write(r.content)

    try:
        df = pd.read_csv(path, low_memory=False)
        return df if not df.empty else None
    except:
        return None

# ==========================================
# PROCESS CAMPAIGNS
# ==========================================

for c in filtered:

    cid = c["id"]
    name = c["name"]
    status = c["status"]

    print(f"\nProcessing: {name}")

    safe = name.replace("/", "_").replace("\\", "_").replace(" ", "_")
    folder = os.path.join(DOWNLOAD_FOLDER, safe)
    os.makedirs(folder, exist_ok=True)

    r = requests.get(
        f"{BASE_URL}/v3/campaigns/{cid}/reports",
        headers=headers
    )

    if r.status_code != 200:
        continue

    reports = r.json()

    status_reports = [
        rep for rep in reports
        if rep.get("reportType", "").upper() == "CAMPAIGN_STATUS_REPORT"
        and rep.get("id")
    ]

    if not status_reports:
        continue

    report_id = status_reports[-1]["id"]

    print("Downloading STATUS report...")

    df = download_status(report_id, folder)

    if df is None:
        print("Skipped empty report")
        continue

    print("Rows Loaded:", len(df))

    # ======================================================
    # ✅ FIX: INSERT COLUMNS AT FRONT (NOT END)
    # ======================================================

    df.insert(0, "Campaign_Name", name)
    df.insert(1, "Campaign_Status", status)

    status_data.append(df)

    # ZIP
    zip_path = os.path.join(folder, f"{safe}.zip")

    with zipfile.ZipFile(zip_path, "w") as z:
        for f in os.listdir(folder):
            if f.endswith(".csv"):
                z.write(os.path.join(folder, f), arcname=f)

    print(f"ZIP created: {zip_path}")

# ==========================================
# MERGE FILE
# ==========================================

print("\nCreating merged file...")

safe_name = campaign_filter.replace(" ", "_")

if status_data:

    final_df = pd.concat(status_data, ignore_index=True)

    final_file = f"{safe_name}_merged_status.csv"
    final_df.to_csv(final_file, index=False)

    print("Created:", final_file)
    print("Total Rows:", len(final_df))

else:
    print("No valid data")

# ==========================================
# BACKUP
# ==========================================

backup_name = f"{safe_name}_backup"
shutil.make_archive(backup_name, "zip", DOWNLOAD_FOLDER)

print("\nBackup created:", backup_name + ".zip")

# ==========================================
# CLEANUP
# ==========================================

time.sleep(90)
if os.path.exists(DOWNLOAD_FOLDER):
    shutil.rmtree(DOWNLOAD_FOLDER)

print("Done")