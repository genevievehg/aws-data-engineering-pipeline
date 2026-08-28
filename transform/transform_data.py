import pandas as pd
import pycountry
import numpy as np
from io import BytesIO
import boto3
import os
from datetime import datetime


def get_dataframe_from_s3(bucket: str, object_key: str) -> pd.DataFrame:
    """
    Reads parquet data from S3 using boto3.

    object_key should be the table/prefix name, e.g. "staff".
    This function reads parquet files under raw/{object_key}/.
    """

    s3_client = boto3.client("s3")

    prefix = f"raw/{object_key}/"

    try:
        list_response = s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
        )

        objects = list_response.get("Contents", [])

        parquet_keys = [
            obj["Key"]
            for obj in objects
            if obj["Key"].endswith(".parquet")
        ]
        
        if not parquet_keys:
            raise FileNotFoundError(
                f"No parquet files found under s3://{bucket}/{prefix}"
        )

        dataframes = []

        for key in parquet_keys:
            response = s3_client.get_object(
                Bucket=bucket,
                Key=key,
            )

            parquet_bytes = response["Body"].read()
            df = pd.read_parquet(BytesIO(parquet_bytes))
            dataframes.append(df)

        return pd.concat(dataframes, ignore_index=True)

    except FileNotFoundError:
        raise
    except Exception as error:
        raise RuntimeError(
            f"Failed to read parquet data from s3://{bucket}/{prefix}"
        ) from error


def get_currency_name(currency_code: str) -> str:
    """Return the ISO currency name for a three-letter currency code."""
    currency = pycountry.currencies.get(alpha_3=currency_code)

    if currency is None:
        raise ValueError(
            f"{currency_code!r} is not a recognised currency code"
        )

    return currency.name


def transform_currency(df: pd.DataFrame) -> pd.DataFrame:
    """Transform source currency data into the dim_currency format.

    Standardises and validates currency codes, adds currency names,
    rejects missing values, and removes duplicate currencies.
    """
    cleaned_df = df.copy()

    cleaned_df = cleaned_df[
        [
            "currency_id",
            "currency_code",
        ]
    ]

    # Remove surrounding whitespace and standardise codes to uppercase.
    cleaned_df["currency_code"] = (
        cleaned_df["currency_code"]
        .str.strip()
        .str.upper()
    )

    # Check for missing/empty values before pycountry lookup.
    if (
        cleaned_df["currency_code"].isna()
        | cleaned_df["currency_code"].eq("")
    ).any():
        raise ValueError("currency_code cannot be missing")

    # get_currency_name will raise ValueError for invalid codes.
    cleaned_df["currency_name"] = cleaned_df["currency_code"].apply(
        get_currency_name
    )

    cleaned_df = cleaned_df.drop_duplicates(
        subset=["currency_code"],
        keep= "first",
    )

    return cleaned_df


def create_merged_staff_dataframe():
    """ 
    Loads raw staff and department tables.
    Drops rows with duplicate staff and department ids and merges raw tables.
    """
    # load dataframes
    staff_df = get_dataframe_from_s3(os.environ["INGEST_BUCKET"], 'staff')
    department_df = get_dataframe_from_s3(os.environ["INGEST_BUCKET"], 'department')

    # drop rows with duplicate staff ids and drop created_at and last_updated column from staff
    staff_df = staff_df.drop_duplicates(subset="staff_id", keep="last").drop(columns=['created_at', 'last_updated', 'extracted_ts'])
        
    # drop rows with duplicate department ids and drop created_at and last_updated column from department
    department_df = department_df.drop_duplicates(subset="department_id", keep="last").drop(columns=['manager', 'created_at', 'last_updated', 'extracted_ts'])

    # merge staff and department dfs and drop department_id column
    combined_df = pd.merge(staff_df, department_df, how="left", on=["department_id", "department_id"]).drop(columns=['department_id'])

    return combined_df


