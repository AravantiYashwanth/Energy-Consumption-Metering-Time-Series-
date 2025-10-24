import boto3
import pandas as pd
from io import StringIO
import warnings
import os
warnings.filterwarnings('ignore')

# ---------- AWS Configuration ----------
RAW_BUCKET = "electricity-meter-readings"
AGG_BUCKET = "electricity-meter-aggregated-readings"
REGION = "ap-south-1"
s3 = boto3.client(
    's3',
    aws_access_key_id='',
    aws_secret_access_key='',
    region_name=REGION
)

# ---------- Local combined CSV ----------
os.makedirs("metering_csv", exist_ok=True)
combined_csv_path = "/Workspace/Users/yashwantharavanti@gmail.com/metering_csv/downloaded_metering_data.csv"

# ---------- EXTRACT ----------
print("EXTRACT PHASE")
df = pd.read_csv(combined_csv_path, quotechar='"', on_bad_lines='skip', low_memory=False)
print(f"Combined CSV loaded: {len(df)} records, columns: {df.columns.tolist()}")

# ---------- TRANSFORM: Cleaning ----------
print("Cleaning data")
# Convert Date column to datetime
df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
df = df.dropna(subset=['Date'])

# Convert numeric columns
numeric_cols = [
    'Global_active_power', 'Global_reactive_power',
    'Voltage', 'Global_intensity',
    'Sub_metering_1', 'Sub_metering_2', 'Sub_metering_3'
]
for c in numeric_cols:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors='coerce')

# Remove rows where all numeric values are NaN or zero
print("Removing empty or zero-value rows")
df = df.dropna(subset=numeric_cols, how='all')
df = df[~(df[numeric_cols].fillna(0) == 0).all(axis=1)]
print(f"Records after removing empty/zero rows: {len(df)}")

# ---------- TRANSFORM: Daily Aggregation ----------
print("Aggregating daily data")
daily_agg = df.groupby('Date').agg({
    'Global_active_power': 'mean',
    'Global_reactive_power': 'mean',
    'Voltage': ['mean', 'min', 'max'],
    'Global_intensity': 'mean',
    'Sub_metering_1': 'sum',
    'Sub_metering_2': 'sum',
    'Sub_metering_3': 'sum'
})

# Flatten column names
daily_agg.columns = [
    'avg_Global_active_power', 'avg_Global_reactive_power',
    'avg_Voltage', 'min_Voltage', 'max_Voltage',
    'avg_Global_intensity',
    'total_Sub_metering_1', 'total_Sub_metering_2', 'total_Sub_metering_3'
]
daily_agg = daily_agg.reset_index()

# Average sub-metering
daily_agg['avg_submetering_value'] = (
    daily_agg['total_Sub_metering_1'] +
    daily_agg['total_Sub_metering_2'] +
    daily_agg['total_Sub_metering_3']
) / 3

# Total daily sum
daily_agg['total_daily_sum'] = (
    daily_agg['total_Sub_metering_1'] +
    daily_agg['total_Sub_metering_2'] +
    daily_agg['total_Sub_metering_3']
)

# ---------- Anomaly Detection (3-sigma) ----------
mean_sub = daily_agg['avg_submetering_value'].mean()
std_sub = daily_agg['avg_submetering_value'].std()
daily_agg['anomaly_flag'] = (
    (daily_agg['avg_submetering_value'] > mean_sub + 3 * std_sub) |
    (daily_agg['avg_submetering_value'] < mean_sub - 3 * std_sub)
)

# ---------- NIGHTLY ETL: Peak/Off-Peak Billing ----------
print("Calculating Peak / Off-Peak billing")
if 'Time' in df.columns:
    df['DateTime'] = pd.to_datetime(
        df['Date'].dt.strftime('%Y-%m-%d') + ' ' + df['Time'],
        errors='coerce'
    )
    df['Hour'] = df['DateTime'].dt.hour
    df['period'] = df['Hour'].apply(lambda x: 'peak' if 18 <= x < 22 else 'offpeak')
    df['Global_active_power'] = pd.to_numeric(df['Global_active_power'], errors='coerce')
    
    daily_power = df.groupby(['Date',
    'period'])['Global_active_power'].sum().unstack(fill_value=0).reset_index()
    
    PEAK_RATE = 8.5
    OFFPEAK_RATE = 5.0
    
    daily_power['peak_charge'] = daily_power.get('peak', 0) * PEAK_RATE
    daily_power['offpeak_charge'] = daily_power.get('offpeak', 0) * OFFPEAK_RATE
    daily_power['total_charge'] = daily_power['peak_charge'] + daily_power['offpeak_charge']
    
    # Merge billing with aggregated data
    final_agg = pd.merge(
        daily_agg,
        daily_power[['Date', 'peak_charge', 'offpeak_charge', 'total_charge']],
        on='Date',
        how='left'
    )
else:
    print("Time column not found, skipping peak/off-peak billing")
    final_agg = daily_agg.copy()

# ---------- LOAD: Upload to S3 ----------
print("Uploading final aggregated ETL file to S3")
csv_buffer = StringIO()
final_agg.to_csv(csv_buffer, index=False)
s3_key = f"data/billing_agg_{pd.Timestamp.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
s3.put_object(
    Bucket=AGG_BUCKET,
    Key=s3_key,
    Body=csv_buffer.getvalue(),
    ContentType='text/csv'
)
print(f"✅ ETL Completed! Uploaded to s3://{AGG_BUCKET}/{s3_key}")
print(f"Total records in final output: {len(final_agg)}")