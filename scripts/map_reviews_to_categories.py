from backend.app.database.session import SessionLocal, engine
from backend.app.database.models import Base, MonthlyCrimeReview, CrimeCategory, CrimeSubcategory, MonthlyReviewCategoryMap
from sqlalchemy import func
import difflib
import re

# Ensure mapping table exists
Base.metadata.create_all(bind=engine)

session = SessionLocal()

def normalize(text: str):
    if not text:
        return ''
    t = text.lower()
    t = re.sub(r"[^a-z0-9\s]", ' ', t)
    t = re.sub(r"\s+", ' ', t).strip()
    return t

try:
    reviews = session.query(MonthlyCrimeReview).all()
    categories = session.query(CrimeCategory).all()
    subcats = session.query(CrimeSubcategory).all()

    # prepare lowercase name lists
    cat_names = [(c.id, normalize(c.name)) for c in categories]
    sub_names = [(s.id, normalize(s.name), s.category_id) for s in subcats]

    inserted = 0
    for r in reviews:
        # try to match subcategory first using minor_head and major_head
        text_candidates = ' '.join(filter(None, [r.minor_head, r.major_head, r.heads_of_crime]))
        text_norm = normalize(text_candidates)
        matched_cat_id = None
        matched_sub_id = None
        confidence = None
        method = None

        if text_norm:
            # substring match for subcategory
            for sid, sname, sc_cat in sub_names:
                if sname and sname in text_norm:
                    matched_sub_id = sid
                    matched_cat_id = sc_cat
                    confidence = 0.95
                    method = 'substring'
                    break

        # category substring match
        if matched_sub_id is None and text_norm:
            for cid, cname in cat_names:
                if cname and cname in text_norm:
                    matched_cat_id = cid
                    confidence = 0.9
                    method = 'substring'
                    break

        # token overlap scoring
        if matched_cat_id is None and text_norm:
            tokens = set([t for t in text_norm.split() if len(t) > 3])
            best = (None, 0)
            for cid, cname in cat_names:
                cname_tokens = set(cname.split())
                common = len(tokens & cname_tokens)
                if common > best[1]:
                    best = (cid, common)
            if best[0] is not None and best[1] > 0:
                # derive confidence from common token ratio
                matched_cat_id = best[0]
                confidence = min(0.8, 0.2 + 0.2*best[1])
                method = 'token_overlap'

        # fuzzy match using difflib as fallback
        if matched_cat_id is None and text_norm:
            choices = [cname for _, cname in cat_names]
            match = difflib.get_close_matches(text_norm, choices, n=1, cutoff=0.6)
            if match:
                # find id
                for cid, cname in cat_names:
                    if cname == match[0]:
                        matched_cat_id = cid
                        confidence = 0.7
                        method = 'fuzzy'
                        break

        # remove existing mapping for this review
        session.query(MonthlyReviewCategoryMap).filter(MonthlyReviewCategoryMap.review_id==r.id).delete()

        mapping = MonthlyReviewCategoryMap(
            review_id=r.id,
            category_id=matched_cat_id,
            subcategory_id=matched_sub_id,
            confidence=confidence,
            method=method
        )
        session.add(mapping)
        inserted += 1

    session.commit()
    print(f"Inserted/updated {inserted} mappings for reviews.")
finally:
    session.close()
