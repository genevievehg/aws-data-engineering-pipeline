import boto3
import pandas as pd
from io import BytesIO

def get_dataframe_from_s3(bucket: str, object_key: str) -> pd.DataFrame:
    """
    Reads parquet data from S3 using boto3.

    object_key should be the table/prefix name, e.g. "staff".
    This function reads parquet files under raw/{object_key}/.
    """

    s3_client = boto3.client("s3")
    
    if bucket == 'js-final-proj-ingested-156470788909-dev':
        prefix = f"raw/{object_key}/"
    if bucket == 'js-final-proj-processed-156470788909-dev':
        prefix = f"processed/{object_key}/"

    try:
        get_last_modified = lambda obj: int(obj['LastModified'].strftime('%s'))

        list_objs = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)

        objs = list_objs['Contents']

        obj_count = list_objs['KeyCount']

        last_added = [obj['Key'] for obj in sorted(objs, key=get_last_modified)][0]    

        if not last_added:
            raise FileNotFoundError(
                f"No parquet files found under s3://{bucket}/{prefix}"
        )

        response = s3_client.get_object(
                Bucket=bucket,
                Key=last_added,
            )

        parquet_bytes = response["Body"].read()
        df = pd.read_parquet(BytesIO(parquet_bytes))
        print(f'File Count in {prefix}: {obj_count}')
        print(f'File: {last_added}')
        
        return df

    except FileNotFoundError:
        raise
    except Exception as error:
        raise RuntimeError(
            f"Failed to read parquet data from s3://{bucket}/{prefix}"
        ) from error
        
        
if __name__ == "__main__":
    print("Which s3 bucket do you want to look in? \n Options = 'ingested' or 'processed'")
    requested_bucket = input()
    while requested_bucket != 'ingested' and requested_bucket != 'processed':
        print("Try again. Which s3 bucket do you want to look in?")
        requested_bucket = input()
    if requested_bucket == 'ingested':
        bucket = 'js-final-proj-ingested-156470788909-dev'
        tables = [
            "sales_order",
            "design",
            "currency",
            "staff",
            "counterparty",
            "address",
            "department",
            "purchase_order",
            "payment_type",
            "payment",
            "transaction"
        ]
        print(f'Table to look up? \nOptions = {tables}')
        table = input()
        result = get_dataframe_from_s3(bucket, table)
        print(result)
        print(result.dtypes)
    else:
        bucket = 'js-final-proj-processed-156470788909-dev'
        tables = [
            "fact_sales", 
            "dim_design", 
            "dim_currency", 
            "dim_staff", 
            "dim_counterparty", 
            "dim_location",
            "dim_date"]
        print(f'Table to look up? \nOptions = {tables}')
        table = input()
        result = get_dataframe_from_s3(bucket, table)
        print(result)
        print(result.dtypes)