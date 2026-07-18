import networkx as nx
from sqlalchemy.orm import Session
import sys
import os

# Add paths to make imports clean
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from app.database.models import FIR, Victim, PoliceStation, Arrest

class CriminalNetworkBuilder:
    def __init__(self, db: Session):
        self.db = db
        self.G = nx.Graph()
        self.accused_by_node_id = {}
        self.firs_by_accused_node_id = {}

    def build_network(self, fir_limit: int = 1500):
        """Builds a multipartite graph of Accused, Victims, Stations, and Crimes.

        fir_limit caps how many (most recent) FIRs feed the graph. Without a cap, a
        full-scale dataset (tens of thousands of FIRs, each with its own accused rows)
        produces a graph with 10,000s of nodes -- and the exact betweenness_centrality
        computed below is O(V*E), which is fine on a demo-sized seed but can hang for
        minutes to hours at that scale. Most recent activity is also what an
        investigator actually wants front and center."""
        self.G.clear()

        # 1. Fetch the most recent FIRs and their associations
        firs = self.db.query(FIR).order_by(FIR.date_reported.desc()).limit(fir_limit).all()
        
        for f in firs:
            station_name = f.station.name if f.station else "Unknown Station"
            crime_type = f.subcategory.name if f.subcategory else "General Crime"
            
            # Add Station Node
            self.G.add_node(station_name, type="station", label=station_name)
            
            # Add Crime Type Node
            self.G.add_node(crime_type, type="crime_type", label=crime_type)
            
            # Link Station to Crime Type
            self.G.add_edge(station_name, crime_type, relationship="station_crime")
            
            # Add Victim Nodes
            for v in f.victims:
                v_node_id = f"Victim: {v.name}"
                self.G.add_node(v_node_id, type="victim", label=v.name, gender=v.gender, age=v.age)
                self.G.add_edge(v_node_id, crime_type, relationship="victim_crime")
                self.G.add_edge(v_node_id, station_name, relationship="victim_station")
                
            # Add Accused Nodes
            acc_list = f.accused_list
            for a in acc_list:
                a_node_id = f"Accused: {a.name}"
                self.accused_by_node_id[a_node_id] = a
                self.firs_by_accused_node_id.setdefault(a_node_id, []).append(f)
                self.G.add_node(a_node_id, type="accused", label=a.name, gender=a.gender, age=a.age, priors=a.prior_offenses_count)
                
                # Link Accused to Crime Type & Station
                self.G.add_edge(a_node_id, crime_type, relationship="accused_crime")
                self.G.add_edge(a_node_id, station_name, relationship="accused_station")
                
                # Link Accused to Victims of this FIR
                for v in f.victims:
                    v_node_id = f"Victim: {v.name}"
                    self.G.add_edge(a_node_id, v_node_id, relationship="accused_victim")
            
            # Co-accused Links: Link all accused members of the same FIR to each other (representing gang links)
            if len(acc_list) > 1:
                for idx1 in range(len(acc_list)):
                    for idx2 in range(idx1 + 1, len(acc_list)):
                        a1_id = f"Accused: {acc_list[idx1].name}"
                        a2_id = f"Accused: {acc_list[idx2].name}"
                        self.G.add_edge(a1_id, a2_id, relationship="co_accused", weight=1.5)

    def analyze_network(self, fir_limit: int = 1500):
        """Calculates centralities and community structures"""
        if len(self.G) == 0:
            self.build_network(fir_limit=fir_limit)

        if len(self.G) == 0:
            return {"nodes": [], "edges": [], "metrics": {}}

        # 1. Centrality metrics
        deg_centrality = nx.degree_centrality(self.G)

        try:
            pagerank = nx.pagerank(self.G, alpha=0.85)
        except Exception:
            pagerank = deg_centrality # Fallback

        try:
            # Exact betweenness is O(V*E); sample source nodes once the graph gets large
            # rather than walking every node's shortest paths.
            k = min(200, len(self.G)) if len(self.G) > 500 else None
            betweenness = nx.betweenness_centrality(self.G, k=k, seed=42)
        except Exception:
            betweenness = deg_centrality # Fallback

        # 2. Community Detection (Gangs) using Label Propagation
        communities = {}
        try:
            comm_list = list(nx.community.label_propagation_communities(self.G))
            for comm_idx, comm in enumerate(comm_list):
                for node in comm:
                    communities[node] = comm_idx
        except Exception:
            # Fallback
            communities = {node: 0 for node in self.G.nodes()}

        # 3. Format nodes and edges list for frontend viz
        nodes = []
        for node, attrs in self.G.nodes(data=True):
            node_type = attrs.get("type", "unknown")
            
            # Base size and color by type
            val = float(pagerank.get(node, 0.0))
            
            # Custom formatting
            node_data = {
                "id": node,
                "label": attrs.get("label", node),
                "type": node_type,
                "centrality": round(float(deg_centrality.get(node, 0)), 4),
                "pagerank": round(val, 4),
                "betweenness": round(float(betweenness.get(node, 0)), 4),
                "community": int(communities.get(node, 0)),
                "gender": attrs.get("gender"),
                "age": attrs.get("age"),
                "priors": attrs.get("priors", 0)
            }
            
            if node_type == "accused":
                # Reuse the Accused/FIR objects already loaded during build_network instead
                # of re-querying by (unindexed) name, or lazy-loading acc_db.firs, per node --
                # an N+1 pattern that's fine on a handful of nodes but grinds to a halt at
                # full-dataset scale.
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
                    
                    subcats = [f.subcategory.name for f in linked_firs if f.subcategory]
                    if subcats:
                        from collections import Counter
                        counts = Counter(subcats)
                        primary_mo = counts.most_common(1)[0][0]
                        districts_involved = set(d["district"] for d in node_data["linked_cases"])
                        node_data["modus_operandi"] = f"Suspect operates cross-jurisdictionally in {', '.join(districts_involved)}. Modus Operandi concentrates on **{primary_mo}** operations."
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
            
        # 4. Find Master Criminals (highly central accused nodes)
        accused_nodes = [n for n in nodes if n["type"] == "accused"]
        master_criminals = sorted(accused_nodes, key=lambda x: (x["pagerank"], x["priors"]), reverse=True)[:5]
        
        # 5. Repeat Offenders
        repeat_offenders = sorted(accused_nodes, key=lambda x: x["priors"], reverse=True)[:5]

        # 6. Bridge suspects: high betweenness centrality, not necessarily high pagerank.
        # These are the individuals connecting otherwise-separate clusters (co-accused rings
        # that don't overlap directly) -- often the actual coordinators between gangs, distinct
        # from "most connected" which master_criminals/pagerank already covers.
        bridge_suspects = sorted(accused_nodes, key=lambda x: x["betweenness"], reverse=True)[:5]

        return {
            "nodes": nodes,
            "edges": edges,
            "metrics": {
                "master_criminals": master_criminals,
                "repeat_offenders": repeat_offenders,
                "bridge_suspects": bridge_suspects,
                "total_nodes": len(self.G),
                "total_edges": len(self.G.edges())
            }
        }
