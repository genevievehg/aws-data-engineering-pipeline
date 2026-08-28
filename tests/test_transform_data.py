from unittest.mock import MagicMock, patch
import boto3
from moto import mock_aws
from io import BytesIO
import pycountry
import pytest
import pandas as pd
from unittest import mock
from transform.transform_data import (
    get_dataframe_from_s3,
    get_currency_name,
    transform_currency,
    transform_staff,
    transform_location,
    transform_sales,
    lambda_handler
)

@mock_aws
def test_get_dataframe_from_s3_returns_dataframe():
    parquet_buffer = BytesIO()
    mock_df = pd.DataFrame(
            {
                "currency_id": [1, 2],
                "currency_code": ["GBP", "USD"],
                "created_at": ["2026-01-01", "2026-01-02"],
                "last_updated": ["2026-01-03", "2026-01-04"],
            }
        )
    mock_df.to_parquet(parquet_buffer, index=False)
    s3_client = boto3.client("s3", region_name="us-east-1")
    s3_client.create_bucket(Bucket="test_bucket")
    s3_client.put_object(Bucket="test_bucket", Key="raw/currency/test.parquet", Body=parquet_buffer.getvalue())

    result = get_dataframe_from_s3("test_bucket", "currency")
    assert isinstance(result, pd.DataFrame)


@mock_aws
def test_get_dataframe_from_s3_handles_missing_file_errors():
    s3_client = boto3.client("s3", region_name="us-east-1")
    s3_client.create_bucket(Bucket="test_bucket")
    s3_client.put_object(Bucket="test_bucket", Key="raw/currency/test.txt", Body="test")
    with pytest.raises(FileNotFoundError) as e:
        get_dataframe_from_s3("test_bucket", "currency")
    assert e.value.args[0] == "No parquet files found under s3://test_bucket/raw/currency/"


@mock_aws
def test_get_dataframe_from_s3_handles_access_errors():
    with pytest.raises(RuntimeError) as e:
        get_dataframe_from_s3("test_bucket", "currency")
    assert e.value.args[0] == "Failed to read parquet data from s3://test_bucket/raw/currency/"
     

def test_get_currency_name_returns_currency_name():
    assert get_currency_name("GBP") == "Pound Sterling"


def test_transform_currency_only_contains_required_columns():
    mock_df = pd.DataFrame(
        {
            "currency_id": [1, 2],
            "currency_code": ["GBP", "USD"],
            "created_at": ["2026-01-01", "2026-01-02"],
            "last_updated": ["2026-01-03", "2026-01-04"],
        }
    )

    result = transform_currency(mock_df)

    assert isinstance(result, pd.DataFrame)

    assert list(result.columns) == [
        "currency_id",
        "currency_code",
        "currency_name",
    ]


def test_transform_currency_raises_error_if_missing_currency_code():
    mock_df = pd.DataFrame(
        {
            "currency_id": [1, 2],
            "currency_code": ["", ""],
            "created_at": ["2026-01-01", "2026-01-02"],
            "last_updated": ["2026-01-03", "2026-01-04"],
        }
    )

    with pytest.raises(ValueError):
        transform_currency(mock_df)

def test_transform_currency_raises_error_for_invalid_code():
    mock_df = pd.DataFrame(
            {
                "currency_id": [1, 2],
                "currency_code": ["Apple", "Banana"],
                "created_at": ["2026-01-01", "2026-01-02"],
                "last_updated": ["2026-01-03", "2026-01-04"],
            }
        )

    with pytest.raises(ValueError):
            transform_currency(mock_df)

def test_transform_currency_standardises_currency_codes():
    mock_df = pd.DataFrame(
            {
                "currency_id": [1, 2],
                "currency_code": ["gbp", "usd"],
                "created_at": ["2026-01-01", "2026-01-02"],
                "last_updated": ["2026-01-03", "2026-01-04"],
            }
        )

    result_df = transform_currency(mock_df)

    assert result_df["currency_code"][0] == "GBP"
    assert result_df["currency_code"][1] == "USD"

def test_transform_staff_returns_df():
    mock_df = pd.DataFrame(
                {
                    "staff_id": [1, 2],
                    "first_name": ["jane", "doe"],
                    "last_name": ["john", "smith"],
                    "email_address": ["janedoe@emailaddress.com", "johnsmith@emailaddress.com"],
                    "department_name": ["Finance", "Comms"],
                    "location": ["Leeds", "Manchester"],
                }
            )
    
    result = transform_staff(mock_df)
    assert isinstance(result, pd.DataFrame)
    assert len(result.columns) == 6
    assert 'staff_id' in result.columns
    assert 'first_name' in result.columns
    assert 'last_name' in result.columns
    assert 'department_name' in result.columns
    assert 'location' in result.columns
    assert 'email_address' in result.columns


