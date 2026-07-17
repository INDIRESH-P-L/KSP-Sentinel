from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "ai-engine"))
from backend.app.database.session import get_db
from backend.app.core.security import deny_admin_from_crime_data
from backend.app.core.masking import REDACTED
from graph.network_builder import CriminalNetworkBuilder

router = APIRouter(prefix="/network", tags=["Network Analysis"])

def _mask_network_for_role(network_data: dict, role: str) -> dict:
    """The graph's node `label` is rendered directly on the visualization (not just a
    detail panel), so it's the actual PII surface here -- an Analyst account (per the
    masking rules in backend/app/core/masking.py: no personal fields) should see an
    anonymized graph shape, not real suspect/victim names on-screen."""
    if role.lower() != "analyst":
        return network_data

    for node in network_data.get("nodes", []):
        if node.get("type") in ("accused", "victim"):
            node["label"] = REDACTED
            if node.get("gender"):
                node["gender"] = REDACTED
            if "modus_operandi" in node:
                node["modus_operandi"] = REDACTED
            if node.get("linked_cases"):
                node["linked_cases"] = []  # case descriptions can themselves be identifying

    for group_key in ("master_criminals", "repeat_offenders", "bridge_suspects"):
        for entry in network_data.get("metrics", {}).get(group_key, []) or []:
            entry["label"] = REDACTED

    return network_data

@router.get("/")
def get_criminal_network(
    fir_limit: int = Query(1500, ge=1, le=5000, description="Most recent N FIRs to include in the graph"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data)
):
    """Computes Node-Link graphs mapping criminal gangs, priors, and hubs"""
    builder = CriminalNetworkBuilder(db)
    network_data = builder.analyze_network(fir_limit=fir_limit)
    return _mask_network_for_role(network_data, current_user.get("role", ""))
