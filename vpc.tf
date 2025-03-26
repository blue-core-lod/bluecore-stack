# VPC Resource
resource "aws_vpc" "bluecore-dev" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    name      = "bluecore-dev"
    terraform = "true"
  }
}

# Public Subnets
resource "aws_subnet" "bluecore-dev-public-1" {
  vpc_id                  = aws_vpc.bluecore-dev.id
  cidr_block              = "10.0.0.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "us-west-2a"

  tags = {
    name      = "bluecore-dev-public-1"
    terraform = "true"
  }
}
resource "aws_subnet" "bluecore-dev-public-2" {
  vpc_id                  = aws_vpc.bluecore-dev.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "us-west-2b"

  tags = {
    name      = "bluecore-dev-public-2"
    terraform = "true"
  }
}

resource "aws_subnet" "bluecore-dev-public-3" {
  vpc_id                  = aws_vpc.bluecore-dev.id
  cidr_block              = "10.0.2.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "us-west-2c"

  tags = {
    name      = "bluecore-dev-public-3"
    terraform = "true"
  }
}

# Private Subnets
resource "aws_subnet" "bluecore-dev-private-1" {
  vpc_id                  = aws_vpc.bluecore-dev.id
  cidr_block              = "10.0.64.0/24"
  availability_zone       = "us-west-2a"

  tags = {
    name      = "bluecore-dev-private-1"
    terraform = "true"
  }
}
resource "aws_subnet" "bluecore-dev-private-2" {
  vpc_id                  = aws_vpc.bluecore-dev.id
  cidr_block              = "10.0.65.0/24"
  availability_zone       = "us-west-2b"

  tags = {
    name      = "bluecore-dev-private-2"
    terraform = "true"
  }
}

resource "aws_subnet" "bluecore-dev-private-3" {
  vpc_id                  = aws_vpc.bluecore-dev.id
  cidr_block              = "10.0.66.0/24"
  availability_zone       = "us-west-2c"

  tags = {
    name      = "bluecore-dev-private-3"
    terraform = "true"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "bluecore-dev" {
  vpc_id = aws_vpc.bluecore-dev.id

  tags = {
    name      = "bluecore-dev"
    terraform = "true"
  }
}

# Route Table
resource "aws_route_table" "bluecore-dev" {
  vpc_id = aws_vpc.bluecore-dev.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.bluecore-dev.id
  }

  tags = {
    name      = "bluecore-dev"
    terraform = "true"
  }
}

# Route Table Association
resource "aws_route_table_association" "bluecore-dev-public-1" {
  subnet_id      = aws_subnet.bluecore-dev-public-1.id
  route_table_id = aws_route_table.bluecore-dev.id
}

resource "aws_route_table_association" "bluecore-dev-public-2" {
  subnet_id      = aws_subnet.bluecore-dev-public-2.id
  route_table_id = aws_route_table.bluecore-dev.id
}

resource "aws_route_table_association" "bluecore-dev-public-3" {
  subnet_id      = aws_subnet.bluecore-dev-public-3.id
  route_table_id = aws_route_table.bluecore-dev.id
}
