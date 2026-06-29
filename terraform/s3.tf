# ──────────────────────────────────────────────────────────────────────────────
# s3.tf — document storage bucket + IAM role for EC2
#
# The IAM Role pattern explained:
#
#   Instead of putting AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env
#   (which means rotating them manually and risking leaks in git commits),
#   we attach an IAM Role to the EC2 instance.
#
#   AWS automatically provides temporary credentials to the instance via the
#   Instance Metadata Service (IMDS) at 169.254.169.254. The AWS SDK
#   checks this endpoint automatically — your Python code needs zero changes.
#
#   The credentials rotate every hour. A leaked .env file grants no S3 access.
#   This is the AWS-recommended production pattern.
#
#   The chain:
#     IAM Role → Trust Policy (allows EC2 to assume the role)
#        └── IAM Policy (defines what S3 actions are allowed)
#              └── IAM Instance Profile (the "attachment point" for EC2)
#                    └── aws_instance (EC2 gets the role via the profile)
# ──────────────────────────────────────────────────────────────────────────────


# ── S3 Bucket ─────────────────────────────────────────────────────────────────

resource "aws_s3_bucket" "documents" {
  bucket = var.s3_bucket_name
  # S3 bucket names are globally unique across ALL AWS accounts and regions.
  # If the name is taken, terraform apply will fail with BucketAlreadyExists.

  tags = { Name = "${var.project_name}-documents" }
}

# Block ALL public access to the bucket.
# Documents are private — only the backend (via IAM role) should access them.
# Without this block, a misconfigured bucket policy could accidentally expose files.
# This is a hard block: even if a policy tries to grant public access, it's denied.
resource "aws_s3_bucket_public_access_block" "documents" {
  bucket = aws_s3_bucket.documents.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable server-side encryption: every object stored is encrypted at rest.
# AES256 (SSE-S3) is AWS's managed encryption — zero performance cost,
# AWS manages the keys. For stricter control, use SSE-KMS with your own key.
resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Lifecycle rule: automatically delete incomplete multipart uploads.
# When a large file upload is interrupted mid-way, S3 keeps the partial parts
# and charges you for them. This rule cleans them up after 1 day.
resource "aws_s3_bucket_lifecycle_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  rule {
    id     = "cleanup-incomplete-uploads"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}


# ── IAM Role ──────────────────────────────────────────────────────────────────
# An IAM Role is an identity with a set of permissions. Unlike a user, a role
# is assumed by AWS services (EC2, Lambda, ECS) rather than humans.

# The Trust Policy: defines WHO can assume this role.
# Here: only the EC2 service. No human users, no Lambda, no other services.
# data.aws_iam_policy_document generates a properly-formatted JSON policy
# from HCL — cleaner than writing raw JSON strings.
data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]   # "sts:AssumeRole" = "become this role"

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]   # only EC2 can assume this role
    }
  }
}

resource "aws_iam_role" "ec2_role" {
  name               = "${var.project_name}-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json

  tags = { Name = "${var.project_name}-ec2-role" }
}


# The Permissions Policy: defines WHAT the role can do.
# We apply the principle of least privilege: the EC2 instance gets exactly
# the S3 permissions it needs and nothing else.
data "aws_iam_policy_document" "s3_access" {
  # Allow: list the bucket contents (needed for "does this file exist?" checks)
  statement {
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.documents.arn]
    # arn = Amazon Resource Name — the globally unique identifier for any AWS resource
    # Format: arn:partition:service:region:account-id:resource
    # Example: arn:aws:s3:::docubrain-uploads-raj-1806
  }

  # Allow: read, write, and delete objects within the bucket
  statement {
    effect = "Allow"
    actions = [
      "s3:GetObject",     # download a file
      "s3:PutObject",     # upload a file
      "s3:DeleteObject",  # delete a file (needed when user deletes a document)
    ]
    resources = ["${aws_s3_bucket.documents.arn}/*"]   # /* = all objects in the bucket
    # Note: the ARN for objects needs the /* suffix. The bucket ARN and object ARNs are different.
  }
}

resource "aws_iam_policy" "s3_access" {
  name        = "${var.project_name}-s3-access"
  description = "Allows DocuBrain EC2 to read/write the documents S3 bucket"
  policy      = data.aws_iam_policy_document.s3_access.json
}

# Attach the permissions policy to the role.
# A role can have multiple policies attached — permissions are additive.
resource "aws_iam_role_policy_attachment" "ec2_s3" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.s3_access.arn
}


# ── IAM Instance Profile ───────────────────────────────────────────────────────
# EC2 instances don't attach IAM Roles directly — they use an "Instance Profile"
# as the bridge. An instance profile wraps exactly one IAM role.
# This is an AWS implementation detail — in the console they're created together,
# but in Terraform/API they're separate resources.

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2_role.name
}
