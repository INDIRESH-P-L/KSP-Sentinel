import sys
import os
from sqlalchemy.orm import Session

# Add paths to make imports clean
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from app.database.models import FIR, Victim, PoliceStation, Arrest

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

class SimpleGraph:
    def __init__(self):
        self._nodes = {}
        self._edges = {}

    def clear(self):
        self._nodes.clear()
        self._edges.clear()

    def add_node(self, n, **kwargs):
        self._nodes[n] = kwargs

    def add_edge(self, u, v, **kwargs):
        if u not in self._nodes:
            self._nodes[u] = {}
        if v not in self._nodes:
            self._nodes[v] = {}
        self._edges.setdefault(u, {})[v] = kwargs
        self._edges.setdefault(v, {})[u] = kwargs

    def __len__(self):
        return len(self._nodes)

    def nodes(self, data=False):
        if data:
            return self._nodes.items()
        return self._nodes.keys()

    def edges(self, data=False):
        seen = set()
        res = []
        for u in self._edges:
            for v, attrs in self._edges[u].items():
                if (v, u) not in seen:
                    seen.add((u, v))
                    res.append((u, v, attrs) if data else (u, v))
        return res


def _build_station_coord_index():
    """
    Build a {station_name_lower: (lat, lng, district)} lookup from the
    Zoho Catalyst FileStore dataset -- which covers all 31+ districts of Karnataka.
    Falls back to an empty dict if the dataset is not yet loaded.
    """
    try:
        from app import filestore_crime_data
        ds = filestore_crime_data.get_dataset()
        if ds is None:
            return {}
        _, _, stations_df, *_ = ds
        index = {}
        for _, row in stations_df.iterrows():
            name = str(row.get("name", "")).strip()
            lat  = row.get("latitude")
            lng  = row.get("longitude")
            dist = str(row.get("district_name", ""))
            if name and lat and lng:
                try:
                    index[name.lower()] = (float(lat), float(lng), dist)
                except (ValueError, TypeError):
                    pass
        return index
    except Exception:
        return {}


