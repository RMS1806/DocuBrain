# ──────────────────────────────────────────────────────────────────────────────
# security_groups.tf — firewall rules for the DocuBrain server
#
# A Security Group (SG) is AWS's stateful firewall.
# "Stateful" means: if you allow inbound traffic on port 80, the return
# traffic (the server's response) is automatically allowed outbound —
# you don't need to write a rule for it. This is smarter than traditional
# firewalls (like iptables) which require explicit rules for both directions.
#
# Security Groups are ALLOW-only — there is no "deny" rule.
# Everything not explicitly allowed is denied by default.
# This is the correct secure default: closed by default, open by exception.
#
# We split security groups into a separate file because they get verbose.
# Keeping them separate makes main.tf readable and security rules easy to audit.
# ──────────────────────────────────────────────────────────────────────────────

resource "aws_security_group" "app" {
  name        = "${var.project_name}-app-sg"
  description = "DocuBrain app server — allows HTTP, HTTPS, and SSH from known IP"
  vpc_id      = aws_vpc.main.id

  # ── Inbound rules (ingress) ───────────────────────────────────────────────
  # Each ingress block is an ALLOW rule for inbound traffic.

  # HTTP (port 80) — from anywhere (0.0.0.0/0 = all IPv4, ::/0 = all IPv6)
  # Nginx listens here. In production it redirects to HTTPS.
  # Needed even if you use HTTPS because Let's Encrypt's HTTP-01 challenge
  # (the domain verification step) uses port 80.
  ingress {
    description      = "HTTP from internet"
    from_port        = 80
    to_port          = 80
    protocol         = "tcp"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  # HTTPS (port 443) — from anywhere
  # All real traffic enters here in production.
  ingress {
    description      = "HTTPS from internet"
    from_port        = 443
    to_port          = 443
    protocol         = "tcp"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  # SSH (port 22) — from YOUR IP ONLY
  # This is the most important security rule. SSH with a private key is
  # already secure, but restricting it to your IP means:
  #   1. Attackers can't even attempt to connect (SYN packets are dropped)
  #   2. Brute-force attacks are impossible — they can't reach port 22
  #   3. SSH zero-days only matter if an attacker can reach the port
  #
  # var.allowed_ssh_cidr should be "YOUR.IP.ADDRESS/32"
  # /32 = exactly one IPv4 address (a host mask, not a network)
  ingress {
    description = "SSH from admin IP only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  # ── What we deliberately DO NOT open ──────────────────────────────────────
  # Port 5432 (PostgreSQL): not exposed. Access via SSH tunnel if needed.
  # Port 6379 (Redis):      not exposed. Internal Docker network only.
  # Port 8000 (FastAPI):    not exposed. Nginx proxies to it internally.
  # Port 9000 (MinIO):      not exposed in prod (using real S3).
  # Port 5433 (PgBouncer):  not exposed. Internal Docker network only.
  #
  # The attack surface is exactly three ports: 80, 443, 22.
  # Everything else is invisible to the internet.


  # ── Outbound rules (egress) ───────────────────────────────────────────────
  # Allow all outbound traffic — the server needs to:
  #   - Call Gemini API (api.generativeai.google.com)
  #   - Call Pinecone API (controller.us-east1-gcp.pinecone.io)
  #   - Pull Docker images from Docker Hub (hub.docker.com)
  #   - Install apt packages (archive.ubuntu.com)
  #   - Access S3 (s3.amazonaws.com — within AWS, but still needs outbound)
  #
  # Locking down egress is good practice in high-security environments
  # (prevents malware from calling home), but requires careful enumeration
  # of all external services. For a portfolio project, open egress is fine.
  egress {
    description      = "All outbound traffic"
    from_port        = 0
    to_port          = 0
    protocol         = "-1"       # -1 = all protocols
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  tags = { Name = "${var.project_name}-app-sg" }

  # lifecycle: if you need to replace a security group (e.g. changing the name),
  # Terraform would normally destroy the old one first — which would detach it
  # from the instance, causing downtime.
  # create_before_destroy = true creates the new SG first, attaches it, THEN destroys the old one.
  lifecycle {
    create_before_destroy = true
  }
}
