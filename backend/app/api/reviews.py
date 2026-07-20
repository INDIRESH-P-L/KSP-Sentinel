from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from app.database.session import SessionLocal
from app.database.models import MonthlyCrimeReview, MonthlyReviewCategoryMap, CrimeCategory, CrimeSubcategory
from app import filestore_data
from app.logging import logger

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get('/reviews')
def list_reviews(month: Optional[int] = Query(None), year: Optional[int] = Query(None), limit: int = 200, offset: int = 0, db: SessionLocal = Depends(get_db)):
    # Primary source: the monthly-review CSVs in the Catalyst FileStore. Returns None on
    # any failure (SDK/config/download/parse), in which case we fall through to the
    # existing Datastore path below unchanged. No Datastore writes happen either way.
    fs = filestore_data.get_reviews(month=month, year=year, limit=limit, offset=offset)
    if fs is not None:
        return fs
    logger.info("reviews: FileStore source unavailable; serving /reviews from the Datastore.")

    q = db.query(MonthlyCrimeReview)
    if month:
        q = q.filter(MonthlyCrimeReview.month == month)
    if year:
        q = q.filter(MonthlyCrimeReview.year == year)
    total = q.count()
    results = q.offset(offset).limit(limit).all()
    out = {
        'total': total,
        'limit': limit,
        'offset': offset,
        'items': []
    }
    for r in results:
        mapping = db.query(MonthlyReviewCategoryMap).filter(MonthlyReviewCategoryMap.review_id==r.id).first()
        mapped_cat = None
        mapped_sub = None
        conf = None
        method = None
        if mapping:
            conf = mapping.confidence
            method = mapping.method
            if mapping.category_id:
                c = db.get(CrimeCategory, mapping.category_id)
                mapped_cat = {'id': mapping.category_id, 'name': c.name if c else None}
            if mapping.subcategory_id:
                s = db.get(CrimeSubcategory, mapping.subcategory_id)
                mapped_sub = {'id': mapping.subcategory_id, 'name': s.name if s else None}
        out['items'].append({
            'id': r.id,
            'source_file': r.source_file,
            'month': r.month,
            'year': r.year,
            'sl_no': r.sl_no,
            'heads_of_crime': r.heads_of_crime,
            'major_head': r.major_head,
            'minor_head': r.minor_head,
            'upto_end_of_month': r.upto_end_of_month,
            'previous_month': r.previous_month,
            'current_month': r.current_month,
            'mapped_category': mapped_cat,
            'mapped_subcategory': mapped_sub,
            'mapping_confidence': conf,
            'mapping_method': method
        })
    return out
