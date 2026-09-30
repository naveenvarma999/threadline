# Deploying to AWS

Everything is in `infra/terraform`. Expect the first apply to take 15–25 minutes (CloudFront and RDS
are slow to create).

## Cost warning — read first

- AWS accounts created on or after 15 July 2025 get up to $200 of credits and a Free plan that lasts
  at most 6 months, not the old 12-month free tier. Check your account's plan.
- This stack runs continuously: RDS, an ALB, and 3 Fargate services. Estimate it with the
  [AWS Pricing Calculator](https://calculator.aws/) for your region before applying, and put the number
  in your README.
- A budget alert is created (`monthly_budget_usd`, default $40). Confirm the SNS email subscription.
- Tear down after demos: `terraform destroy`. Rebuilding takes one `apply`.

## 1. Prerequisites

- AWS CLI configured (`aws sts get-caller-identity` works)
- Terraform ≥ 1.6, Docker, Node 22

## 2. Create the infrastructure

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars   # set alert_email
terraform init
terraform apply -target=aws_ecr_repository.repo   # repositories first, so images can be pushed
```

## 3. Build and push images

```bash
REGION=eu-west-2
REGISTRY=$(aws sts get-caller-identity --query Account --output text).dkr.ecr.$REGION.amazonaws.com
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $REGISTRY

docker build -f services/inference/Dockerfile -t $REGISTRY/threadline/inference:latest .
docker build -t $REGISTRY/threadline/app-api:latest services/app_api
docker build -t $REGISTRY/threadline/mlflow:latest infra/mlflow
docker build -f ml/Dockerfile -t $REGISTRY/threadline/trainer:latest .
for r in inference app-api mlflow trainer; do docker push $REGISTRY/threadline/$r:latest; done
```

## 4. Apply the rest

```bash
terraform apply
```

The inference service starts without a model and retries every 30 s. That is expected.

## 5. First training run

```bash
$(terraform output -raw run_training_command)
```

Follow it in CloudWatch Logs (`/ecs/threadline/trainer`). When it finishes it has registered and
promoted a model, published processed data to S3 and asked the inference service to reload.

Restart the API once so it seeds the catalogue from the published data:

```bash
aws ecs update-service --cluster threadline --service app-api --force-new-deployment
```

## 6. Publish the frontends

```bash
cd web/storefront && npm run build
aws s3 sync dist s3://$(terraform -chdir=../../infra/terraform output -json site_buckets | jq -r .storefront) --delete
cd ../ops-console && npx ng build
aws s3 sync dist/ops-console/browser s3://$(terraform -chdir=../../infra/terraform output -json site_buckets | jq -r .ops) --delete
```

Open `terraform output storefront_url`. For the ops console, read the token with the command shown by
`terraform output ops_token_parameter`.

## 7. Continuous deployment

`.github/workflows/deploy.yml` does steps 3 and 6 on every `v*` tag using GitHub OIDC (no long-lived
keys). Create an IAM role trusted by `token.actions.githubusercontent.com` for your repository, and set
the repository variables listed at the top of the workflow.

## Real H&M data

Upload `articles.csv`, `customers.csv` and `transactions_train.csv` to a bucket, set
`raw_data_s3_prefix = "s3://your-bucket/hm"` and re-apply. Check the competition's data rules first.
The trainer task has 16 GB memory and trains on the last 16 weeks; raise `TL_HISTORY_WEEKS` only with
more memory.
