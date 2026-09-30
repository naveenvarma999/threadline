"""Item content embeddings with TensorFlow / Keras.

A denoising autoencoder compresses each article's metadata (categorical attributes plus a
hashed bag of words from the product description) into a 32-d vector. The vectors feed:
* the two-tower item tower (helps cold-start items with few sales),
* the ``content_sim`` ranker feature,
* the "Similar items" endpoint.

If product images are available (real H&M ``images/`` folder) ``image_features`` adds pooled
features from a pretrained EfficientNetB0 before the autoencoder.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.preprocessing import OneHotEncoder

log = logging.getLogger(__name__)

CONTENT_ATTRS = ["product_type_name", "product_group_name", "colour_group_name", "department_name",
                 "index_group_name", "garment_group_name"]


def article_matrix(articles: pd.DataFrame, n_text_features: int = 512) -> np.ndarray:
    onehot = OneHotEncoder(handle_unknown="ignore", min_frequency=5, sparse_output=False)
    cats = onehot.fit_transform(articles[CONTENT_ATTRS].astype(str))
    text = HashingVectorizer(n_features=n_text_features, binary=True, norm=None, alternate_sign=False,
                             stop_words="english").transform(articles["detail_desc"].fillna(""))
    return np.hstack([cats, text.toarray()]).astype(np.float32)


def image_features(articles: pd.DataFrame, image_dir: Path, n_components: int = 64) -> np.ndarray | None:
    """Pooled EfficientNetB0 features for H&M images laid out as images/<first 3 digits>/<id>.jpg."""
    import tensorflow as tf
    from sklearn.decomposition import PCA

    paths = [image_dir / f"{a:010d}"[:3] / f"{a:010d}.jpg" for a in articles["article_id"]]
    if not any(p.exists() for p in paths[:100]):
        return None
    model = tf.keras.applications.EfficientNetB0(include_top=False, pooling="avg", weights="imagenet")
    feats = np.zeros((len(paths), model.output_shape[-1]), dtype=np.float32)
    batch, idx = [], []
    for i, p in enumerate(paths):
        if p.exists():
            img = tf.keras.utils.load_img(p, target_size=(224, 224))
            batch.append(tf.keras.utils.img_to_array(img))
            idx.append(i)
        if len(batch) == 64 or (i == len(paths) - 1 and batch):
            x = tf.keras.applications.efficientnet.preprocess_input(np.stack(batch))
            feats[idx] = model.predict(x, verbose=0)
            batch, idx = [], []
    return PCA(n_components=n_components, random_state=0).fit_transform(feats).astype(np.float32)


def train_content_embeddings(
    articles: pd.DataFrame,
    dim: int = 32,
    epochs: int = 15,
    seed: int = 42,
    image_dir: Path | None = None,
    log_fn=None,
) -> np.ndarray:
    import tensorflow as tf

    tf.keras.utils.set_random_seed(seed)
    x = article_matrix(articles)
    if image_dir is not None and image_dir.exists():
        img = image_features(articles, image_dir)
        if img is not None:
            img = (img - img.mean(0)) / (img.std(0) + 1e-6)
            x = np.hstack([x, 1 / (1 + np.exp(-img))]).astype(np.float32)  # squash into [0, 1]
            log.info("Added image features: %s", img.shape)

    inp = tf.keras.Input(shape=(x.shape[1],))
    noisy = tf.keras.layers.Dropout(0.2)(inp)
    h = tf.keras.layers.Dense(128, activation="relu")(noisy)
    z = tf.keras.layers.Dense(dim, name="embedding")(h)
    h2 = tf.keras.layers.Dense(128, activation="relu")(z)
    out = tf.keras.layers.Dense(x.shape[1], activation="sigmoid")(h2)
    auto = tf.keras.Model(inp, out)
    auto.compile(optimizer=tf.keras.optimizers.Adam(1e-3), loss="binary_crossentropy")
    hist = auto.fit(x, x, epochs=epochs, batch_size=256, verbose=0, shuffle=True)
    if log_fn:
        for i, v in enumerate(hist.history["loss"]):
            log_fn("content_ae_loss", float(v), i)
    encoder = tf.keras.Model(inp, z)
    emb = encoder.predict(x, batch_size=2048, verbose=0)
    emb /= np.linalg.norm(emb, axis=1, keepdims=True) + 1e-8
    log.info("Content embeddings: %s, final loss %.4f", emb.shape, hist.history["loss"][-1])
    return emb.astype(np.float32)


def main() -> None:
    """Run as its own process: ``python -m threadline.content --out emb.npy``.

    The training pipeline calls this in a subprocess because TensorFlow and PyTorch share
    native thread pools badly when both train in one process.
    """
    import argparse
    import logging

    from threadline.config import Paths, TrainConfig

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    a = p.parse_args()
    paths, cfg = Paths(), TrainConfig()
    articles = pd.read_parquet(paths.processed / "articles.parquet")
    emb = train_content_embeddings(articles, dim=cfg.content_dim, epochs=cfg.content_epochs, seed=cfg.seed,
                                   image_dir=paths.raw_hm / "images")
    np.save(a.out, emb)


if __name__ == "__main__":
    main()
