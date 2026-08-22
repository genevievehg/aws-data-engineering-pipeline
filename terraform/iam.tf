# Trust policy shared by the Lambda execution roles.
# Allows the AWS Lambda service to assume these roles when functions run.
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

# Runtime role for the extract Lambda.
# Permissions are attached separately below.
resource "aws_iam_role" "extract_lambda_role" {
  name_prefix        = "role-extract-lambda-"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

# Runtime role for the transform Lambda.
resource "aws_iam_role" "transform_lambda_role" {
  name_prefix        = "role-transform-lambda-"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

# Runtime role for the Lambda that loads processed data
# into the PostgreSQL warehouse.
resource "aws_iam_role" "load_lambda_role" {
  name_prefix        = "role-load-lambda-"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

## Runtime role for the Lambda that loads the schema
# into the PostgresSQL warehouse
resource "aws_iam_role" "schema_load_lambda_role" {
  name_prefix        = "schema-load-lambda-"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

# Looks up the existing Totesys credentials secret.
data "aws_secretsmanager_secret" "totesys_credentials" {
  name = "totesys_database_credentials"
}

# Grants the Lambda permission to write objects
# only to the ingestion S3 bucket.
resource "aws_iam_policy" "extract_s3_policy" {
  name = "extract-lambda-s3-access"

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid      = "WriteRawData"
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "${aws_s3_bucket.ingestion_zone.arn}/*"
      },
      {
        Sid      = "ListIngestionBucket"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.ingestion_zone.arn
      }
    ]
  })
}

# Grants the extract Lambda permission to retrieve the Totesys database credentials
# from AWS Secrets Manager. Access is restricted to the specific secret
# referenced above.
resource "aws_iam_policy" "extract_secrets_policy" {
  name = "extract-lambda-secrets-access"

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid      = "ReadTotesysCredentials"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = data.aws_secretsmanager_secret.totesys_credentials.arn
      }
    ]
  })
}

#Grants the load Lambda permission to retrieve the warehouse credentials from Secrets Manager
resource "aws_iam_policy" "load_warehouse_secret_policy" {
  name = "load-lambda-warehouse-secret-access"

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid      = "ReadWarehouseCredentials"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_db_instance.warehouse.master_user_secret[0].secret_arn
      }
    ]
  })
}

# Grants the Lambda function permission to create CloudWatch log groups and streams
# and write log events to CloudWatch Logs.
resource "aws_iam_policy" "lambda_function_logging_policy" {
  name = "function-logging-policy"
  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        Action : [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Effect : "Allow",
        Resource : "arn:aws:logs:*:*:*"
      }
    ]
  })
}


resource "aws_iam_policy" "transform_s3_policy" {
  name = "transform-lambda-s3-access"

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid      = "ReadRawObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.ingestion_zone.arn}/*"
      },
      {
        Sid    = "ReadCode"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion"
        ]
        Resource = "${aws_s3_bucket.code.arn}/*"
      },
      {
        Sid      = "ListIngestionBucket"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.ingestion_zone.arn
      },
      {
        Sid      = "WriteProcessedData"
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "${aws_s3_bucket.processed_zone.arn}/*"
      }
    ]
  })
}


# Grants the load Lambda read access to the processed S3 bucket.
resource "aws_iam_policy" "load_s3_policy" {
  name = "load-lambda-processed-s3-access"

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid      = "ReadProcessedObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.processed_zone.arn}/*"
      },
      {
        Sid      = "ListProcessedBucket"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.processed_zone.arn
      }
    ]
  })
}

# Give the load Lambda permission to read objects from processed zone S3.
resource "aws_iam_role_policy_attachment" "load_s3_attach" {
  role       = aws_iam_role.load_lambda_role.name
  policy_arn = aws_iam_policy.load_s3_policy.arn
}

# Give the extract Lambda permission to write raw data to S3.
resource "aws_iam_role_policy_attachment" "extract_s3_attach" {
  role       = aws_iam_role.extract_lambda_role.name
  policy_arn = aws_iam_policy.extract_s3_policy.arn
}

# Attaches the CloudWatch logging policy to the Lambda execution role,
# allowing the function to write logs to CloudWatch Logs.
resource "aws_iam_role_policy_attachment" "function_logging_policy_attach" {
  role       = aws_iam_role.extract_lambda_role.name
  policy_arn = aws_iam_policy.lambda_function_logging_policy.arn
}

