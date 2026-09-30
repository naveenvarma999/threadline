# Design decisions

This file records why the system looks the way it does. Interviewers ask about these choices more than
about any single line of code, so each section states the decision, the reason and the cost.

## 1. Two-stage recommender

**Decision.** Retrieval (4 sources, ~100 candidates per user) followed by a gradient-boosted ranker.

**Why.** Scoring every article for every user with a rich model does not scale (105k articles × 1.37M
customers in the real H&M data). Cheap retrievers narrow the pool; the ranker spends its budget where it
matters. This is the standard industry pattern (YouTube, Pinterest, most e-commerce).

**Cost.** The ranker can only reorder what retrieval found. *Candidate recall* is reported next to MAP@12
because it is the ceiling: if 52% of next-week purchases are in the candidate set, no ranker can recover
the other 48%.

## 2. Time-based evaluation with no leakage

**Decision.** Every feature for label week `t` is computed from weeks `< t` only (`features.make_snapshot`).
Retrieval models are trained on data strictly before every ranker label week. `tests/test_leakage.py`
checks both.

**Why.** Random train/test splits on transaction data leak the future (item popularity computed with
the label week, repeat purchases seen in training). Leaky offline metrics look great and collapse in
production.

**Cost.** Retrieval embeddings are several weeks old by the time they serve. Weekly retraining limits
this; a production system would retrain more often or use a streaming feature store.

## 3. One feature code path for training and serving

**Decision.** `build_features()` and `CandidateGenerator.generate()` run unchanged offline (thousands of
users) and online inside FastAPI (one user).

**Why.** Training/serving skew — features computed slightly differently in two code bases — is one of
the most common silent failures in production ML.

**Cost.** Online scoring uses pandas, which is slower than hand-written NumPy. Measured p95 is under
100 ms on 2 vCPUs, which is inside the budget, so the simplicity is worth it.

## 4. PyTorch for training, NumPy for serving the two-tower model

**Decision.** The two-tower model trains in PyTorch; item vectors are pre-computed and the small user
MLP is exported to NumPy (`TwoTowerNumpy`). A test asserts both forward passes agree to 1e-5.

**Why.** The inference image stays small (no PyTorch, no GPU drivers) and starts fast.

**Cost.** Any change to the user tower architecture must be mirrored in `encode_users`. The parity test
catches mistakes.

## 5. TensorFlow for content embeddings

**Decision.** A Keras denoising autoencoder compresses article metadata (and product images when
available) into 32-d vectors used by the item tower, a ranker feature and "Similar items".

**Why.** Helps cold-start articles with few sales, and powers similarity that does not depend on
purchase history.

**Honest note.** This could be written in PyTorch too. TensorFlow is here to show working knowledge of
both frameworks. It runs as a separate process because TensorFlow and PyTorch conflict when both train
in one Python process (segfault from shared native thread pools, observed during development).

## 6. Django and FastAPI as separate services

**Decision.** Django owns users, catalogue, orders, events and admin. FastAPI owns model inference.

**Why.** They scale and release differently. The model service is CPU-bound, stateless and redeployed
on every promotion; the product API is I/O-bound and changes with product features. Separate services
also let the storefront degrade gracefully: Django falls back to best sellers when inference is down.

**Cost.** An extra network hop (~1–3 ms in the same VPC) and one more service to operate.

## 7. React storefront, Angular ops console

**Decision.** Customers use a React app; the internal team uses an Angular app.

**Why.** Two audiences with different needs. **Honest note:** in a real company one framework would
usually serve both. Angular is here to demonstrate it; the split along an audience boundary is the most
defensible place to put it.

## 8. MLflow registry with aliases and a promotion gate

**Decision.** Every training run registers a new version as `challenger`. It becomes `champion` only if
its test MAP@12 is at least 1% better than the current champion. The inference service loads
`models:/threadline-recommender@champion` and hot-reloads on promotion.

**Known limitation.** Two versions trained on different weeks are compared on *different* test weeks.
A stricter gate re-scores the champion on the challenger's test week before comparing. That is the next
improvement to make.

## 9. AWS layout

ECS Fargate (no servers to patch), RDS Postgres, S3 + CloudFront for both frontends, CloudFront also
fronting the ALB so everything is one HTTPS origin per app. MLflow runs as an internal ECS service with
Postgres metadata and S3 artifacts. Retraining is an EventBridge Scheduler → ECS RunTask job.

Deliberately **not** used: NAT gateway (cost; public subnets + tight security groups instead), SageMaker
endpoints and ElastiCache (both cost more than the rest of the stack for a demo). The inference service
uses an in-process cache instead of Redis on AWS; Redis is used in Docker Compose.

## 10. What is not done (say this before an interviewer does)

- No real users, so no online A/B test. Engagement numbers in the ops console come from demo traffic.
- The ranker is pointwise (binary cross-entropy). A LambdaRank objective (LightGBM) may do better.
- No streaming features; history updates only through session items sent with each request.
- Synthetic data results say nothing about real-world quality. Run on the H&M data before quoting numbers.
