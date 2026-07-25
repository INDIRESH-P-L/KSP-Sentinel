from scripts.import_monthly_reviews import import_reviews
from scripts.map_reviews_to_categories import *
from scripts.export_reviews_summary import *

if __name__ == '__main__':
    print('Importing monthly review CSVs...')
    import_reviews()
    print('Mapping reviews to categories...')
    # mapping script runs on import due to module side-effects; re-run mapping logic by importing module
    from importlib import reload
    import scripts.map_reviews_to_categories as mapper
    reload(mapper)
    print('Exporting consolidated CSV...')
    from scripts.export_reviews_summary import *
    print('Done.')
