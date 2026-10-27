"""
IoU computation and linear assignment for ByteTrack's two-stage matching.

Uses numpy for IoU (no cython-bbox dependency) and scipy's Hungarian
algorithm for assignment (no `lap` dependency) — same result, fewer
compiled dependencies to install for a hackathon MVP.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment


def iou_batch(bboxes1: list[tuple[float, float, float, float]], bboxes2: list[tuple[float, float, float, float]]) -> np.ndarray:
    """Vectorized IoU between two lists of (x1, y1, x2, y2) boxes."""
    if len(bboxes1) == 0 or len(bboxes2) == 0:
        return np.zeros((len(bboxes1), len(bboxes2)), dtype=float)

    b1 = np.asarray(bboxes1, dtype=float)
    b2 = np.asarray(bboxes2, dtype=float)

    x11, y11, x12, y12 = b1[:, 0:1], b1[:, 1:2], b1[:, 2:3], b1[:, 3:4]
    x21, y21, x22, y22 = b2[:, 0], b2[:, 1], b2[:, 2], b2[:, 3]

    xi1 = np.maximum(x11, x21)
    yi1 = np.maximum(y11, y21)
    xi2 = np.minimum(x12, x22)
    yi2 = np.minimum(y12, y22)

    inter_w = np.clip(xi2 - xi1, 0, None)
    inter_h = np.clip(yi2 - yi1, 0, None)
    inter_area = inter_w * inter_h

    area1 = (x12 - x11) * (y12 - y11)
    area2 = (x22 - x21) * (y22 - y21)
    union = area1 + area2 - inter_area

    return np.where(union > 0, inter_area / union, 0.0)


def linear_assignment(
    cost_matrix: np.ndarray, thresh: float
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Hungarian assignment, rejecting matches above `thresh` cost.

    Returns (matches, unmatched_rows, unmatched_cols).
    """
    if cost_matrix.size == 0:
        return [], list(range(cost_matrix.shape[0])), list(range(cost_matrix.shape[1]))

    row_idx, col_idx = linear_sum_assignment(cost_matrix)

    matches: list[tuple[int, int]] = []
    unmatched_rows = set(range(cost_matrix.shape[0]))
    unmatched_cols = set(range(cost_matrix.shape[1]))
    for r, c in zip(row_idx, col_idx):
        if cost_matrix[r, c] <= thresh:
            matches.append((r, c))
            unmatched_rows.discard(r)
            unmatched_cols.discard(c)

    return matches, sorted(unmatched_rows), sorted(unmatched_cols)
