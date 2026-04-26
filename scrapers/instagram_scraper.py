from bs4 import BeautifulSoup
import requests

class InstagramScraper:
    def __init__(self, username):
        self.username = username
        self.base_url = f'https://www.instagram.com/{self.username}/'
        self.posts = []

    def scrape(self):
        response = requests.get(self.base_url)
        if response.status_code == 200:
            self.parse(response.text)
        else:
            print(f"Failed to retrieve data for {self.username}")

    def parse(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        scripts = soup.find_all('script', type='text/javascript')
        for script in scripts:
            if 'window._sharedData =' in script.text:
                shared_data = script.text.split(' = ', 1)[1].rstrip(';')
                self.extract_posts(shared_data)

    def extract_posts(self, shared_data):
        import json
        data = json.loads(shared_data)
        user_data = data['entry_data']['ProfilePage'][0]['graphql']['user']
        for edge in user_data['edge_owner_to_timeline_media']['edges']:
            post = {
                'id': edge['node']['id'],
                'shortcode': edge['node']['shortcode'],
                'timestamp': edge['node']['taken_at_timestamp'],
                'likes': edge['node']['edge_liked_by']['count'],
                'comments': edge['node']['edge_media_to_comment']['count'],
                'image_url': edge['node']['display_url'],
            }
            self.posts.append(post)

    def get_posts(self):
        return self.posts

# Example usage:
# scraper = InstagramScraper('instagram_username')
# scraper.scrape()
# print(scraper.get_posts())