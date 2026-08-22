import boto3
import json
import os
from botocore.exceptions import ClientError
import psycopg2
import pandas as pd
from io import BytesIO, StringIO
from psycopg2 import sql

sql_schema = """
Drop TABLE IF EXISTS fact_sales CASCADE;
Drop TABLE IF EXISTS dim_date;
Drop TABLE IF EXISTS dim_staff;
Drop TABLE IF EXISTS dim_location;
Drop TABLE IF EXISTS dim_currency;
Drop TABLE IF EXISTS dim_design;
Drop TABLE IF EXISTS dim_counterparty;


CREATE TABLE fact_sales (
  sales_record_id SERIAL PRIMARY KEY,
  sales_order_id INT NOT NULL,
  created_date DATE NOT NULL,
  created_time TIME NOT NULL,
  last_updated_date DATE NOT NULL,
  last_updated_time TIME NOT NULL,
  sales_staff_id INT NOT NULL,
  counterparty_id INT NOT NULL,
  units_sold INT NOT NULL,
  unit_price NUMERIC(10, 2) NOT NULL,
  currency_id INT NOT NULL,
  design_id INT NOT NULL,
  agreed_payment_date DATE NOT NULL,
  agreed_delivery_date DATE NOT NULL,
  agreed_delivery_location_id INT NOT NULL
);

CREATE TABLE dim_date (
  date_id DATE PRIMARY KEY NOT NULL,
  year INT NOT NULL,
  month INT NOT NULL,
  day INT NOT NULL,
  day_of_week INT NOT NULL,
  day_name VARCHAR NOT NULL,
  month_name VARCHAR NOT NULL,
  quarter INT NOT NULL
);

CREATE TABLE dim_staff (
  staff_id INT PRIMARY KEY NOT NULL,
  first_name VARCHAR NOT NULL,
  last_name VARCHAR NOT NULL,
  department_name VARCHAR NOT NULL,
  location VARCHAR NOT NULL,
  email_address VARCHAR NOT NULL
);

CREATE TABLE dim_location (
  location_id INT PRIMARY KEY NOT NULL,
  address_line_1 VARCHAR NOT NULL,
  address_line_2 VARCHAR,
  district VARCHAR,
  city VARCHAR NOT NULL,
  postal_code VARCHAR NOT NULL,
  country VARCHAR NOT NULL,
  phone VARCHAR NOT NULL
);

CREATE TABLE dim_currency (
  currency_id INT PRIMARY KEY NOT NULL,
  currency_code VARCHAR NOT NULL,
  currency_name VARCHAR NOT NULL
);

CREATE TABLE dim_design (
  design_id INT PRIMARY KEY NOT NULL,
  design_name VARCHAR NOT NULL,
  file_location VARCHAR NOT NULL,
  file_name VARCHAR NOT NULL
);

CREATE TABLE dim_counterparty (
  counterparty_id INT PRIMARY KEY NOT NULL,
  counterparty_legal_name VARCHAR NOT NULL,
  counterparty_legal_address_line_1 VARCHAR NOT NULL,
  counterparty_legal_address_line_2 VARCHAR,
  counterparty_legal_district VARCHAR,
  counterparty_legal_city VARCHAR NOT NULL,
  counterparty_legal_postal_code VARCHAR NOT NULL,
  counterparty_legal_country VARCHAR NOT NULL,
  counterparty_legal_phone_number VARCHAR NOT NULL
);

ALTER TABLE fact_sales ADD FOREIGN KEY (created_date) REFERENCES dim_date (date_id) DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE fact_sales ADD FOREIGN KEY (last_updated_date) REFERENCES dim_date (date_id) DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE fact_sales ADD FOREIGN KEY (sales_staff_id) REFERENCES dim_staff (staff_id) DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE fact_sales ADD FOREIGN KEY (counterparty_id) REFERENCES dim_counterparty (counterparty_id) DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE fact_sales ADD FOREIGN KEY (currency_id) REFERENCES dim_currency (currency_id) DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE fact_sales ADD FOREIGN KEY (design_id) REFERENCES dim_design (design_id) DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE fact_sales ADD FOREIGN KEY (agreed_payment_date) REFERENCES dim_date (date_id) DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE fact_sales ADD FOREIGN KEY (agreed_delivery_date) REFERENCES dim_date (date_id) DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE fact_sales ADD FOREIGN KEY (agreed_delivery_location_id) REFERENCES dim_location (location_id) DEFERRABLE INITIALLY IMMEDIATE;
"""

def get_secret(secret_name):

    region_name = "eu-west-2"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        return json.loads(get_secret_value_response["SecretString"])

    except ClientError as e:
        raise e


def load_schema(secret):

    with psycopg2.connect(
        user=os.environ["USER"], 
        password = secret["password"], 
        dbname=os.environ["WAREHOUSE_NAME"], 
        host=os.environ["HOST"], 
        port=os.environ["PORT"],
    ) as conn:

        with conn.cursor() as cur:
            cur.execute(sql_schema)


def get_dataframe_from_s3(bucket: str, object_key: str) -> pd.DataFrame:
    """
    Reads parquet data from S3 using boto3 and returns most recent file.

    object_key should be the table/prefix name, e.g. "staff".
    This function reads parquet files under processed/{object_key}/.
    """

    s3_client = boto3.client("s3")

    prefix = f"processed/{object_key}/"

    try:
        list_response = s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
        )

        objects = list_response.get("Contents", [])

        parquet_objects = [obj for obj in objects if obj["Key"].endswith(".parquet")]

        if not parquet_objects:
            raise FileNotFoundError(
                f"No parquet files found under s3://{bucket}/{prefix}"
        )

        most_recent = max(parquet_objects, key=lambda obj: obj["LastModified"])

      
        response = s3_client.get_object(
                Bucket=bucket,
                Key=most_recent['Key'],
            )

        parquet_bytes = response["Body"].read()
        df = pd.read_parquet(BytesIO(parquet_bytes))

        return df

    except Exception as error:
        raise RuntimeError(
            f"Failed to read parquet data from s3://{bucket}/{prefix}"
        ) from error

    
def seed_table_in_db(secret, table, df):
    
    with psycopg2.connect(
            user=os.environ["USER"], 
            password = secret["password"], 
            dbname=os.environ["WAREHOUSE_NAME"], 
            host=os.environ["HOST"], 
            port=os.environ["PORT"],
        ) as conn:

        with conn.cursor() as cur:

            csv_buffer = StringIO()
            df.to_csv(csv_buffer, index=False, header=False, na_rep="\\N")
            csv_buffer.seek(0)

            copy_sql = sql.SQL("""
            COPY {} ({})
            FROM STDIN
            WITH (FORMAT CSV)
            """).format(sql.Identifier(table),sql.SQL(", ").join(sql.Identifier(column) for column in df.columns))

            cur.copy_expert(
                copy_sql,
                csv_buffer
            )

        conn.commit()



def lambda_handler(event, context):
    
    secret = get_secret(os.environ["WAREHOUSE_SECRET_NAME"])

    load_schema(secret)

    tables = [
            "dim_counterparty",
            "dim_currency",
            "dim_date",
            "dim_design",
            "dim_location",
            "dim_staff",
            "fact_sales"
        ]
    
    for table in tables:
      df = get_dataframe_from_s3(os.environ["PROCESSED_BUCKET"], table)
      seed_table_in_db(secret, table, df)