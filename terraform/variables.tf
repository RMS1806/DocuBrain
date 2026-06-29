# ──────────────────────────────────────────────────────────────────────────────
# variables.tf — all input parameters for the DocuBrain stack
#
# Why keep all variables in one file?
# When you want to deploy a second environment (staging), you create a new
# terraform.tfvars with different values and `terraform apply -var-file=staging.tfvars`.
# The infrastructure code itself doesn't change — only the inputs do.
# ──────────────────────────────────────────────────────────────────────────────

# ── AWS ───────────────────────────────────────────────────────────────────────

variable "aws_region" {
  description = "AWS region to deploy into. Choose one close to your users."
  type        = string
  default     = "us-east-1"
  # Common choices:
  #   us-east-1 (N. Virginia)  — cheapest, most services available
  #   eu-west-1 (Ireland)      — for EU users
  #   ap-south-1 (Mumbai)      — for South Asia
}

variable "aws_profile" {
  description = "AWS CLI profile to use for authentication. Run 'aws configure --profile docubrain' first."
  type        = string
  default     = "default"
}

# ── Project ───────────────────────────────────────────────────────────────────

variable "project_name" {
  description = "Prefix applied to every AWS resource name. Makes it easy to find DocuBrain resources in the AWS Console."
  type        = string
  default     = "docubrain"
}

variable "environment" {
  description = "Deployment environment. Controls naming and certain security settings."
  type        = string
  default     = "production"

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "environment must be one of: development, staging, production."
    # Terraform validates this BEFORE making any API calls.
    # This catches typos like "prod" or "Production" that would silently create
    # misnamed resources.
  }
}

# ── Networking ────────────────────────────────────────────────────────────────

variable "vpc_cidr" {
  description = "CIDR block for the VPC. /16 gives 65,536 IP addresses — plenty for a single-server setup."
  type        = string
  default     = "10.0.0.0/16"
  # CIDR notation:  10.0.0.0/16 means:
  #   Network:  10.0.0.0 to 10.0.255.255
  #   Usable:   65,534 addresses
  # For a single server, /16 is overkill — but it's the standard starting point
  # because it leaves room for subnets when you scale later.
}

variable "public_subnet_cidr" {
  description = "CIDR for the public subnet. Must be a subset of vpc_cidr."
  type        = string
  default     = "10.0.1.0/24"
  # /24 = 256 addresses (254 usable) in the 10.0.1.x range
}

variable "allowed_ssh_cidr" {
  description = "Your IP address in CIDR notation. Only this IP can SSH to the server. Find yours at https://checkip.amazonaws.com"
  type        = string
  # No default — you MUST provide your own IP.
  # Setting this to "0.0.0.0/0" would allow anyone to attempt SSH — never do this.
  # Example: "203.0.113.42/32"  (/32 = exactly one IP address)
}

# ── EC2 ───────────────────────────────────────────────────────────────────────

variable "instance_type" {
  description = "EC2 instance size. t3.small is the minimum comfortable size for the full stack."
  type        = string
  default     = "t3.small"
  # Instance type format: <family><generation>.<size>
  #   t3 = burstable (gets baseline CPU + can burst using accumulated credits)
  #       good for web apps that have idle periods between requests
  #   t3.micro  = 1 vCPU, 1GB  RAM — too small for Postgres + Redis + Python
  #   t3.small  = 2 vCPU, 2GB  RAM — minimum viable for DocuBrain
  #   t3.medium = 2 vCPU, 4GB  RAM — comfortable for production
  #
  # Pricing (us-east-1, on-demand):
  #   t3.small  = ~$0.0208/hr = ~$15/month
  #   t3.medium = ~$0.0416/hr = ~$30/month
}

variable "ami_id" {
  description = "Amazon Machine Image ID — the OS + pre-installed software. Must match the aws_region."
  type        = string
  default     = "ami-0c7217cdde317cfec"
  # This is Ubuntu 22.04 LTS in us-east-1 (as of 2024).
  # AMI IDs are REGION-SPECIFIC — the same Ubuntu image has a different ID in each region.
  # Find the latest: AWS Console → EC2 → AMIs → search "ubuntu 22.04"
  # Or use: aws ec2 describe-images --owners 099720109477 --filters 'Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64*'
}

variable "key_pair_name" {
  description = "Name of an existing EC2 key pair for SSH access. Create one in AWS Console → EC2 → Key Pairs, then download the .pem file."
  type        = string
  # No default — you must create a key pair first.
  # Example: "docubrain-key"
}

# ── S3 ────────────────────────────────────────────────────────────────────────

variable "s3_bucket_name" {
  description = "S3 bucket name for document uploads. Must be globally unique across ALL AWS accounts."
  type        = string
  # S3 bucket names are a global namespace — like domain names.
  # Best practice: prefix with your org or project + random suffix.
  # Example: "docubrain-uploads-raj-1806"
}

# ── App secrets (passed to the server via user_data) ──────────────────────────
# These are marked sensitive = true so Terraform never prints them in plan output
# or logs. They still appear in tfstate (another reason not to commit tfstate).

variable "secret_key" {
  description = "Django/FastAPI SECRET_KEY for JWT signing. Generate with: python -c 'import secrets; print(secrets.token_hex(32))'"
  type        = string
  sensitive   = true
}

variable "postgres_password" {
  description = "Password for the PostgreSQL docubrain user."
  type        = string
  sensitive   = true
}

variable "gemini_api_key" {
  description = "Google Gemini API key."
  type        = string
  sensitive   = true
}

variable "pinecone_api_key" {
  description = "Pinecone vector database API key."
  type        = string
  sensitive   = true
}

variable "pinecone_index_name" {
  description = "Name of the Pinecone index."
  type        = string
  default     = "docubrain-index"
}
