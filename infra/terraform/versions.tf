terraform {
  required_version = ">= 1.6"
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 5.80" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }

  # Keep state in S3 so CI and your laptop share it. Create the bucket once by hand, then uncomment.
  # backend "s3" {
  #   bucket = "threadline-tfstate-<your-account-id>"
  #   key    = "threadline/terraform.tfstate"
  #   region = "eu-west-2"
  # }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = var.project, ManagedBy = "terraform" }
  }
}
