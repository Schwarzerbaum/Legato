"""HDBSCAN clustering → group posts into Social Personas.

This is the core of Semantic Compression:
10,000 posts → 5 Vibes → send only vibes to reasoning model.
90% token savings.
"""
import numpy as np
from sklearn.cluster import KMeans


def cluster_posts(
    embeddings: np.ndarray,
    n_clusters: int = 5,
) -> np.ndarray:
    """Cluster post embeddings into Social Personas.

    Uses KMeans as primary (reliable), HDBSCAN as optional.
    Returns array of cluster labels (0 to n_clusters-1).
    """
    if len(embeddings) < n_clusters:
        return np.zeros(len(embeddings), dtype=int)

    try:
        # Try HDBSCAN first (auto-detects cluster count)
        from hdbscan import HDBSCAN
        clusterer = HDBSCAN(min_cluster_size=max(3, len(embeddings) // 20))
        labels = clusterer.fit_predict(embeddings)

        # If HDBSCAN produces too many noise points, fall back to KMeans
        n_noise = (labels == -1).sum()
        if n_noise > len(labels) * 0.5:
            raise ValueError("Too much noise")

        # Reassign noise points to nearest cluster
        if n_noise > 0:
            valid_mask = labels >= 0
            if valid_mask.any():
                from sklearn.neighbors import NearestCentroid
                nc = NearestCentroid()
                nc.fit(embeddings[valid_mask], labels[valid_mask])
                noise_labels = nc.predict(embeddings[~valid_mask])
                labels[~valid_mask] = noise_labels

        return labels

    except Exception:
        # Fallback: KMeans (always works)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        return kmeans.fit_predict(embeddings)


def get_cluster_representatives(
    posts: list[dict],
    embeddings: np.ndarray,
    labels: np.ndarray,
) -> dict:
    """For each cluster, find the most representative posts.

    Returns {cluster_id: {"posts": [...], "center_idx": int, "count": int}}
    """
    clusters = {}
    unique_labels = set(labels)

    for label in unique_labels:
        if label < 0:
            continue
        mask = labels == label
        indices = np.where(mask)[0]
        cluster_embeddings = embeddings[indices]

        # Find centroid
        centroid = cluster_embeddings.mean(axis=0)

        # Find closest post to centroid
        distances = np.linalg.norm(cluster_embeddings - centroid, axis=1)
        center_idx = indices[distances.argmin()]

        # Get top 3 representative posts (closest to center)
        top_indices = indices[distances.argsort()[:3]]

        clusters[int(label)] = {
            "posts": [posts[i] for i in top_indices],
            "center_idx": int(center_idx),
            "count": int(mask.sum()),
        }

    return clusters
