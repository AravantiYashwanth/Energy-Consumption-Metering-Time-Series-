import json
import boto3
import pandas as pd

# --- Configuration ---
BUCKET_NAME = "electricity-meter-aggregated-readings"
S3_PREFIX = "data/billing_agg_"
SNS_TOPIC_ARN = "arn:aws:sns:ap-south-1:487615743519:AnamolyDetection"

# --- AWS Clients ---
s3 = boto3.client('s3')
sns = boto3.client('sns')

def lambda_handler(event, context):
    """
    This Lambda function scans an S3 bucket for the latest billing CSV file,
    analyzes it for consumption anomalies, and sends an alert via SNS if any
    anomalies are detected.
    """
    try:
        # 1. Find the most recent billing file in S3
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=S3_PREFIX)
        if 'Contents' not in response:
            print("No billing files found in the specified S3 path.")
            return {"statusCode": 404, "body": "No billing files found in S3"}
        
        # Get the key of the file with the latest 'LastModified' timestamp
        latest_file = max(response['Contents'], key=lambda x: x['LastModified'])['Key']
        print(f"Latest billing file found: {latest_file}")
        
        # 2. Load the CSV file into a Pandas DataFrame
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=latest_file)
        df = pd.read_csv(obj['Body'])
        
        # 3. Data Cleaning and Preparation
        # Ensure 'Date' column exists and convert it to datetime objects
        if 'Date' not in df.columns:
            raise ValueError("CSV file is missing the required 'Date' column.")
        
        df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        df.dropna(subset=['Date'], inplace=True) # Drop rows where date conversion failed
        
        # Define column groups for processing
        sub_meter_cols = ['total_Sub_metering_1', 'total_Sub_metering_2', 'total_Sub_metering_3']
        billing_cols = ['total_daily_sum', 'peak_charge', 'offpeak_charge', 'total_charge']
        
        # Safely convert data columns to numeric, creating them if they don't exist
        for col in sub_meter_cols + billing_cols:
            if col not in df.columns:
                df[col] = 0 # Create the column with a default of 0 if missing
            else:
                # Convert to numeric, forcing errors (like non-numeric strings) into NaN, then fill with 0
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # 4. Anomaly Detection Logic
        alerts = []
        
        # Calculate average daily consumption, handle empty DataFrame case
        avg_daily = df['total_daily_sum'].mean() if not df['total_daily_sum'].empty else 0
        
        for idx, row in df.iterrows():
            date_str = row['Date'].strftime('%d-%m-%Y')
            
            # Rule 1: High Consumption
            # Alert if consumption is 50% higher than the average
            if avg_daily > 0 and row['total_daily_sum'] > 1.5 * avg_daily:
                alerts.append(f"High consumption alert on {date_str}: {row['total_daily_sum']:.2f} (Avg: {avg_daily:.2f})")
            
            # Rule 2: Zero Consumption
            # Alert if there was no consumption for a given day
            if row['total_daily_sum'] == 0:
                alerts.append(f"Zero consumption detected on {date_str}")
            
            # Rule 3: Sub-metering Spike
            # Alert if any sub-metering value exceeds a defined threshold
            for col in sub_meter_cols:
                if row[col] > 10000: # Threshold is adjustable
                    alerts.append(f"Sub-metering spike on {date_str} in '{col}': {row[col]}")
        
        # 5. Send Alerts via SNS if any were found
        if alerts:
            message = "\n".join(alerts)
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=f"⚠️ Billing Anomalies Detected in {latest_file}",
                Message=message
            )
            print(f"Alerts sent to SNS: {len(alerts)}")
        else:
            print("No anomalies detected.")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Processing complete.",
                "file_processed": latest_file,
                "records_analyzed": len(df),
                "alerts_found": len(alerts)
            })
        }
    
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        # Optionally, send an error notification via SNS
        # sns.publish(...)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }