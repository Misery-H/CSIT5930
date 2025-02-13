import requests
import os
import json
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime
from collections import defaultdict
import datetime


class WebSpider:
    """
    start_url: start of the crawl
    max_pages: maximum number of pages to crawl, we set it to 300
    domain: domain of the start_url, it is www.cse.ust.hk in this case.
            It is used to check if a link is in the same domain.

    index_file: file to store the index of the crawled pages
    data_dir: directory to store the crawled pages
    index: a dictionary to store the index of the crawled pages
    page_id: unique id for each page
    queue: a list to store the urls to be crawled
    visited: a set to store the urls that have been crawled
    parent_child: a dictionary to store the parent-child relationships
    child_parents: a dictionary to store the child-parent relationships

    """
    def __init__(self, start_url, max_pages, index_file='index.json', data_dir='pages'):
        self.start_url = start_url
        self.max_pages = max_pages
        self.domain = urlparse(start_url).netloc
        self.index_file = index_file
        self.data_dir = data_dir
        self.index = {}
        self.page_id = 1
        self.queue = []
        self.visited = set()
        self.parent_child = defaultdict(list)
        self.child_parents = defaultdict(list)

        os.makedirs(data_dir, exist_ok=True)
        self.load_index()

    def load_index(self):
        if os.path.exists(self.index_file):
            with open(self.index_file, 'r') as f:
                self.index = json.load(f)
            if self.index:
                self.page_id = max(int(v['id']) for v in self.index.values()) + 1

    def save_index(self):
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f, indent=2)

    def is_same_domain(self, url):
        return urlparse(url).netloc == self.domain

    def needs_fetch(self, url):
        if url not in self.index:
            return True

        try:
            response = requests.head(url, timeout=5,verify=False)
            response.raise_for_status()
            if 'Last-Modified' not in response.headers:
                return False
            current_lm = parsedate_to_datetime(response.headers['Last-Modified'])
            indexed_lm = datetime.datetime.fromisoformat(self.index[url]['last_modified'])

            return current_lm > indexed_lm

        except (requests.exceptions.RequestException, ValueError) as e:

            print(f"Check failed for {url}: {str(e)}")
            return False


    def fetch_page(self, url):
        try:
            response = requests.get(url, timeout=5,verify=False)
            response.raise_for_status()
            return response.text, response.headers.get('Last-Modified')
        except Exception as e:
            print(f"Failed to fetch {url}: {str(e)}")
            return None, None


    def extract_links(self, html, base_url):
        """
        Extract links from the html content
        :param html:
        :param base_url:
        :return:
        """
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        for link in soup.find_all('a', href=True):
            absolute_url = urljoin(base_url, link['href'])
            """
            ONLY crawl the pages in the same domain /*www.cse.ust.hk*/
            """
            if self.is_same_domain(absolute_url):
                links.append(absolute_url)
        return links


    def save_page(self, page_id, content):
        """
        Save the content of the page to a file
        :param page_id:
        :param content:
        :return:
        """
        with open(os.path.join(self.data_dir, f'{page_id}.html'), 'w', encoding='utf-8') as f:
            f.write(content)


    def save_relations(self):
        with open('relations.txt', 'w') as f:
            for parent, children in self.parent_child.items():
                f.write(f"{parent} {' '.join(map(str, children))}\n")
        with open('urls.txt', 'w') as f:
            for url, info in self.index.items():
                f.write(f"{info['id']} {url}\n")


    def crawl(self):
        self.queue.append(self.start_url)
        count = 0
        #FIFO
        while self.queue and count < self.max_pages:
            current_url = self.queue.pop(0)
            if current_url in self.visited:
                continue
            self.visited.add(current_url)

            if not self.needs_fetch(current_url):
                continue

            html, last_modified = self.fetch_page(current_url)
            if not html:
                continue

            # Update or create index entry
            if current_url in self.index:
                page_id = self.index[current_url]['id']
                if last_modified:
                    self.index[current_url]['last_modified'] = parsedate_to_datetime(last_modified).isoformat()
            else:
                page_id = self.page_id
                self.index[current_url] = {
                    'id': page_id,
                    'last_modified': parsedate_to_datetime(last_modified).isoformat() if last_modified
                    else datetime.datetime.now().isoformat()
                }
                self.page_id += 1

            self.save_page(page_id, html)

            # Extract and process links
            links = self.extract_links(html, current_url)
            for link in links:
                # record the parent of the childlink
                # at this time child link don't have a page_id
                self.child_parents[link].append(page_id)
                #if childlink is not recorded adding it to the queue
                if link not in self.visited and link not in self.queue:
                    self.queue.append(link)

            # Update parent-child relationships
            for parent_id in self.child_parents.get(current_url, []):
                if page_id not in self.parent_child[parent_id]:
                    self.parent_child[parent_id].append(page_id)

            count += 1

        self.save_index()
        self.save_relations()


if __name__ == "__main__":
    spider = WebSpider(
        start_url="https://www.cse.ust.hk/~kwtleung/COMP4321/testpage.htm",
        max_pages=300
    )
    spider.crawl()
