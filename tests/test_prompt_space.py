import numpy as np

from creative_machine.prompt_space import PromptSpace


def test_distances_rank_outlier_far_from_cluster():
    rng = np.random.default_rng(0)
    cluster = rng.normal(size=(50, 8)) * 0.05 + np.array([1.0] + [0.0] * 7)
    cluster /= np.linalg.norm(cluster, axis=1, keepdims=True)
    space = PromptSpace(cluster)
    inside = cluster[0]
    outlier = np.array([0.0] * 7 + [1.0])
    d = space.distances(np.stack([inside, outlier]), k=5)
    assert d[0]["centroid_distance"] < d[1]["centroid_distance"]
    assert d[0]["knn_distance"] < d[1]["knn_distance"]
    assert d[1]["knn_distance"] > 0.9  # orthogonal to everything


def test_centroid_is_unit_norm():
    space = PromptSpace(np.eye(4))
    assert np.isclose(np.linalg.norm(space.centroid), 1.0)
