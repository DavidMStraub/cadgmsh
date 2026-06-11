from __future__ import annotations

import gmsh
import meshio
import numpy as np
from numpy.typing import ArrayLike, NDArray


def _to_meshio() -> meshio.Mesh:
    """
    Extract the current gmsh model into a :class:`meshio.Mesh`.

    Reads nodes, elements, and any named physical groups from the active gmsh
    session and returns them as a meshio-compatible object.
    Must be called while a gmsh session is active (between ``initialize`` /
    ``finalize``) and after ``gmsh.model.mesh.generate``.
    """
    idx, raw_pts, _ = gmsh.model.mesh.getNodes()
    pts: NDArray[np.float64] = np.asarray(raw_pts).reshape(-1, 3)
    node_idx: NDArray[np.int64] = np.asarray(idx, dtype=np.int64) - 1
    srt = np.argsort(node_idx)
    if not np.all(node_idx[srt] == np.arange(len(node_idx))):
        raise ValueError("gmsh returned non-consecutive node indices")
    pts = pts[srt]

    elem_types, elem_tags, node_tags = gmsh.model.mesh.getElements()

    cells: list[tuple[str, ArrayLike] | meshio.CellBlock] = []
    for etype, etags, ntags in zip(elem_types, elem_tags, node_tags, strict=True):
        n: int = gmsh.model.mesh.getElementProperties(etype)[3]
        conn: NDArray[np.int64] = np.asarray(ntags, dtype=np.int64).reshape(-1, n) - 1
        conn = conn[np.argsort(np.asarray(etags, dtype=np.int64))]
        cells.append(meshio.CellBlock(meshio.gmsh.gmsh_to_meshio_type[etype], conn))

    cell_sets: dict[str, list[ArrayLike]] = {}
    for dim, tag in gmsh.model.getPhysicalGroups():
        name = gmsh.model.getPhysicalName(dim, tag)
        groups: list[list[NDArray[np.int64]]] = [[] for _ in range(len(cells))]
        for etag in gmsh.model.getEntitiesForPhysicalGroup(dim, tag):
            etypes_e, etags_e, _ = gmsh.model.mesh.getElements(dim, etag)
            if not etypes_e:
                continue
            mtype = meshio.gmsh.gmsh_to_meshio_type[etypes_e[0]]
            for k, cb in enumerate(cells):
                if isinstance(cb, meshio.CellBlock) and cb.type == mtype:
                    groups[k].append(np.asarray(etags_e[0], dtype=np.int64) - 1)
        cell_sets[name] = [
            np.concatenate(ids) if ids else np.empty(0, dtype=np.int64)
            for ids in groups
        ]

    return meshio.Mesh(pts, cells, cell_sets=cell_sets)