# lambda logging permissions
resource "aws_iam_role_policy_attachment" "transform_lambda_basic_execution" {
  role       = aws_iam_role.transform_lambda_role.name
  policy_arn = aws_iam_policy.lambda_function_logging_policy.arn
}

# Give the extract Lambda permission to retrieve database credentials.
resource "aws_iam_role_policy_attachment" "extract_secrets_attach" {
  role       = aws_iam_role.extract_lambda_role.name
  policy_arn = aws_iam_policy.extract_secrets_policy.arn
}

# Give the load Lambda permission to retrieve warehouse credentials.
resource "aws_iam_role_policy_attachment" "load_warehouse_secret_attach" {
  role       = aws_iam_role.load_lambda_role.name
  policy_arn = aws_iam_policy.load_warehouse_secret_policy.arn
}

# Give the transform Lambda permission to read raw data and write processed data.
resource "aws_iam_role_policy_attachment" "transform_s3_attach" {
  role       = aws_iam_role.transform_lambda_role.name
  policy_arn = aws_iam_policy.transform_s3_policy.arn
}

# Enables VPC access and basic CloudWatch logging for the load Lambda.
resource "aws_iam_role_policy_attachment" "load_lambda_vpc_attach" {
  role       = aws_iam_role.load_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Provision the IAM role for the pipeline execution step function
resource "aws_iam_role" "sfn_assume_role" {
  name               = "sfn-assume-role"
  assume_role_policy = data.aws_iam_policy_document.sfn_assume_role_doc.json
}

# Define the Assume Role policy for the Pipeline step function to allow it to
# assume a role
data "aws_iam_policy_document" "sfn_assume_role_doc" {
  statement {
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

# Provision the IAM role for the scheduler
resource "aws_iam_role" "scheduler_assume_role" {
  name               = "scheduler-assume-role"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume_role_doc.json
}

# Define the Assume Role policy for the scheduler to allow it to allow it to
# assume a role
data "aws_iam_policy_document" "scheduler_assume_role_doc" {
  statement {
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

# Provision the policy that allows the scheduler to trigger the step function
resource "aws_iam_policy" "sfn_invoke_lambda_policy" {
  name   = "sfn-invoke-lambda-policy"
  policy = data.aws_iam_policy_document.sfn_allow_lambda_invoke.json
}

# Define the policy that allows the scheduler to trigger the step function
data "aws_iam_policy_document" "sfn_allow_lambda_invoke" {
  statement {
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.ingest_raw_data.arn]
  }
}

# Attach the lambda invokation policy to the step function
resource "aws_iam_role_policy_attachment" "sfn_lambda_invokation_attach" {
  role       = aws_iam_role.sfn_assume_role.name
  policy_arn = aws_iam_policy.sfn_invoke_lambda_policy.arn
}

# Provision the policy that allows the scheduler to trigger the step function
resource "aws_iam_policy" "scheduler_trigger_sfn" {
  name   = "scheduler-trigger-sfn"
  policy = data.aws_iam_policy_document.scheduler_allow_sfn_trigger.json
}

# Define the policy that allows the scheduler to trigger the step function
data "aws_iam_policy_document" "scheduler_allow_sfn_trigger" {
  statement {
    actions   = ["states:StartExecution"]
    resources = [aws_sfn_state_machine.pipeline_sfn.arn]
  }
}

# Attach the scheduler step function trigger policy to the scheduler
resource "aws_iam_role_policy_attachment" "scheduler_allow_sfn_trigger_attach" {
  role       = aws_iam_role.scheduler_assume_role.name
  policy_arn = aws_iam_policy.scheduler_trigger_sfn.arn
}

resource "aws_iam_policy" "schema_load_lambda_secrets_policy" {
  name = "schema-load-lambda-secrets-access"

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "ReadRDSCredentials"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"]
        Resource = aws_db_instance.warehouse.master_user_secret[0].secret_arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "schema_load_lambda_secrets_policy_attach" {
  role       = aws_iam_role.schema_load_lambda_role.name
  policy_arn = aws_iam_policy.schema_load_lambda_secrets_policy.arn
}

# Allow schema load lambda role to create VPC network interfaces and write logs.
resource "aws_iam_role_policy_attachment" "schema_load_lambda_vpc_attach" {
  role       = aws_iam_role.schema_load_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}