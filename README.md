# Jurassic Sparks Data Engineering Pipeline

An AWS-based ETL pipeline that extracts data from the ToteSys PostgreSQL database, stores raw and transformed data in Amazon S3, and loads analytical data into an Amazon RDS PostgreSQL warehouse.

## Architecture

```text
ToteSys PostgreSQL
        |
        v
EventBridge Scheduler
        |
        v
  Step Functions
        |
        v
   Ingest Lambda
        |
        v
 Raw S3 (Parquet)
        |
        v
 Transform Lambda
        |
        v
Processed S3 (Parquet)
        |
        v
    Load Stage
        |
        v
RDS PostgreSQL Warehouse
        |
        v
Jupyter / Analytics
```

The pipeline is scheduled to run every 30 minutes.

> Note: the automated load stage is still being completed and provisioned.

---

## Data Warehouse

The transformed data is remodelled into a star schema.

### Fact table

- `fact_sales`

### Dimension tables

- `dim_date`
- `dim_staff`
- `dim_location`
- `dim_currency`
- `dim_design`
- `dim_counterparty`

---

## Technology

| Layer | Technology |
| --- | --- |
| Source | PostgreSQL |
| Extraction | Python, psycopg2, Pandas, AWS Lambda |
| Transformation | Python, Pandas |
| Storage | Amazon S3, Parquet |
| Warehouse | Amazon RDS PostgreSQL |
| Orchestration | AWS Step Functions |
| Scheduling | Amazon EventBridge Scheduler |
| Secrets | AWS Secrets Manager |
| Monitoring | Amazon CloudWatch, SNS |
| Infrastructure | Terraform |
| CI/CD | GitHub Actions |
| Analysis | Jupyter, Pandas, Plotly |

---

## Repository Structure

```text
.
├── analysis/              # Jupyter analysis and visualisations
├── ingestion/             # Source database extraction
├── lambda_layers/         # Lambda dependency definitions and build script
├── load/                  # Warehouse loading utilities
├── schema/                # Warehouse schema creation
├── scripts/               # Local scripts for accessing and inspecting AWS resources
├── terraform/             # Main AWS infrastructure
├── terraform-bootstrap/   # Remote Terraform state infrastructure
├── tests/                 # Unit tests
├── transform/             # Data transformation
├── requirements.txt
├── requirements_dev.txt
└── README.md
```

---

## Requirements

Before running the project locally you will need:

- Python 3.13
- Docker
- Terraform
- AWS CLI
- AWS credentials with access to the project AWS account

---

## Local Setup

Clone the repository:

```bash
git clone https://github.com/jurassic-spark/de-final-project.git
cd de-final-project
```

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Upgrade pip and install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements_dev.txt
```

Run the tests:

```bash
python -m pytest tests -v
```

---

## Lambda Dependencies

Lambda dependencies are built using Docker so that compiled packages are compatible with the AWS Lambda Python 3.13 runtime.

Build the Lambda layers from the repository root:

```bash
bash lambda_layers/build.sh
```

This generates the dependency directories used by Terraform when creating the Lambda layer ZIP packages.

Generated build directories and Terraform deployment packages are ignored by Git and should not be committed.

---

## Terraform

The project uses Terraform to provision its AWS infrastructure.

### Shared Terraform State

The main Terraform project uses a shared remote S3 backend.

For normal development, where the backend already exists:

```bash
terraform -chdir=terraform init
terraform -chdir=terraform validate
terraform -chdir=terraform plan
```

Always review the Terraform plan before applying changes.

If the backend configuration has changed:

```bash
terraform -chdir=terraform init -reconfigure
```

If Terraform state needs to be migrated:

```bash
terraform -chdir=terraform init -migrate-state
```

### Terraform Backend Bootstrap

The S3 bucket used to store Terraform state is managed separately in:

```text
terraform-bootstrap/
```

This bootstrap project is only required when creating the shared Terraform backend from scratch.

```bash
terraform -chdir=terraform-bootstrap init
terraform -chdir=terraform-bootstrap validate
terraform -chdir=terraform-bootstrap plan
terraform -chdir=terraform-bootstrap apply
```

Once the backend exists, initialise the main infrastructure:

```bash
terraform -chdir=terraform init
```

---

## Pipeline Flow

### 1. Extract

Amazon EventBridge Scheduler starts the pipeline every 30 minutes through AWS Step Functions.

The ingestion Lambda:

1. retrieves ToteSys database credentials from AWS Secrets Manager
2. connects to the source PostgreSQL database
3. extracts source tables
4. converts the data to Parquet
5. writes the files to the ingestion S3 bucket

Raw files are stored using the structure:

```text
raw/<table>/<table>_<timestamp>.parquet
```

Example:

```text
raw/staff/staff_20260821_103000.parquet
```

---

### 2. Transform

The transform Lambda reads raw Parquet data from the ingestion S3 bucket.

The source tables are cleaned, joined and remodelled into fact and dimension tables.

The transformed data currently includes:

```text
fact_sales
dim_date
dim_staff
dim_location
dim_currency
dim_design
dim_counterparty
```

Processed data is written to the processed S3 bucket using the structure:

```text
processed/<table>/<table>_<timestamp>.parquet
```

For example:

```text
processed/dim_staff/dim_staff_20260821_103000.parquet
```

---

### 3. Load

Processed Parquet data is intended to be loaded into the Amazon RDS PostgreSQL warehouse.

The warehouse credentials are generated and managed by Amazon RDS through AWS Secrets Manager.

The load stage is currently being completed.

The intended flow is:

```text
Processed S3
     |
     v
