import json
import subprocess
import time
from typing import List, Dict, Optional, Tuple
from type import Edge


class Cluster:
    max_id = 0
    adj_list: Dict[int, List[int]] = {}

    def __init__(self, id: int, tier: int, nodes: Optional[List[int]] = None):
        self.id = id
        self.tier = tier
        self.nodes = nodes or []
        self.clusters: List["Cluster"] = []

        Cluster.max_id = max(id, Cluster.max_id)

    @staticmethod
    def set_edges(edges: List[Edge]):
        Cluster.adj_list = {}
        for a, b, _ in edges:
            Cluster.adj_list.setdefault(a, []).append(b)
            Cluster.adj_list.setdefault(b, []).append(a)

    def insert(self, id: int, levels: List[int]):
        if not levels:
            self.nodes.append(id)
        else:
            target_id = levels[0]
            c = next((c for c in self.clusters if c.id == target_id), None)

            if c:
                c.insert(id, levels[1:])
            else:
                cluster = Cluster(target_id, self.tier + 1)
                cluster.insert(id, levels[1:])
                self.clusters.append(cluster)

    def size(self) -> int:
        return len(self.nodes) + sum(c.size() for c in self.clusters)

    def all_nodes(self) -> List[int]:
        result = list(self.nodes)
        for c in self.clusters:
            result.extend(c.all_nodes())
        return result

    def distance(self, cluster: "Cluster") -> float:
        nodes = self.all_nodes()
        other_nodes = cluster.all_nodes()

        num_potential_edges = len(nodes) * len(other_nodes)
        if num_potential_edges == 0:
            return 0

        edges_found = 0
        for n in nodes:
            neighbors = Cluster.adj_list.get(n, [])
            for o in other_nodes:
                if o in neighbors:
                    edges_found += 1

        return edges_found / num_potential_edges

    def add_cluster(self, cluster: "Cluster"):
        cluster.tier = self.tier + 1
        self.clusters.append(cluster)

    def merge(self, min_prop=0.15, min_size=10):
        threshold = max(min_size, self.size() * min_prop)

        if self.size() < threshold:
            raise Exception("Cluster is too small to merge")

        if self.nodes and self.clusters:
            self.add_cluster(Cluster(Cluster.max_id + 1, self.tier + 1, self.nodes))
            self.nodes = []

        if self.size() < threshold:
            for c in self.clusters:
                self.nodes.extend(c.all_nodes())
            self.clusters = []
            return

        while len(self.clusters) > 2:
            if not self.clusters:
                break

            self.clusters.sort(key=lambda c: c.size())
            smallest = self.clusters[0]

            if smallest.size() >= threshold:
                break

            self.clusters.pop(0)

            closest = min(self.clusters, key=lambda c: self.distance(c), default=None)
            if closest:
                closest.add_cluster(smallest)

        cluster_sizes = [c.size() for c in self.clusters]
        min_csize = min(cluster_sizes) if cluster_sizes else 0

        if self.clusters and min_csize <= threshold:
            for c in self.clusters:
                self.nodes.extend(c.all_nodes())
            self.clusters = []

        for cluster in self.clusters:
            cluster.merge(min_prop, min_size)

    def to_node_dict(self) -> Dict[str, List[int]]:
        result: Dict[str, List[int]] = {}

        for node in self.nodes:
            result[str(node)] = [node]

        for c in self.clusters:
            result.update(c.to_node_dict())

        max_len = max((len(v) for v in result.values()), default=0)

        for node_id, cluster_path in result.items():
            while len(cluster_path) <= max_len:
                cluster_path.insert(0, self.id)

        return result

    def to_json(self):
        return {
            "id": self.id,
            "tier": self.tier,
            "nodes": self.nodes,
            "clusters": [c.to_json() for c in self.clusters],
        }

    @staticmethod
    def from_json(data):
        cluster = Cluster(data["id"], data["tier"], data.get("nodes", []))
        cluster.clusters = [Cluster.from_json(c) for c in data.get("clusters", [])]
        return cluster


# ---------------------------
# Subprocess + create_cluster
# ---------------------------

def exec_shell_command(cmd: str) -> str:
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout or result.stderr
    except Exception as e:
        print(e)
        return ""


async def create_cluster(edges: List[Edge], edge_path='data/edges.txt', cluster_path='data/clusters.json'):
    # Write edges
    with open(edge_path, 'w') as f:
        for e in edges:
            f.write(f"{e[0]} {e[1]} {e[2]}\n")

    print("Creating clusters...")
    start = time.time()

    exec_shell_command(f"python3 cluster_algo.py {edge_path} {cluster_path}")

    print(f"Clustering took {time.time() - start:.2f}s")

    # Process clusters
    print("Merging small clusters...")
    Cluster.set_edges(edges)

    with open(cluster_path, 'r') as f:
        root = Cluster.from_json(json.load(f))

    root.merge()

    # Write merged clusters
    with open(cluster_path, 'w') as f:
        json.dump(root.to_json(), f)

    return root
