# Model/utils/safety_graph.py
from collections import defaultdict
from .geometry_utils import haversine  # returns meters

class RoadGraph:
    def __init__(self):
        self.edges = defaultdict(list)      # node -> [(node2, dist)]
        self.risk = {}                      # (node1,node2) -> risk (0–1)

    def add_edge(self, a, b):
        # Ensure nodes are tuples of floats
        a = (float(a[0]), float(a[1]))
        b = (float(b[0]), float(b[1]))

        dist = haversine(a[0], a[1], b[0], b[1])
        # Avoid duplicate neighbor entries
        if not any(n == b for n, _ in self.edges[a]):
            self.edges[a].append((b, dist))
        if not any(n == a for n, _ in self.edges[b]):
            self.edges[b].append((a, dist))

    def set_risk(self, a, b, value):
        a = (float(a[0]), float(a[1]))
        b = (float(b[0]), float(b[1]))
        self.risk[(a, b)] = float(value)
        self.risk[(b, a)] = float(value)

    def get_neighbors(self, node):
        return self.edges.get(node, [])

    def remove_edge(self, a, b):
        removed = False
        if a in self.edges:
            newlist = [(n, d) for n, d in self.edges[a] if n != b]
            if len(newlist) != len(self.edges[a]):
                self.edges[a] = newlist
                removed = True
        if b in self.edges:
            newlist = [(n, d) for n, d in self.edges[b] if n != a]
            if len(newlist) != len(self.edges[b]):
                self.edges[b] = newlist
                removed = True
        return removed

    def restore_edge(self, a, b):
        dist = haversine(a[0], a[1], b[0], b[1])
        # add if missing
        if not any(n == b for n, _ in self.edges[a]):
            self.edges[a].append((b, dist))
        if not any(n == a for n, _ in self.edges[b]):
            self.edges[b].append((a, dist))

    def has_edge(self, a, b):
        return any(n == b for n, _ in self.edges.get(a, []))