import math
import random
from typing import Dict, List, Sequence, Tuple
from type import Edge as EdgeType


class Node:
    def __init__(self, id: int):
        self.id = id
        self.x = 0.0
        self.y = 0.0
        self.hue = 0.0

    def norm(self):
        return math.sqrt(self.x * self.x + self.y * self.y)


class Edge:
    def __init__(self, source: Node, target: Node, weight: float):
        self.source = source
        self.target = target
        self.weight = weight


class Layout:
    def __init__(self, clusters: Dict[str, List[int]], edges: Sequence[EdgeType], min_colors=20):
        self.Clusters = clusters
        self.Cluster_Nodes: Dict[int, List[int]] = {}
        self.Edges = edges
        self.edges: List[Edge] = []
        self.min_colors = min_colors

        self.nodes: List[Node] = []
        self.done = False
        self.tier = 0
        self.alpha = 0.25  # simulation energy

        self.init_cluster_map()

    # -----------------------
    # Core simulation
    # -----------------------

    def tick(self, iters=1):
        if self.alpha < 0.01:
            self.done = True
            return

        for _ in range(iters):
            self.apply_forces()

        self.normalize_density()
        self.alpha *= 0.98  # decay

        if self.tier <= self.max_tier() and self.alpha < 0.05:
            self.nodes = self.new_cluster_nodes(self.nodes, self.tier)
            self.edges = self.get_cluster_edges(self.tier, self.nodes)
            self.tier += 1
            print(f"Laying out cluster tier {self.tier}...")
            self.alpha = 0.25

    def apply_forces(self):
        # Repulsion
        for i, a in enumerate(self.nodes):
            for b in self.nodes[i + 1:]:
                dx = a.x - b.x
                dy = a.y - b.y
                dist = math.sqrt(dx * dx + dy * dy) + 0.01
                force = 50 / dist

                a.x += dx / dist * force * 0.01
                a.y += dy / dist * force * 0.01
                b.x -= dx / dist * force * 0.01
                b.y -= dy / dist * force * 0.01

        # Attraction (edges)
        for edge in self.edges:
            dx = edge.source.x - edge.target.x
            dy = edge.source.y - edge.target.y
            dist = math.sqrt(dx * dx + dy * dy) + 0.01

            force = edge.weight * (dist - 50)

            edge.source.x -= dx / dist * force * 0.01
            edge.source.y -= dy / dist * force * 0.01
            edge.target.x += dx / dist * force * 0.01
            edge.target.y += dy / dist * force * 0.01

    # -----------------------
    # Helpers
    # -----------------------

    def normalize_density(self, target_density=0.00007):
        if not self.nodes:
            return

        max_norm = max(node.norm() for node in self.nodes)
        area = math.pi * max_norm * max_norm
        target_area = len(self.nodes) / target_density

        if area == 0:
            return

        scale = math.sqrt(target_area / area)

        for node in self.nodes:
            node.x *= scale
            node.y *= scale

    def max_tier(self):
        return len(self.Clusters["1"]) - 1

    def init_cluster_map(self):
        for node_id, cluster_ids in self.Clusters.items():
            for cluster_id in set(cluster_ids):
                self.Cluster_Nodes.setdefault(cluster_id, []).append(int(node_id))

    def assign_hues(self, nodes: List[Node], min_hue: float, max_hue: float):
        nodes.sort(key=lambda n: len(self.Cluster_Nodes.get(n.id, [])))

        shuffled = nodes[2:]
        random.shuffle(shuffled)
        shuffled = nodes[:2] + shuffled

        middle = len(shuffled) // 2
        shuffled[1], shuffled[middle] = shuffled[middle], shuffled[1]

        rng = max_hue - min_hue
        for i, node in enumerate(shuffled):
            node.hue = rng * i / len(shuffled) + min_hue

    def get_cluster(self, id: int, tier: int) -> int:
        if tier < 0:
            tier = len(self.Clusters[str(id)]) + tier
        return self.Clusters[str(id)][tier]

    def new_cluster_nodes(self, old_nodes: List[Node], tier: int) -> List[Node]:
        if tier == 0:
            ids = list(set(v[0] for v in self.Clusters.values()))
            return [Node(id) for id in ids]

        ids = list(set(v[tier] for v in self.Clusters.values()))

        parents = {}
        for node_id, cluster in self.Clusters.items():
            parents[cluster[tier]] = cluster[tier - 1]

        def jiggle():
            return (random.random() - 0.5) * 10

        nodes = []
        for id in ids:
            parent_node = next(n for n in old_nodes if n.id == parents[id])
            new_node = Node(id)
            new_node.x = parent_node.x + jiggle()
            new_node.y = parent_node.y + jiggle()
            new_node.hue = parent_node.hue
            nodes.append(new_node)

        if len(old_nodes) < self.min_colors and len(nodes) >= self.min_colors:
            self.assign_hues(nodes, 0, 360)

        return nodes

    def get_cluster_edges(self, tier: int, nodes: List[Node]) -> List[Edge]:
        node_dict = {node.id: node for node in nodes}
        edge_dict: Dict[str, float] = {}

        for a, b, weight in self.Edges:
            s = self.get_cluster(a, tier)
            t = self.get_cluster(b, tier)

            if s == t:
                continue

            if tier > 1 and self.get_cluster(a, tier - 2) != self.get_cluster(b, tier - 2):
                continue

            if tier > 0:
                if self.get_cluster(a, tier - 1) != self.get_cluster(b, tier - 1):
                    weight /= 30

            key = f"{min(s, t)}-{max(s, t)}"
            edge_dict[key] = edge_dict.get(key, 0) + weight

        if not edge_dict:
            return []

        max_weight = max(edge_dict.values())

        for key in edge_dict:
            if tier == self.max_tier():
                edge_dict[key] = math.sqrt(edge_dict[key]) / 3
            else:
                edge_dict[key] /= max_weight

        self.edges = []
        for key, weight in edge_dict.items():
            s, t = map(int, key.split("-"))
            self.edges.append(Edge(node_dict[s], node_dict[t], weight))

        return self.edges

    def to_json(self):
        positions = {}
        for node in self.nodes:
            positions[node.id] = {
                "x": node.x,
                "y": node.y,
                "hue": node.hue,
            }

        edges = []
        for edge in self.edges:
            edges.append([edge.source.id, edge.target.id, edge.weight])

        return {"nodes": positions, "edges": edges}