def test_transform_staff_returns_df_with_no_duplicates():
    mock_df = pd.DataFrame(
                    {
                        "staff_id": [1, 1],
                        "first_name": ["jane", "doe"],
                        "last_name": ["john", "smith"],
                        "email_address": ["janedoe@emailaddress.com", "johnsmith@emailaddress.com"],
                        "department_name": ["Finance", "Comms"],
                        "location": ["Leeds", "Manchester"],
                    }
                )
    
    result = transform_staff(mock_df)
    repeated_staff_ids = result[result["staff_id"].duplicated(keep=False)]
    assert len(repeated_staff_ids) == 0

def test_transform_staff_removes_rows_with_null_values():
    mock_df = pd.DataFrame(
                    {
                        "staff_id": [1, 2],
                        "first_name": ["jane", "doe"],
                        "last_name": ["", "smith"],
                        "email_address": ["janedoe@emailaddress.com", "johnsmith@emailaddress.com"],
                        "department_name": ["Finance", "Comms"],
                        "location": ["Leeds", "Manchester"],
                    }
                )
    
    result = transform_staff(mock_df)
    assert len(result) == 1

def test_transform_location_returns_df():
    mock_df = pd.DataFrame(
            {
                "address_id": [1, 2],
                "address_line_1": ["1 new street", "flat 1"],
                "address_line_2": ["", "2 new street"],
                "district": ["new district", "old district"],
                "city": ["london", "leeds"],
                "postal_code": ["L58362", "LE 84 2152"],
                "country": ["UK", "UK"],
                "phone": ["542 217832 12", "323 437811 328"],
                "created_at": ["2026-01-01", "2026-01-02"],
                "last_updated": ["2026-01-03", "2026-01-04"],
            }
        )
    result = transform_location(mock_df)
    assert isinstance(result, pd.DataFrame)
    assert len(result.columns) == 8
    assert "location_id" in result.columns
    assert "address_line_1" in result.columns
    assert "address_line_2" in result.columns
    assert "district" in result.columns
    assert "city" in result.columns
    assert "postal_code" in result.columns
    assert "country" in result.columns
    assert "phone" in result.columns

def test_transform_location_returns_df_with_no_duplicates():
    mock_df = pd.DataFrame(
            {
                "address_id": [1, 1],
                "address_line_1": ["1 new street", "flat 1"],
                "address_line_2": ["", "2 new street"],
                "district": ["new district", "old district"],
                "city": ["london", "leeds"],
                "postal_code": ["L58362", "LE 84 2152"],
                "country": ["UK", "UK"],
                "phone": ["542 217832 12", "323 437811 328"],
                "created_at": ["2026-01-01", "2026-01-02"],
                "last_updated": ["2026-01-03", "2026-01-04"],
            }
        )
    result = transform_location(mock_df)
    repeated_rows = result[result["location_id"].duplicated(keep=False)]
    assert len(repeated_rows) == 0
    assert len(result) == 1

def test_transform_location_removes_rows_with_missing_values():
    mock_df = pd.DataFrame(
            {
                "address_id": [1, 2],
                "address_line_1": ["1 new street", ""],
                "address_line_2": ["", "2 new street"],
                "district": ["new district", "old district"],
                "city": ["london", "leeds"],
                "postal_code": ["L58362", "LE 84 2152"],
                "country": ["UK", "UK"],
                "phone": ["542 217832 12", "323 437811 328"],
                "created_at": ["2026-01-01", "2026-01-02"],
                "last_updated": ["2026-01-03", "2026-01-04"],
            }
        )
    result = transform_location(mock_df)
    repeated_rows = result[result["location_id"].duplicated(keep=False)]
    assert len(repeated_rows) == 0
    assert len(result) == 1

def test_transform_sales_returns_df():
    mock_df = pd.DataFrame(
            {
                "sales_order_id": [1, 2],
                "created_at": ["2026-01-01", "2026-01-02"],
                "last_updated": ["2026-01-01", "2026-01-02"],
                "design_id": [1, 2],
                "staff_id": [1, 2],
                "counterparty_id": [1, 2],
                "units_sold": [4734, 27354],
                "unit_price": [1.45, 1.76],
                "currency_id": [1, 2],
                "agreed_delivery_date": ["2026-01-01", "2026-01-02"],
                "agreed_payment_date": ["2026-01-03", "2026-01-04"],
                "agreed_delivery_location_id": [1, 2],
            }
        )
    result = transform_sales(mock_df)
    assert isinstance(result, pd.DataFrame)
    assert len(result.columns) == 15
    assert "sales_record_id" in result.columns
    assert "sales_order_id" in result.columns
    assert "created_date" in result.columns
    assert "created_time" in result.columns
    assert "last_updated_date" in result.columns
    assert "last_updated_time" in result.columns
    assert "sales_staff_id" in result.columns
    assert "counterparty_id" in result.columns
    assert "units_sold" in result.columns
    assert "unit_price" in result.columns
    assert "currency_id" in result.columns
    assert "design_id" in result.columns
    assert "agreed_payment_date" in result.columns
    assert "agreed_delivery_date" in result.columns
    assert "agreed_delivery_location_id" in result.columns


