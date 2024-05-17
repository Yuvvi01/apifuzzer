import requests
import os
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
import argparse
import tqdm
import ast
import logging
from collections import deque
import asyncio

# Initialize logging
logging.basicConfig(filename='apifuzzer.log', level=logging.INFO)

class RateLimiter(object):
    def __init__(self, max_calls, period=1.0):
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()

    async def __aenter__(self):
        if len(self.calls) >= self.max_calls:
            until = time.time() - self.calls[0]
            if until < self.period:
                await asyncio.sleep(self.period - until)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.calls.append(time.time())
        while self.calls and time.time() - self.calls[0] > self.period:
            self.calls.popleft()

def validate_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def apifuzzer(url, wordlist_path, method='GET', headers=None, cookies=None, delay=1, concurrency=10, status_code=200, content_type='text/html', auth=None):
    if not validate_url(url):
        logging.error(f"The URL {url} is not valid.")
        return

    wordlist_path = os.path.normpath(wordlist_path)

    if not os.path.exists(wordlist_path):
        logging.error(f"The file or directory {wordlist_path} does not exist.")
        return

    output_file = open(f"{url.replace('/', '_').replace(':', '')}_output.txt", "w")

    rate_limiter = RateLimiter(max_calls=concurrency, period=delay)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        if os.path.isdir(wordlist_path):
            for filename in os.listdir(wordlist_path):
                if filename.endswith(".txt"):
                    with open(os.path.join(wordlist_path, filename), 'r') as file:
                        words = file.read().splitlines()
                        for word in tqdm.tqdm(words, desc="Processing wordlist"):
                            with rate_limiter:
                                executor.submit(send_request, url, word, method, headers, cookies, delay, status_code, content_type, output_file, auth)
        else:
            with open(wordlist_path, 'r') as file:
                words = file.read().splitlines()
                for word in tqdm.tqdm(words, desc="Processing wordlist"):
                    with rate_limiter:
                        executor.submit(send_request, url, word, method, headers, cookies, delay, status_code, content_type, output_file, auth)

    output_file.close()

def send_request(url, word, method, headers, cookies, delay, status_code, content_type, output_file, auth):
    try:
        time.sleep(delay)
        if method.upper() == 'GET':
            res = requests.get(f"{url}/{word}", headers=headers, cookies=cookies, auth=auth)
        elif method.upper() == 'POST':
            res = requests.post(f"{url}/{word}", headers=headers, cookies=cookies, auth=auth)
        elif method.upper() == 'PUT':
            res = requests.put(f"{url}/{word}", headers=headers, cookies=cookies, auth=auth)
        elif method.upper() == 'DELETE':
            res = requests.delete(f"{url}/{word}", headers=headers, cookies=cookies, auth=auth)
        else:
            logging.error(f"HTTP method {method} is not supported.")
            return

        if res.status_code == status_code and content_type in res.headers.get('Content-Type', ''):
            output_file.write(f"\nURL: {url}/{word}\n")
            output_file.write(f"Method: {method}\n")
            output_file.write(f"Headers: {headers}\n")
            output_file.write(f"Cookies: {cookies}\n")
            output_file.write(f"Status Code: {res.status_code}\n")
            output_file.write(f"Response content (type: {res.headers.get('Content-Type')}):\n{res.content}\n")
            output_file.write("-"*50 + "\n")
        else:
            logging.info(f"Response with status code {res.status_code} and content type {res.headers.get('Content-Type')} received.")
            # Analyze the response body for common error messages or anomalies
            analyze_response(res)
    except requests.exceptions.RequestException as e:
        logging.error(f"An error occurred: {e}. Skipping this request.")

def analyze_response(response):
    # This is a placeholder function. You should implement your own logic to analyze the response body for common error messages or anomalies.
    pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='API Fuzzer')
    parser.add_argument('-url', required=True, help='The URL to fuzz')
    parser.add_argument('-wordlist', required=True, help='The path to the wordlist or directory')
    parser.add_argument('-method', default='GET', help='The HTTP method to use')
    parser.add_argument('-headers', type=ast.literal_eval, default={"User-Agent": "My Fuzzer"}, help='The headers to use')
    parser.add_argument('-cookies', type=ast.literal_eval, default={"session": "123456"}, help='The cookies to use')
    parser.add_argument('-delay', type=int, default=1, help='The delay between requests')
    parser.add_argument('-concurrency', type=int, default=10, help='The number of concurrent requests')
    parser.add_argument('-status_code', type=int, default=200, help='The status code to filter results')
    parser.add_argument('-content_type', default='text/html', help='The content type to filter results')
    parser.add_argument('-auth', type=ast.literal_eval, default=None, help='The authentication to use (e.g., ("username", "password") for Basic Auth)')
    args = parser.parse_args()

    apifuzzer(args.url, args.wordlist, args.method, args.headers, args.cookies, args.delay, args.concurrency, args.status_code, args.content_type, args.auth)
