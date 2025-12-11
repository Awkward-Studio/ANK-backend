# =====================================
# VPC and Networking Resources
# =====================================
# Creates VPC, subnets, internet gateway, route tables
# Cost-optimized: Single-AZ, NO NAT Gateway

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project_name}-${var.environment}-vpc"
  }
}

# =====================================
# Internet Gateway
# =====================================

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-${var.environment}-igw"
  }
}

# =====================================
# Public Subnet (for ECS & ALB)
# =====================================

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidr
  availability_zone       = var.availability_zone
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-${var.environment}-public-subnet"
    Type = "Public"
  }
}

# =====================================
# Private Subnet (for RDS only)
# =====================================

resource "aws_subnet" "private" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidr
  availability_zone = var.availability_zone

  tags = {
    Name = "${var.project_name}-${var.environment}-private-subnet"
    Type = "Private"
  }
}

# RDS requires at least 2 subnets in different AZs for subnet group
# Create a second private subnet in a different AZ
resource "aws_subnet" "private_secondary" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, 10)  # Auto-generate CIDR
  availability_zone = data.aws_availability_zones.available.names[1]

  tags = {
    Name = "${var.project_name}-${var.environment}-private-subnet-2"
    Type = "Private"
  }
}

# =====================================
# Route Tables
# =====================================

# Public Route Table (routes to Internet Gateway)
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-public-rt"
  }
}

# Private Route Table (local VPC only - NO NAT Gateway)
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  # No internet route - cost optimization
  
  tags = {
    Name = "${var.project_name}-${var.environment}-private-rt"
  }
}

# =====================================
# Route Table Associations
# =====================================

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  subnet_id      = aws_subnet.private.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_secondary" {
  subnet_id      = aws_subnet.private_secondary.id
  route_table_id = aws_route_table.private.id
}

# =====================================
# Data Sources
# =====================================

data "aws_availability_zones" "available" {
  state = "available"
}
