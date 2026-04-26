from requests import OAuth1Session
import json

class TwitterScraper:
    def __init__(self, consumer_key, consumer_secret, access_token, access_token_secret):
        self.auth = OAuth1Session(consumer_key, consumer_secret, access_token, access_token_secret)
        self.base_url = "https://api.twitter.com/1.1/"

    def get_user_tweets(self, username, count=10):
        url = f"{self.base_url}statuses/user_timeline.json"
        params = {
            "screen_name": username,
            "count": count,
            "tweet_mode": "extended"
        }
        response = self.auth.get(url, params=params)
        if response.status_code == 200:
            return json.loads(response.text)
        else:
            return None

    def search_tweets(self, query, count=10):
        url = f"{self.base_url}search/tweets.json"
        params = {
            "q": query,
            "count": count,
            "tweet_mode": "extended"
        }
        response = self.auth.get(url, params=params)
        if response.status_code == 200:
            return json.loads(response.text)
        else:
            return None

# Example usage:
# scraper = TwitterScraper(consumer_key, consumer_secret, access_token, access_token_secret)
# tweets = scraper.get_user_tweets("username")
# print(tweets)