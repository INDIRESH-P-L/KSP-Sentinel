from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "ai-engine"))
from backend.app.database.session import get_db
from backend.app.dependencies import get_current_user
from graph.network_builder import CriminalNetworkBuilder

router = APIRouter(prefix="/network", tags=["Network Analysis"])

@router.get("/")
def get_criminal_network(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Computes Node-Link graphs mapping criminal gangs, priors, and hubs"""
    builder = CriminalNetworkBuilder(db)
    network_data = builder.analyze_network()
    return network_data
