resource "aws_cloudwatch_log_group" "ingest_function_log_group" {
  name              = "/aws/lambda/ingest_raw_data"
  retention_in_days = 30
  lifecycle {
    prevent_destroy = false
  }
}

resource "aws_cloudwatch_log_metric_filter" "ingest_function_error" {
  name           = "ingest_function_error"
  pattern        = "ERROR"
  log_group_name = aws_cloudwatch_log_group.ingest_function_log_group.name

  metric_transformation {
    name      = "ingest_function_error"
    namespace = "Lambda errors"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "ingest_function_error_alarm" {
  alarm_name                = "ingest_function_error_alarm"
  comparison_operator       = "GreaterThanOrEqualToThreshold"
  evaluation_periods        = 1
  metric_name               = aws_cloudwatch_log_metric_filter.ingest_function_error.name
  namespace                 = "Lambda errors"
  period                    = 60
  statistic                 = "Sum"
  threshold                 = 1
  alarm_description         = "Alert when ingest function logs contain Error"
  insufficient_data_actions = []
  alarm_actions             = [aws_sns_topic.error_notification.arn]
}

# cloudwatch log group for transform lambda
resource "aws_cloudwatch_log_group" "transform_function_log_group" {
  name              = "/aws/lambda/transform_function" # change if the function name differs, finds the logging info in warehouse function
  retention_in_days = 30                               # logs delete after 14 days
}