class CriminalNetworkBuilder:
    def __init__(self, db: Session):
        self.db = db
        self.G = nx.Graph() if HAS_NETWORKX else SimpleGraph()
        self.accused_by_node_id = {}
        self.firs_by_accused_node_id = {}
        # Karnataka-wide station coordinates from Zoho Catalyst FileStore
        self._station_coords = _build_station_coord_index()

    def _station_lat_lng(self, station_name: str):
        """Return (lat, lng, district) for a station name, or (None, None, None)."""
        if not station_name:
            return None, None, None
        key = station_name.lower().strip()
        if key in self._station_coords:
            return self._station_coords[key]
        # Normalised match: strip Police Station / PS suffix
        for suffix in (" police station", " ps", " p.s.", " p.s"):
            stripped = key.replace(suffix, "").strip()
            if stripped in self._station_coords:
                return self._station_coords[stripped]
        return None, None, None

    def build_network(self, fir_limit: int = 5000):
        self.G.clear()
        firs = self.db.query(FIR).order_by(FIR.date_reported.desc()).limit(fir_limit).all()

        for f in firs:
            station_name = f.station.name if f.station else "Unknown Station"
            crime_type   = f.subcategory.name if f.subcategory else "General Crime"

            # Attach Karnataka-wide coordinates to station node
            s_lat, s_lng, s_dist = self._station_lat_lng(station_name)
            self.G.add_node(station_name, type="station", label=station_name,
                            lat=s_lat, lng=s_lng, district=s_dist or "")

            # Crime type node -- approximate with station location
            if crime_type not in dict(self.G.nodes(data=True) if HAS_NETWORKX else self.G._nodes):
                self.G.add_node(crime_type, type="crime_type", label=crime_type,
                                lat=s_lat, lng=s_lng)
            self.G.add_edge(station_name, crime_type, relationship="station_crime")

            for v in f.victims:
                v_node_id = f"Victim: {v.name}"
                self.G.add_node(v_node_id, type="victim", label=v.name,
                                gender=v.gender, age=v.age,
                                lat=s_lat, lng=s_lng)
                self.G.add_edge(v_node_id, crime_type, relationship="victim_crime")
                self.G.add_edge(v_node_id, station_name, relationship="victim_station")

            acc_list = f.accused_list
            for a in acc_list:
                a_node_id = f"Accused: {a.name}"
                self.accused_by_node_id[a_node_id] = a
                self.firs_by_accused_node_id.setdefault(a_node_id, []).append(f)
                self.G.add_node(a_node_id, type="accused", label=a.name,
                                gender=a.gender, age=a.age,
                                priors=a.prior_offenses_count)

                self.G.add_edge(a_node_id, crime_type, relationship="accused_crime")
                self.G.add_edge(a_node_id, station_name, relationship="accused_station")

                for v in f.victims:
                    v_node_id = f"Victim: {v.name}"
                    self.G.add_edge(a_node_id, v_node_id, relationship="accused_victim")

            if len(acc_list) > 1:
                for idx1 in range(len(acc_list)):
                    for idx2 in range(idx1 + 1, len(acc_list)):
                        a1_id = f"Accused: {acc_list[idx1].name}"
                        a2_id = f"Accused: {acc_list[idx2].name}"
                        self.G.add_edge(a1_id, a2_id, relationship="co_accused", weight=1.5)

    def analyze_network(self, fir_limit: int = 5000):
        if len(self.G) == 0:
            self.build_network(fir_limit=fir_limit)

        if len(self.G) == 0:
            return {"nodes": [], "edges": [], "links": [], "metrics": {}}

        if HAS_NETWORKX:
            deg_centrality = nx.degree_centrality(self.G)
            try:
                pagerank = nx.pagerank(self.G, alpha=0.85)
            except Exception:
                pagerank = deg_centrality
            try:
                k = min(200, len(self.G)) if len(self.G) > 500 else None
                betweenness = nx.betweenness_centrality(self.G, k=k, seed=42)
            except Exception:
                betweenness = deg_centrality
            communities = {}
            try:
                comm_list = list(nx.community.label_propagation_communities(self.G))
                for comm_idx, comm in enumerate(comm_list):
                    for node in comm:
                        communities[node] = comm_idx
            except Exception:
                communities = {node: 0 for node in self.G.nodes()}
        else:
            n_nodes = max(1, len(self.G))
            deg_centrality = {}
            pagerank = {}
            betweenness = {}
            communities = {}
            for node, attrs in self.G.nodes(data=True):
                degree = len(self.G._edges.get(node, {}))
                deg_centrality[node] = degree / float(n_nodes)
                pagerank[node] = deg_centrality[node]
                betweenness[node] = deg_centrality[node]
                communities[node] = 0

        nodes = []
        for node, attrs in self.G.nodes(data=True):
            node_type = attrs.get("type", "unknown")
            val = float(pagerank.get(node, 0.0))

            node_data = {
                "id": node,
                "label": attrs.get("label", node),
                "type": node_type,
                "centrality": round(float(deg_centrality.get(node, 0)), 4),
                "pagerank": round(val, 4),
                "betweenness": round(float(betweenness.get(node, 0)), 4),
                "community": int(communities.get(node, 0)),
                "gang": str(communities.get(node, 0)),
                "gender": attrs.get("gender"),
                "age": attrs.get("age"),
                "priors": attrs.get("priors", 0),
                "district": attrs.get("district", ""),
                # Coordinates from the Zoho Catalyst FileStore (Karnataka-wide)
                "lat": attrs.get("lat"),
                "lng": attrs.get("lng"),
            }

            if node_type == "accused":
                acc_db = self.accused_by_node_id.get(node)
                if acc_db:
                    linked_firs = self.firs_by_accused_node_id.get(node, [])
                    node_data["linked_cases"] = [{
                        "fir_number": f.fir_number,
                        "date": f.date_reported.strftime("%Y-%m-%d") if f.date_reported else "N/A",
                        "station": f.station.name if f.station else "Unknown PS",
                        "district": f.station.district.name if (f.station and f.station.district) else "Unknown District",
                        "crime": f.subcategory.name if f.subcategory else "General",
                        "description": f.description
                    } for f in linked_firs]

                    # Geographic center -- prefer FIR lat/lng, fall back to station coords
                    coord_list = []
                    for fir in linked_firs:
                        if fir.latitude and fir.longitude:
                            coord_list.append((float(fir.latitude), float(fir.longitude)))
                        else:
                            sn = fir.station.name if fir.station else ""
                            sl, sg, _ = self._station_lat_lng(sn)
                            if sl and sg:
                                coord_list.append((sl, sg))
                    if coord_list:
                        node_data["lat"] = sum(x[0] for x in coord_list) / len(coord_list)
                        node_data["lng"] = sum(x[1] for x in coord_list) / len(coord_list)

                    subcats = [f.subcategory.name for f in linked_firs if f.subcategory]
                    if subcats:
                        from collections import Counter
                        counts = Counter(subcats)
                        primary_mo = counts.most_common(1)[0][0]
                        districts_involved = set(d["district"] for d in node_data["linked_cases"])
                        node_data["modus_operandi"] = (
                            f"Suspect operates cross-jurisdictionally in "
                            f"{', '.join(districts_involved)}. "
                            f"Modus Operandi concentrates on **{primary_mo}** operations."
                        )
                    else:
                        node_data["modus_operandi"] = "Modus Operandi details under verification."
                else:
                    node_data["linked_cases"] = []
                    node_data["modus_operandi"] = "No linked cases found."

            nodes.append(node_data)

        edges = []
        for u, v, attrs in self.G.edges(data=True):
            edges.append({
                "source": u,
                "target": v,
                "relationship": attrs.get("relationship", "link"),
                "weight": float(attrs.get("weight", 1.0))
            })

        accused_nodes    = [n for n in nodes if n["type"] == "accused"]
        master_criminals = sorted(accused_nodes, key=lambda x: (x["pagerank"], x["priors"]), reverse=True)[:5]
        repeat_offenders = sorted(accused_nodes, key=lambda x: x["priors"], reverse=True)[:5]
        bridge_suspects  = sorted(accused_nodes, key=lambda x: x["betweenness"], reverse=True)[:5]

        return {
            "nodes": nodes,
            "edges": edges,
            "links": edges,   # alias so frontend `links` key works directly
            "metrics": {
                "master_criminals": master_criminals,
                "repeat_offenders": repeat_offenders,
                "bridge_suspects": bridge_suspects,
                "total_nodes": len(self.G),
                "total_edges": len(self.G.edges())
            }
        }