Load Lambda
     |
     v
RDS PostgreSQL
```

---

## Orchestration

Amazon EventBridge Scheduler currently starts an AWS Step Functions state machine every 30 minutes.

The target architecture is:

```text
EventBridge Scheduler
        |
        v
   Step Functions
        |
        +----> Ingest Lambda
        |
        +----> Transform Lambda
        |
        +----> Load Lambda
        |
        v
      Success
```

This allows each pipeline stage to run only after the previous stage has completed successfully.

Retries and failure handling can also be managed centrally through Step Functions.

---

## AWS Infrastructure

Terraform provisions the main infrastructure required by the pipeline, including:

- S3 code bucket
- S3 ingestion/raw-data bucket
- S3 processed-data bucket
- AWS Lambda functions
- Lambda dependency layers
- IAM roles and policies
- AWS Secrets Manager access
- Amazon RDS PostgreSQL warehouse
- security groups
- VPC networking
- Secrets Manager VPC endpoint
- AWS Step Functions
- EventBridge Scheduler
- CloudWatch logging and alarms
- SNS error notifications

The S3 buckets use versioning and public-access blocking.

The RDS warehouse is configured as development infrastructure using a small Single-AZ PostgreSQL instance.

---

## Secrets

Database credentials are not stored in the application source code.

The pipeline uses AWS Secrets Manager for:

- ToteSys source database credentials
- RDS warehouse credentials

The RDS master password is generated and managed automatically by AWS.

---

## Monitoring

Amazon CloudWatch is used for Lambda logging and pipeline monitoring.

The ingestion stage currently includes:

- CloudWatch log collection
- an error metric filter
- a CloudWatch alarm
- SNS email notifications

Future monitoring should extend this to the transform and load stages and to Step Functions pipeline failures.

---

## Analysis

The `analysis/` directory contains Jupyter-based analysis and visualisations created from the warehouse data.

The analysis workflow uses tools including:

- Jupyter
- Pandas
- SQLAlchemy
- Plotly
- PostgreSQL queries

This demonstrates how the resulting star schema can be queried for analytical use cases after the ETL pipeline has populated the warehouse.

---

## CI/CD

GitHub Actions runs automated tests and Terraform checks.

### Tests

The test workflow installs the development dependencies and runs the Python test suite.

```bash
python -m pytest tests -v
```

### Terraform Workflow

For pull requests, the Terraform workflow:

```text
Checkout repository
        |
        v
Setup Python 3.13
        |
        v
Build Lambda layers
        |
        v
Terraform Init
        |
        v
Terraform Validate
        |
        v
Terraform Plan
```

On a push or merge to `main`, the workflow can also run:

```text
Terraform Apply
```

Infrastructure changes should therefore be reviewed carefully before merging a pull request into `main`.

---

## Known Limitations / Future Improvements

The project is still under active development.

Current improvements include:

- provision the automated Load Lambda
- connect the load stage to processed S3 and the RDS warehouse
- extend Step Functions to orchestrate the full extract → transform → load workflow
- extend CloudWatch alarms to transform, load and Step Functions

---

## Current Development Architecture

```text
                    EventBridge
                        |
                        v
                  Step Functions
                        |
                        v
                   Ingest Lambda
                        |
       +----------------+----------------+
       |                                 |
       v                                 v
ToteSys PostgreSQL                 Secrets Manager
       |
       v
   Raw S3 Bucket
       |
       v
 Transform Lambda
       |
       v
Processed S3 Bucket
       |
       v
    Load Stage
       |
       v
RDS PostgreSQL Warehouse
       |
       v
 Jupyter / Plotly Analysis
```