def transform_staff(df):
    """
    Any rows with missing data are dropped and column order is corrected.
    """
    # remove rows with missing data
    cleaned_df = df.replace(["NaN", "nan", "None", ""], np.nan).dropna()

    # drop duplicates
    cleaned_df = cleaned_df.drop_duplicates(subset="staff_id", keep="last")

    column_order = ['staff_id', 'first_name', 'last_name', 'department_name', 'location', 'email_address']
    cleaned_df = cleaned_df[column_order]

    return cleaned_df


def transform_location(df):
    """Transforms raw address data into the dim_location format.
    Drops rows with duplicate address ids, removes created_at and last_updated columns,
    and changes the "address_id" column to "location_id".
    Any rows with missing data are dropped.
    """
     # drop rows with duplicate address ids
    cleaned_df = df.drop_duplicates(subset="address_id", keep="last")

    # drop created_at and last_updated column
    cleaned_df = cleaned_df.drop(columns=['created_at', 'last_updated'])

    # rename "address_id" column to "location_id"
    cleaned_df = cleaned_df.rename(columns={'address_id': 'location_id'})

    # remove rows with missing data, except for address_line_2 and district columns
    cleaned_df = cleaned_df.replace(["NaN", "nan", "None", ""], np.nan).dropna(subset=["location_id", "address_line_1", "city", "postal_code", "country", "phone"])

    column_order = ["location_id", "address_line_1", "address_line_2", "district", "city", "postal_code", "country", "phone"]

    cleaned_df = cleaned_df[column_order]
    return cleaned_df


def create_merged_counterparty_dataframe() -> pd.DataFrame:
    """Create dim_counterparty by joining counterparty and address data."""
    counterparty_df = get_dataframe_from_s3(os.environ["INGEST_BUCKET"], 'counterparty')
    address_df = get_dataframe_from_s3(os.environ["INGEST_BUCKET"], 'address')
    dim_counterparty_df = counterparty_df.merge(
        address_df,
        how="left",
        left_on="legal_address_id",
        right_on="address_id",
    )

    dim_counterparty_df = dim_counterparty_df[
        [
            "counterparty_id",
            "counterparty_legal_name",
            "address_line_1",
            "address_line_2",
            "district",
            "city",
            "postal_code",
            "country",
            "phone",
        ]
    ].rename(columns={
        "address_line_1": "counterparty_legal_address_line_1",
        "address_line_2": "counterparty_legal_address_line_2",
        "district": "counterparty_legal_district",
        "city": "counterparty_legal_city",
        "postal_code": "counterparty_legal_postal_code",
        "country": "counterparty_legal_country",
        "phone": "counterparty_legal_phone_number",
    })

    return dim_counterparty_df


def transform_counterparty(df) -> pd.DataFrame:
    """Clean counterparty data."""
    df = df.copy()
    df = df.drop_duplicates()
    df.columns = df.columns.str.strip()

    text_cols = [
        "counterparty_legal_name",
        "counterparty_legal_address_line_1",
        "counterparty_legal_address_line_2",
        "counterparty_legal_district",
        "counterparty_legal_city",
        "counterparty_legal_postal_code",
        "counterparty_legal_country"
    ]

    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip().str.lower()

    if "counterparty_legal_phone_number" in df.columns:
        df["counterparty_legal_phone_number"] = df["counterparty_legal_phone_number"].astype("string").str.strip()

    df = df.replace("", pd.NA)
    df = df.dropna(subset=["counterparty_id"])

    df = df.drop_duplicates(
        subset=["counterparty_id"],
        keep="last",
    )

    df = df.reset_index(drop=True)

    return df


