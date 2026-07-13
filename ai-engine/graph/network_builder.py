import networkx as nx
from sqlalchemy.orm import Session
import sys
import os

# Add paths to make imports clean
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from backend.app.database.models import FIR, Accused, Victim, PoliceStation, Arrest

class CriminalNetworkBuilder:
    def __init__(self, db: Session):
        self.db = db
        self.G = nx.Graph()

    def build_network(self):
        """Builds a multipartite graph of Accused, Victims, Stations, and Crimes"""
        self.G.clear()
        
        # 1. Fetch all FIRs and their associations
        firs = self.db.query(FIR).all()
        
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

    def analyze_network(self):
        """Calculates centralities and community structures"""
        if len(self.G) == 0:
            self.build_network()
            
        if len(self.G) == 0:
            return {"nodes": [], "edges": [], "metrics": {}}
            
        # 1. Centrality metrics
        deg_centrality = nx.degree_centrality(self.G)
        
        try:
            pagerank = nx.pagerank(self.G, alpha=0.85)
        except Exception:
            pagerank = deg_centrality # Fallback
            
        try:
            betweenness = nx.betweenness_centrality(self.G)
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

        return {
            "nodes": nodes,
            "edges": edges,
            "metrics": {
                "master_criminals": master_criminals,
                "repeat_offenders": repeat_offenders,
                "total_nodes": len(self.G),
                "total_edges": len(self.G.edges())
            }
        }
