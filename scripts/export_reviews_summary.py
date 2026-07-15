import csv
import os
from backend.app.database.session import SessionLocal
from backend.app.database.models import MonthlyCrimeReview, MonthlyReviewCategoryMap, CrimeCategory, CrimeSubcategory

session = SessionLocal()
try:
    rows = session.query(MonthlyCrimeReview).all()
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'datasets', 'exports', 'consolidated_monthly_reviews.csv'))
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id','source_file','month','year','sl_no','heads_of_crime','major_head','minor_head','upto_end_of_month','prev_year_month','previous_month','current_month','category_id','category_name','subcategory_id','subcategory_name','mapping_confidence','mapping_method'])
        for r in rows:
            mapping = session.query(MonthlyReviewCategoryMap).filter(MonthlyReviewCategoryMap.review_id==r.id).first()
            cat_name = None
            sub_name = None
            conf = None
            method = None
            if mapping:
                if mapping.category_id:
                    c = session.get(CrimeCategory, mapping.category_id)
                    cat_name = c.name if c else None
                if mapping.subcategory_id:
                    s = session.get(CrimeSubcategory, mapping.subcategory_id)
                    sub_name = s.name if s else None
                conf = mapping.confidence
                method = mapping.method
            writer.writerow([r.id,r.source_file,r.month,r.year,r.sl_no,r.heads_of_crime,r.major_head,r.minor_head,r.upto_end_of_month,r.corresponding_month_prev_year,r.previous_month,r.current_month,mapping.category_id if mapping else None,cat_name,mapping.subcategory_id if mapping else None,sub_name,conf,method])
    print(f"Exported consolidated CSV to {out_path}")
finally:
    session.close()
