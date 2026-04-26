from bs4 import BeautifulSoup
import requests

class FacebookScraper:
    def __init__(self, page_url):
        self.page_url = page_url
        self.posts = []

    def scrape(self):
        response = requests.get(self.page_url)
        if response.status_code == 200:
            self.parse(response.text)
        else:
            print(f"Failed to retrieve page: {response.status_code}")

    def parse(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        for post in soup.find_all('div', class_='post'):
            content = post.find('div', class_='content').text
            timestamp = post.find('span', class_='timestamp').text
            self.posts.append({'content': content, 'timestamp': timestamp})

    def get_posts(self):
        return self.posts

# Example usage:
# scraper = FacebookScraper('https://www.facebook.com/somepage')
# scraper.scrape()
# print(scraper.get_posts())