def transform_sales(df):
    """Transforms raw sales data into the fact_sales format.
    Splits both the created_at and last_updated columns into two columns for date and time.
    """
    # remove duplicates
    df.drop_duplicates(inplace=True)

    # add sales_record_id column
    df.insert(0, "sales_record_id", range(1, len(df) + 1))

    # split created_at into two separate date and time columns
    df['created_date'] = pd.to_datetime(df['created_at'], format="mixed").dt.date
    df['created_time'] = pd.to_datetime(df['created_at'], format="mixed").dt.time

    # split last_updated into two separate date and time columns
    df['last_updated_date'] = pd.to_datetime(df['last_updated'], format="mixed").dt.date
    df['last_updated_time'] = pd.to_datetime(df['last_updated'], format="mixed").dt.time

    # drop redundant created_at and last_updated columns
    cleaned_df = df.drop(columns=['created_at', 'last_updated'])

    # change agreed_delivery_date and agreed_payment_date column types to datetime
    cleaned_df['agreed_delivery_date'] = pd.to_datetime(cleaned_df['agreed_delivery_date'])
    cleaned_df['agreed_payment_date'] = pd.to_datetime(cleaned_df['agreed_payment_date'])

    # rename staff_id column
    cleaned_df = cleaned_df.rename(columns={'staff_id': 'sales_staff_id'})

    # remove rows with missing data
    cleaned_df = cleaned_df.replace(["NaN", "nan", "None", ""], np.nan).dropna()

    # correct column order
    column_order = ["sales_record_id", "sales_order_id", "created_date", 
        "created_time", "last_updated_date", "last_updated_time", "sales_staff_id", 
        "counterparty_id", "units_sold", "unit_price", "currency_id", "design_id",
        "agreed_payment_date", "agreed_delivery_date", "agreed_delivery_location_id" 
        ]
    cleaned_df = cleaned_df[column_order]
    
    return cleaned_df

def create_dim_date(start_date, end_date):

    """ this function create dim_date table 
       it takes the date range as start_date, end_date
       and returns df date 

    """

    dates = pd.date_range(
        start=start_date,
        end=end_date,
        freq="D"
    )

    dim_date = pd.DataFrame({
        "date_id": dates,
        "year": dates.year,
        "month": dates.month,
        "day": dates.day,
        "day_of_week": dates.dayofweek + 1,
        "day_name": dates.day_name(),
        "month_name": dates.month_name(),
        "quarter": dates.quarter
    })

    return dim_date

def transform_design(df):
   
    # drop unwanted columns
    cleaned_df = df.drop(
    columns=['created_at','last_updated']
    )
    # drop duplicate
    df = df.drop_duplicates(
    subset='design_id',
    keep='last'
    )

    column_order = ["design_id", "design_name", "file_location", "file_name"]
    cleaned_df = cleaned_df[column_order]

    return cleaned_df

def save_dataframe_to_s3_parquet(dataframe, bucket_name, table_name, extracted_ts):
    parquet_buffer = BytesIO()

    if extracted_ts is None:
        object_key = f"processed/{table_name}/{table_name}.parquet"
    else:
        timestamp = pd.to_datetime(extracted_ts).strftime("%Y%m%d_%H%M%S")
        object_key = f"processed/{table_name}/{table_name}_{timestamp}.parquet"


    dataframe.to_parquet(parquet_buffer, index=False)

    s3_client = boto3.client("s3")

    s3_client.put_object(
        Bucket=bucket_name, Key=object_key, Body=parquet_buffer.getvalue()
    )

    return object_key

def lambda_handler(event, context):

    raw_tables = ["sales_order", "design", "currency", "staff", "counterparty", "address"]

    target_tables = ["fact_sales", "dim_design", "dim_currency", "dim_staff", "dim_counterparty", "dim_location"]

    transform_functions = [transform_sales, transform_design, transform_currency, transform_staff, transform_counterparty, transform_location]

    extracted_ts = datetime.now().isoformat()

    for raw_table, target_table, function in zip(raw_tables, target_tables, transform_functions):
        if raw_table == "staff":
            df = create_merged_staff_dataframe()
        elif raw_table == "counterparty":
            df = create_merged_counterparty_dataframe()
        else:
            df = get_dataframe_from_s3(os.environ["INGEST_BUCKET"], raw_table)
        transformed_df = function(df)
        save_dataframe_to_s3_parquet(
            dataframe=transformed_df, 
            bucket_name=os.environ["PROCESSED_BUCKET"],
            table_name=target_table, 
            extracted_ts=extracted_ts
        )

    dim_date = create_dim_date("2022-01-01", "2029-12-31")
    save_dataframe_to_s3_parquet(
                dataframe=dim_date, 
                bucket_name=os.environ["PROCESSED_BUCKET"],
                table_name='dim_date', 
                extracted_ts=None
            )