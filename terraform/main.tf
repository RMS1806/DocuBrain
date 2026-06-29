# ──────────────────────────────────────────────────────────────────────────────
# main.tf — core infrastructure: VPC, networking, EC2, Elastic IP
#
# Resource dependency graph (Terraform figures this out automatically
# and creates resources in the right order):
#
#   aws_vpc
#     └── aws_internet_gateway
#     └── aws_subnet (public)
#           └── aws_route_table → aws_route_table_association
#     └── aws_security_group (defined in security_groups.tf)
#           └── aws_instance (EC2)
#                 └── aws_eip (Elastic IP)
# ──────────────────────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.6"   # minimum Terraform CLI version

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"   # "~> 5.0" means: >=5.0, <6.0 (minor updates OK, no major)
    }
  }

  # ── Remote state (recommended for teams — uncomment and configure) ───────────
  # Without this, tfstate is stored locally. Fine for solo development, but
  # if two people run terraform simultaneously, state gets corrupted.
  #
  # backend "s3" {
  #   bucket         = "docubrain-terraform-state"
  #   key            = "production/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true       # encrypt state at rest (it contains secrets)
  #   dynamodb_table = "docubrain-terraform-locks"  # prevents concurrent applies
  # }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  # default_tags: applied to EVERY resource this provider creates.
  # AWS tags are key-value pairs — crucial for:
  #   - Cost allocation: see exactly what DocuBrain costs on your bill
  #   - Filtering: find all DocuBrain resources in one console search
  #   - Automation: scripts can target resources by tag
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"   # anyone who sees this resource knows not to edit it manually
    }
  }
}


# ── VPC (Virtual Private Cloud) ───────────────────────────────────────────────
# A VPC is your own isolated section of the AWS network.
# Think of it as a private data centre inside AWS where you control
# the IP address ranges, routing rules, and what's public vs private.
#
# Without a VPC, all your resources would be on a flat shared network
# with other AWS customers. VPCs provide the isolation.

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true   # required for EC2 instance hostnames to work
  enable_dns_hostnames = true   # assigns a DNS name to each instance (e.g. ec2-x-x-x-x.compute.amazonaws.com)

  tags = { Name = "${var.project_name}-vpc" }
}


# ── Internet Gateway ──────────────────────────────────────────────────────────
# An Internet Gateway (IGW) is what connects your VPC to the public internet.
# Without it, all resources in the VPC are completely isolated — they can talk
# to each other but not to the outside world. Nothing can reach them from outside.
#
# Think of it as the front door of your data centre.
# The VPC is the building. The IGW is the door.

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id   # attach to our VPC

  tags = { Name = "${var.project_name}-igw" }
}


# ── Public Subnet ─────────────────────────────────────────────────────────────
# A subnet is a subdivision of your VPC's IP range.
# "Public" means resources in it can be assigned a public IP and reach the internet
# (via the Internet Gateway). "Private" subnets cannot.
#
# Our EC2 server lives in the public subnet because it needs to receive
# HTTPS traffic from browsers. In a more complex setup:
#   - Public subnet:  load balancer, NAT gateway
#   - Private subnet: EC2 app servers, RDS (database), ElastiCache
# This is the 3-tier architecture. For a single-server portfolio project,
# one public subnet is the right tradeoff.

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidr
  availability_zone       = "${var.aws_region}a"   # e.g. "us-east-1a"
  map_public_ip_on_launch = true   # every instance gets a public IP automatically

  tags = { Name = "${var.project_name}-public-subnet" }
}


# ── Route Table ───────────────────────────────────────────────────────────────
# A route table is a set of routing rules: "where should traffic go?"
#
# Our route table has one rule:
#   destination: 0.0.0.0/0 (meaning: any IP address)
#   target: the Internet Gateway
#
# Translation: "for all outbound traffic, send it to the internet gateway."
# This is what makes the subnet "public."

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = { Name = "${var.project_name}-public-rt" }
}

# Associate the route table with our public subnet.
# A subnet can only have one route table. Without this association,
# the subnet uses the VPC's default route table (which has no internet route).
resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}


# ── EC2 Instance ──────────────────────────────────────────────────────────────
# The virtual machine that runs everything: Nginx, FastAPI, Postgres, Redis.
#
# user_data: a bash script that runs ONCE when the instance first boots.
# This is how we install Docker, pull our repo, and start the stack
# without ever SSHing in manually.

resource "aws_instance" "app" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.app.id]   # defined in security_groups.tf
  key_name               = var.key_pair_name
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name   # defined in s3.tf

  # user_data: passed as a bash script. templatefile() reads user_data.sh
  # and substitutes ${variable} placeholders with actual values.
  # The script runs as root on first boot — perfect for installing system packages.
  user_data = templatefile("${path.module}/user_data.sh", {
    project_name        = var.project_name
    postgres_password   = var.postgres_password
    secret_key          = var.secret_key
    gemini_api_key      = var.gemini_api_key
    pinecone_api_key    = var.pinecone_api_key
    pinecone_index_name = var.pinecone_index_name
    s3_bucket_name      = var.s3_bucket_name
    aws_region          = var.aws_region
  })

  # root_volume: the OS disk.
  root_block_device {
    volume_type           = "gp3"    # gp3 is the latest general-purpose SSD — cheaper than gp2
    volume_size           = 20       # GB — enough for OS + Docker images + Postgres data
    delete_on_termination = true     # delete disk when instance is terminated (avoids orphaned EBS charges)
    encrypted             = true     # encrypt disk at rest (good practice, no performance cost on modern instances)
  }

  tags = { Name = "${var.project_name}-app-server" }

  # lifecycle: prevent accidental deletion.
  # If you run 'terraform apply' and the change would DESTROY this instance,
  # Terraform will error instead. You must explicitly remove this block first.
  # This protects against typos that would wipe your production server.
  lifecycle {
    prevent_destroy = false   # set to true after initial setup is confirmed working
  }
}


# ── Elastic IP ────────────────────────────────────────────────────────────────
# An EC2 instance's public IP changes every time it restarts.
# An Elastic IP (EIP) is a STATIC public IP that stays the same.
# You associate it with an instance — if the instance restarts, the IP stays.
#
# Why this matters: your DNS record (docubrain.com → 54.x.x.x) must point
# to a stable IP. Without an EIP, every server restart would require a DNS update.

resource "aws_eip" "app" {
  domain   = "vpc"   # required for VPC-attached EIPs (vs the legacy EC2-Classic)
  instance = aws_instance.app.id

  # The EIP depends on the IGW existing. Without this explicit dependency,
  # Terraform might try to attach the EIP before the IGW is ready.
  depends_on = [aws_internet_gateway.main]

  tags = { Name = "${var.project_name}-eip" }
}