def test_transform_sales_returns_df_with_no_duplicates():
    mock_df = pd.DataFrame(
            {
                "sales_order_id": [1, 1],
                "created_at": ["2026-01-01", "2026-01-01"],
                "last_updated": ["2026-01-02", "2026-01-02"],
                "design_id": [1, 1],
                "staff_id": [3, 3],
                "counterparty_id": [2, 2],
                "units_sold": [4734, 4734],
                "unit_price": [1.45, 1.45],
                "currency_id": [5, 5],
                "agreed_delivery_date": ["2026-01-03", "2026-01-03"],
                "agreed_payment_date": ["2026-01-02", "2026-01-02"],
                "agreed_delivery_location_id": [2, 2],
            }
        )
    result = transform_sales(mock_df)
    repeated_orders = result[result["sales_order_id"].duplicated(keep=False)]
    assert len(repeated_orders) == 0
    assert len(result) == 1

def test_transform_sales_removes_rows_with_missing_values():
    mock_df = pd.DataFrame(
            {
                "sales_order_id": [1, 1],
                "created_at": ["2026-01-01", "2026-01-01"],
                "last_updated": ["2026-01-02", "2026-01-02"],
                "design_id": [1, None],
                "staff_id": [3, 3],
                "counterparty_id": [2, 2],
                "units_sold": [4734, 4734],
                "unit_price": [1.45, 1.45],
                "currency_id": [5, 5],
                "agreed_delivery_date": ["2026-01-03", "2026-01-03"],
                "agreed_payment_date": ["2026-01-02", "2026-01-02"],
                "agreed_delivery_location_id": [2, 2],
            }
        )
    result = transform_sales(mock_df)
    assert len(result) == 1


@mock.patch("transform.transform_data.save_dataframe_to_s3_parquet")
@mock.patch("transform.transform_data.create_merged_counterparty_dataframe")
@mock.patch("transform.transform_data.create_merged_staff_dataframe")
@mock.patch("transform.transform_data.get_dataframe_from_s3")
@mock.patch("transform.transform_data.create_dim_date")
@mock.patch("transform.transform_data.transform_location")
@mock.patch("transform.transform_data.transform_counterparty")
@mock.patch("transform.transform_data.transform_staff")
@mock.patch("transform.transform_data.transform_currency")
@mock.patch("transform.transform_data.transform_design")
@mock.patch("transform.transform_data.transform_sales")
@mock.patch("transform.transform_data.boto3.client")
def test_lambda_handler_extracts_all_data(
    mock_boto_client,
    mock_transform_sales,
    mock_transform_design,
    mock_transform_currency,
    mock_transform_staff,
    mock_transform_counterparty,
    mock_transform_location,
    mock_create_dim_date,
    mock_get_dataframe_from_s3,
    mock_create_merged_staff_dataframe,
    mock_create_merged_counterparty_dataframe,
    mock_save_dataframe,
    monkeypatch,
):
    monkeypatch.setenv("INGEST_BUCKET", "mock-s3")
    monkeypatch.setenv("PROCESSED_BUCKET", "mock-s3")

    mock_s3_client = mock.MagicMock()
    mock_boto_client.return_value = mock_s3_client
    
    mock_get_dataframe_from_s3.return_value = pd.DataFrame()
    mock_transform_sales.return_value = pd.DataFrame()
    mock_transform_design.return_value = pd.DataFrame()
    mock_transform_currency.return_value = pd.DataFrame()
    mock_transform_staff.return_value = pd.DataFrame()
    mock_transform_counterparty.return_value = pd.DataFrame()
    mock_transform_location.return_value = pd.DataFrame()
    mock_create_dim_date.return_value = pd.DataFrame()
    mock_create_merged_staff_dataframe.return_value = pd.DataFrame()
    mock_create_merged_counterparty_dataframe.return_value = pd.DataFrame()

    lambda_handler({}, None)

    call_list = mock_save_dataframe.call_args_list
    table_names = []
    for call in call_list:
        table_name = call.kwargs["table_name"]
        table_names.append(table_name)

    assert mock_save_dataframe.call_count == 7
    assert 'fact_sales' in table_names
    assert 'dim_design' in table_names
    assert 'dim_currency' in table_names
    assert 'dim_staff' in table_names
    assert 'dim_counterparty' in table_names
    assert 'dim_location' in table_names