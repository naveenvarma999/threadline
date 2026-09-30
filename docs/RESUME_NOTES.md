# Resume and interview notes

## Before you list this project

- Run it end to end yourself, locally and on AWS, and break something on purpose (stop the inference
  service, promote a worse model) to see what happens.
- Train on the real H&M data and replace the synthetic numbers with your own.
- Be ready to explain every file in `ml/threadline/` without notes. Interviewers pick one component and
  go deep. `docs/DESIGN.md` covers the decisions they usually ask about.
- Only claim what you have done. "Deployed" means you ran `terraform apply` and served real requests.

## Resume bullets (fill the brackets with your own measured numbers)

- Built a two-stage fashion recommender (four retrievers incl. a PyTorch two-tower model with FAISS,
  plus a gradient-boosted ranker over 38 engineered features) on [N]M H&M transactions, reaching
  MAP@12 of [x] vs [y] for a popularity baseline under a strict time-based split.
- Served recommendations through a FastAPI service at p95 [z] ms, with per-user caching, autoscaling on
  ECS Fargate and a popularity fallback; one shared feature code path for training and serving.
- Implemented MLflow experiment tracking and a model registry with champion/challenger aliases, an
  automatic promotion gate, weekly retraining on EventBridge and zero-downtime model hot reload.
- Delivered a React storefront with explainable recommendations and an Angular ops console
  (offline metrics, ablations, latency, CTR by placement) on a Django REST API and PostgreSQL.
- Provisioned all AWS infrastructure (ECS, RDS, S3, CloudFront, ECR, IAM, budgets) with Terraform and
  automated test, build and deploy with GitHub Actions.

## Questions to prepare for

1. Why two stages instead of one model? What limits your MAP@12? (candidate recall)
2. How do you know there is no leakage? Show the test.
3. Why does the ranker barely use the two-tower features, and what would you try next?
4. What is logQ correction and why does in-batch softmax need it?
5. Why is the two-tower model served in NumPy? What breaks if someone changes the user tower?
6. What happens when the inference service is down? When MLflow is down?
7. Your p95 is [z] ms at 1 request but much higher under load. Where is the time going, and how would
   you fix it?
8. How would you run an online A/B test between champion and challenger with this architecture?
9. Why no NAT gateway? What would change for a real production deployment?
10. The promotion gate compares different test weeks. Why is that a problem, and how do you fix it?
