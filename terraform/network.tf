data "aws_vpc" "default" {
  default = true
}

# Finds the existing subnets belonging to the default VPC.
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_subnet" "lambda_a" {
  id = "subnet-0d880cf5d3312f884"
}

data "aws_subnet" "lambda_b" {
  id = "subnet-018743f5729ea520b"
}

data "aws_route_table" "default" {
  vpc_id = data.aws_vpc.default.id

  filter {
    name   = "association.main"
    values = ["true"]
  }
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id = data.aws_vpc.default.id

  service_name      = "com.amazonaws.eu-west-2.s3"
  vpc_endpoint_type = "Gateway"

  route_table_ids = [
    data.aws_route_table.default.id
    ]
}