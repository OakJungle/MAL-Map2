import json
from typing import Dict, List, Tuple

from type import Edge

def store_edges(metadata: Dict, filename='data/edges.json') -> List[Edge]:
    edges = get_edges(metadata)

    # filter + sort
    edges = [e for e in edges if e[2] > 0.03]
    edges.sort(key=lambda e: e[0] - e[1], reverse=True)

    # format output (like toPrecision(3))
    out = [[e[0], e[1], float(f"{e[2]:.3g}")] for e in edges]

    with open(filename, 'w') as f:
        json.dump({"Edges": out}, f)

    return edges


def get_edges(metadatas: Dict) -> List[Edge]:
    edge_dict: Dict[str, List[float]] = {}

    def add_to_edge(a: int, b: int, w: float):
        if b not in metadatas or a not in metadatas:
            return

        s = min(a, b)
        t = max(a, b)
        eid = f"{s}-{t}"

        if eid not in edge_dict:
            edge_dict[eid] = [s, t, 0.0]

        edge_dict[eid][2] += w

    for id_str, metadata in metadatas.items():
        a = int(id_str)

        recs = metadata.get("recommendations", [])

        total_recs = sum(r.get("count", 0) for r in recs)
        if total_recs == 0:
            continue

        for rec in recs:
            add_to_edge(a, rec["id"], rec.get("count", 0) / total_recs / 2)

    return [(int(e[0]), int(e[1]), float(e[2])) for e in edge_dict.values()]