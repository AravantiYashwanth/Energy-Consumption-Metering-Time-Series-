import json
import boto3
import pandas as pd

# ------------------ S3 Configuration ------------------
BUCKET_NAME = "electricity-meter-aggregated-readings"
S3_PREFIX = "data/billing_agg"
s3 = boto3.client('s3')

# ------------------ Lambda Handler ------------------
def lambda_handler(event, context):
    try:
        # Debug: log incoming event
        print("Event received:", event)
        
        # Get 'month' parameter (format: YYYY-MM)
        month = (event.get('queryStringParameters') or {}).get('month')
        if not month:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Month parameter is required, e.g., ?month=2025-10"})
            }
        
        # List all billing files in S3
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=S3_PREFIX)
        if 'Contents' not in response:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "No billing files found in S3"})
            }
        
        # Pick the latest file based on LastModified
        latest_file = max(response['Contents'], key=lambda x: x['LastModified'])['Key']
        print("Latest billing file:", latest_file)
        
        # Load CSV into DataFrame
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=latest_file)
        df = pd.read_csv(obj['Body'])
        
        # Ensure 'Date' column exists and parse it
        if 'Date' not in df.columns:
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "CSV missing 'Date' column"})
            }
        
        df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Date'])
        
        if df.empty:
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "No valid dates found in CSV"})
            }
        
        # Fill missing billing columns with 0
        billing_cols = [
            'total_Sub_metering_1', 'total_Sub_metering_2', 'total_Sub_metering_3',
            'avg_submetering_value', 'total_daily_sum',
            'peak_charge', 'offpeak_charge', 'total_charge'
        ]
        
        for col in billing_cols:
            if col not in df.columns:
                df[col] = 0
        
        df[billing_cols] = df[billing_cols].fillna(0)
        
        # Filter data for requested month
        monthly_df = df[df['Date'].dt.strftime('%Y-%m') == month]
        
        if monthly_df.empty:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": f"No billing data found for month {month}"})
            }
        
        # Select relevant columns and format date
        monthly_df = monthly_df[['Date'] + billing_cols]
        monthly_df['Date'] = monthly_df['Date'].dt.strftime('%d-%m-%Y') # Format for JSON
        
        # Return JSON response
        return {
            "statusCode": 200,
            "body": monthly_df.to_json(orient='records')
        }
    
    except Exception as e:
        print("Error:", str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error", "details": str(e)})
        }