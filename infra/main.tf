provider "aws" {
  region = "us-east-1"
}
 
resource "aws_s3_bucket" "demo_bucket" {
  bucket = "shiftleft-forge-shahmikh-19741"
}
 
# Intentionally missing: encryption, versioning, public access block
# Checkov will flag this — we fix it after seeing the real finding
