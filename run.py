from scraper import OyezScraper

for i in range(1960, 2016):
    scraper = OyezScraper(i, i)
    scraper.run()

    
