import requests
import os
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
import argparse
import tqdm
import ast
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def validate_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def apifuzzer(url, wordlist_path, method='GET', headers=None, cookies=None, delay=1, concurrency=10, status_code=200, content_type='text/html'):
    if not validate_url(url):
        print(f"The URL {url} is not valid.")
        return

    wordlist_path = os.path.normpath(wordlist_path)

    if not os.path.exists(wordlist_path):
        print(f"The file or directory {wordlist_path} does not exist.")
        return

    output_file = open(f"{url.replace('/', '_').replace(':', '')}_output.txt", "w")

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        if os.path.isdir(wordlist_path):
            for filename in os.listdir(wordlist_path):
                if filename.endswith(".txt"):
                    with open(os.path.join(wordlist_path, filename), 'r') as file:
                        words = file.read().splitlines()
                        for word in tqdm.tqdm(words, desc="Processing wordlist"):
                            executor.submit(send_request, url, word, method, headers, cookies, delay, status_code, content_type, output_file)
        else:
            with open(wordlist_path, 'r') as file:
                words = file.read().splitlines()
                for word in tqdm.tqdm(words, desc="Processing wordlist"):
                    executor.submit(send_request, url, word, method, headers, cookies, delay, status_code, content_type, output_file)

    output_file.close()

def send_request(url, word, method, headers, cookies, delay, status_code, content_type, output_file):
    try:
        time.sleep(delay)
        session = requests.Session()
        retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[ 500, 502, 503, 504 ])
        session.mount('http://', HTTPAdapter(max_retries=retries))
        session.mount('https://', HTTPAdapter(max_retries=retries))

        if method.upper() == 'GET':
            res = session.get(f"{url}/{word}", headers=headers, cookies=cookies)
        elif method.upper() == 'POST':
            res = session.post(f"{url}/{word}", headers=headers, cookies=cookies)
        elif method.upper() == 'PUT':
            res = session.put(f"{url}/{word}", headers=headers, cookies=cookies)
        elif method.upper() == 'DELETE':
            res = session.delete(f"{url}/{word}", headers=headers, cookies=cookies)
        else:
            print(f"HTTP method {method} is not supported.")
            return

        if res.status_code == status_code and content_type in res.headers.get('Content-Type', ''):
            output_file.write(f"\nURL: {url}/{word}\n")
            output_file.write(f"Method: {method}\n")
            output_file.write(f"Headers: {headers}\n")
            output_file.write(f"Cookies: {cookies}\n")
            output_file.write(f"Status Code: {res.status_code}\n")
            output_file.write(f"Response content (type: {res.headers.get('Content-Type')}):\n{res.content}\n")
            output_file.write("-"*50 + "\n")
    except requests.exceptions.RequestException as e:
        output_file.write(f"An error occurred: {e}. Retrying...\n")
        send_request(url, word, method, headers, cookies, delay, status_code, content_type, output_file)

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
    args = parser.parse_args()

    apifuzzer(args.url, args.wordlist, args.method, args.headers, args.cookies, args.delay, args.concurrency, args.status_code, args.content_type)
