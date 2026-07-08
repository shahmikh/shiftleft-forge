provider "aws" {
  region = "us-east-1"
}
 
resource "aws_s3_bucket" "demo_bucket" {
  bucket = "shiftleft-forge-YOUR-NAME-12345"
}
 
resource "aws_s3_bucket_server_side_encryption_configuration" "enc" {
  bucket = aws_s3_bucket.demo_bucket.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
 
resource "aws_s3_bucket_versioning" "ver" {
  bucket = aws_s3_bucket.demo_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}
 
resource "aws_s3_bucket_public_access_block" "block" {
  bucket                  = aws_s3_bucket.demo_bucket.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
