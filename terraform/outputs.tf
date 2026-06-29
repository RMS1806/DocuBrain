# ──────────────────────────────────────────────────────────────────────────────
# outputs.tf — values printed after terraform apply
#
# Outputs serve three purposes:
#   1. Human convenience: you know your server's IP without opening AWS Console
#   2. Cross-module reference: other Terraform modules can read these values
#   3. CI/CD integration: a pipeline can run `terraform output -raw server_ip`
#      to get the IP and then SSH in to deploy
# ──────────────────────────────────────────────────────────────────────────────

output "server_ip" {
  description = "The static public IP address of the DocuBrain server. Point your DNS A record here."
  value       = aws_eip.app.public_ip
}

output "server_dns" {
  description = "EC2-assigned DNS hostname. Use for temporary access before DNS is configured."
  value       = aws_instance.app.public_dns
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket for document uploads. Set S3_BUCKET_NAME in your .env to this value."
  value       = aws_s3_bucket.documents.bucket
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket. Useful for referencing in other AWS policies."
  value       = aws_s3_bucket.documents.arn
}

output "iam_role_arn" {
  description = "ARN of the EC2 IAM role. The instance uses this to access S3 without hardcoded credentials."
  value       = aws_iam_role.ec2_role.arn
}

output "ssh_command" {
  description = "Ready-to-paste SSH command to connect to the server."
  value       = "ssh -i ~/.ssh/${var.key_pair_name}.pem ubuntu@${aws_eip.app.public_ip}"
}

output "next_steps" {
  description = "Post-deploy checklist."
  value = <<-EOT
    ========================================
    DocuBrain infrastructure is ready!
    ========================================

    1. Point DNS:
       Add an A record: yourdomain.com → ${aws_eip.app.public_ip}

    2. SSH in and verify the stack started:
       ssh -i ~/.ssh/${var.key_pair_name}.pem ubuntu@${aws_eip.app.public_ip}
       sudo docker ps
       sudo docker logs docubrain_backend

    3. Set S3_BUCKET_NAME in your .env:
       S3_BUCKET_NAME=${aws_s3_bucket.documents.bucket}

    4. Remove AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY from .env
       (EC2 gets S3 access via IAM Role automatically — no keys needed)

    5. Get a TLS certificate (Let's Encrypt):
       sudo certbot certonly --standalone -d yourdomain.com
       Then uncomment the HTTPS block in infra/nginx.conf

    6. Set DEPLOY_HOST in GitHub Secrets:
       ${aws_eip.app.public_ip}
    ========================================
  EOT
}
