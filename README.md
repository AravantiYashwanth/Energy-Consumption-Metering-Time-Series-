
# ⚡ Energy Consumption Metering (Time-Series)

### 📘 Overview
**Energy Consumption Metering** is an **end-to-end batch data pipeline** built on **AWS**, designed to process smart electricity meter readings for **billing insights**, **anomaly detection**, and **interactive analytics**.  
The pipeline automatically ingests raw energy data, performs nightly ETL on **Databricks**, stores processed results in **Amazon S3**, and delivers them to **Athena**, **QuickSight**, and **API Gateway** for querying and visualization.

It provides:
1. **Automated Billing Reports** — daily and monthly consumption summaries.  
2. **Anomaly Detection Alerts** — near-real-time monitoring via SNS.  
3. **Interactive Dashboards** — visual analytics in QuickSight and Athena.

---

## 🏗️ Solution Architecture
```
Smart Meter CSV (Readings)
│
▼
Amazon S3 (Raw Zone)
│
▼
Databricks ETL (Nightly Batch)
│
▼
Amazon S3 (Processed Zone)
│
├──▶ AWS Lambda → Amazon SNS (Anomaly Alerts)
├──▶ AWS Lambda → API Gateway (REST API for Billing)
└──▶ Amazon Athena → QuickSight (Dashboards)

```
---

## ⚙️ Technologies Used

| Category | Technologies |
|-----------|--------------|
| **Data Ingestion** | Amazon S3 |
| **Data Processing** | Databricks, PySpark, Pandas |
| **Data Storage** | Amazon S3 (Raw + Processed zones) |
| **Query & Visualization** | Amazon Athena, Amazon QuickSight |
| **Automation & APIs** | AWS Lambda, API Gateway, Amazon SNS |
| **Languages / Libraries** | Python, Boto3, Pandas, PySpark, SQL |

---

## 🔄 Pipeline Breakdown

### 🔹 Step 1: Data Ingestion
Raw electricity readings are uploaded as CSV files into an **S3 raw zone**:
`s3://electricity-meter-readings/raw/Readings.csv`

Each record represents minute-level measurements of voltage, current, and sub-metering data from household meters.

---

### 🔹 Step 2: ETL with Databricks (Batch Processing)

A **Databricks notebook (Nightly-ETL-Process)** performs:
1. **Extract:** Reads raw CSV files from S3.  
2. **Transform:** Cleans missing values, converts data types, and aggregates readings to daily level.  
3. **Load:** Writes final aggregated and billing-ready data to the processed S3 bucket:
`s3://electricity-meter-aggregated-readings/data/`


**Key Transformations:**
- Daily mean of power and voltage.
- Min/Max voltage per day.
- Sub-meter energy totals.
- Peak/Off-Peak billing (₹8.5 and ₹5.0 rates).
- 3-sigma anomaly detection for abnormal energy use.

---

### 🔹 Step 3: Automated Billing via REST API

A **Lambda function** provides monthly billing summaries via **API Gateway**:

```bash
GET https://<api-id>[.execute-api.ap-south-1.amazonaws.com/bills?month=2007-04](https://.execute-api.ap-south-1.amazonaws.com/bills?month=2007-04)
````

**Lambda Logic:**

1.  Reads the latest billing CSV from S3.
2.  Filters by month (YYYY-MM).
3.  Returns JSON-formatted daily billing data.

### 🔹 Step 4: Anomaly Detection & Alerts (Rule-Based)

A second Lambda function runs after ETL to scan for anomalies and send alerts via **SNS**.

**Rules:**

  - 🔺 High consumption (\>150% of average)
  - ⚠️ Zero consumption
  - ⚡ Sub-meter spikes (\>10,000 Wh)

**Alert Flow:**
S3 (Processed) → Lambda → SNS → Email/SMS Subscribers

### 🔹 Step 5: Analytical Query Layer (Athena)

Processed data stored in S3 is queried directly using **Amazon Athena**.

**Athena Table Example:**

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS energy_bills.daily_summary (
    date STRING,
    avg_Global_active_power DOUBLE,
    avg_Voltage DOUBLE,
    total_Sub_metering_1 DOUBLE,
    total_Sub_metering_2 DOUBLE,
    total_Sub_metering_3 DOUBLE,
    total_daily_sum DOUBLE,
    anomaly_flag BOOLEAN,
    peak_charge DOUBLE,
    offpeak_charge DOUBLE,
    total_charge DOUBLE
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
LOCATION 's3://electricity-meter-aggregated-readings/data/'
TBLPROPERTIES ('skip.header.line.count'='1');
```

### 🔹 Step 6: Visualization with QuickSight

**QuickSight** connects directly to Athena.

**Dashboards visualize:**

  - Daily & Monthly consumption.
  - Voltage and intensity trends.
  - Billing comparisons across months.
  - Highlighted anomalies and alerts.

-----

## 🧠 Key Features
 
✅ Automated nightly ETL using Databricks   
✅ Peak and Off-Peak billing logic   
✅ 3-Sigma anomaly detection   
✅ Serverless REST API for on-demand bills   
✅ SNS alert notifications for anomalies  
✅ Queryable and visual insights via Athena & QuickSight   
✅ Data partitioning for optimized cost & query performance   

-----

## ⚔️ Challenges & Solutions

| Challenge | Solution |
|-----------|----------|
| Large CSV file (200K+ rows) caused memory spikes | Streamed ingestion and Pandas chunk processing |
| Athena schema mismatch (string vs numeric) | Created clean folder with casted DOUBLE types |
| Frequent false positives in anomaly detection | Implemented statistical 3-sigma threshold and rule-based filters |
| Duplicate uploads overwriting old data | Timestamped ETL outputs (`billing_agg_YYYY-MM-DD_HH-MM-SS.csv`) |

-----

## 📂 Project Structure

```
Energy-Consumption-Metering/
│
├── Nightly-ETL-Process.py      # Databricks ETL notebook
├── billing_api_lambda.py       # REST API Lambda function
├── anomaly_alert_lambda.py     # SNS alerting Lambda
├── readings.csv                # Sample raw dataset
├── architecture_diagram.png    # Pipeline visualization
└── README.md
```

-----

## 📊 Sample Athena Query

```sql
SELECT 
  TRY_CAST(date AS DATE) AS consumption_date,
  avg_Global_active_power,
  total_daily_sum,
  peak_charge,
  offpeak_charge,
  total_charge
FROM energy_bills.daily_summary
WHERE TRY_CAST(date AS DATE)
      BETWEEN DATE '2007-04-01' AND DATE '2007-04-30'
ORDER BY consumption_date;
```

-----

## 💡 Learnings

  - Building scalable batch pipelines with AWS serverless tools.
  - Applying ETL design best practices with Databricks and S3 partitioning.
  - Implementing rule-based anomaly detection using Lambda & SNS.
  - Exposing data insights via APIs and BI dashboards.

-----

## 🧰 Tools & Services

• AWS S3   
• Databricks    
• AWS Lambda    
• Amazon Athena    
• Amazon SNS    
• Amazon QuickSight    
• API Gateway    
• PySpark    
• Pandas    
• Boto3   

-----

## 🏁 Conclusion

This project demonstrates how to design a scalable, automated energy data processing system using AWS.

It transforms raw IoT-style meter readings into actionable insights — delivering bills, alerts, and analytics — all through a serverless, cost-optimized data architecture.

-----

## 👨‍💻 Author

**A. Yashwanth**

Aspiring Data Engineer | Python & AWS Enthusiast

📧 www.linkedin.com/in/yashwantharavanti
