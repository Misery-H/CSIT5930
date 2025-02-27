import hashlib
import logging

import requests
import os
import json
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime
from collections import defaultdict, Counter
import datetime
from utils.DBHelper import DBHelper
import re
#to ignore warning
import shutup
shutup.please()


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
    def __init__(self, start_url, max_pages, index_file='index.json', data_dir='pages', stopwords_file='stopwords.txt'):
        self.start_url = start_url
        self.max_pages = max_pages
        self.domain = urlparse(start_url).netloc
        self.index_file = index_file
        self.data_dir = data_dir
        self.index = {}
        self.update_index = {}
        self.page_id = 1
        self.queue = []
        self.visited = set()
        self.parent_child = defaultdict(list)
        self.child_parents = defaultdict(list)
        self.dBHelper = DBHelper()
        self.stopwords_file = stopwords_file
        self.linkageParent= {}
        self.linkageChild= {}
        os.makedirs(data_dir, exist_ok=True)

        self.load_index()

    def load_index(self):
        self.index = self.dBHelper.get_all_documents()
        self.page_id = max(len(self.index), 0) + 1

    def is_same_domain(self, url):
        return urlparse(url).netloc == self.domain

    def needs_fetch(self, url):
        if url not in self.index:
            return True

        try:
            response = requests.head(url, timeout=5, verify=False)
            response.raise_for_status()
            if 'Last-Modified' not in response.headers:
                return False
            current_lm_utc = parsedate_to_datetime(response.headers['Last-Modified'])
            east8_tz = datetime.timezone(datetime.timedelta(hours=8))  # 定义东八区
            current_lm = current_lm_utc.astimezone(east8_tz).replace(tzinfo=None)
            indexed_lm = datetime.datetime.fromisoformat(self.index[url]['last_modify'])
            return current_lm > indexed_lm

        # except (requests.exceptions.RequestException, ValueError) as e:
        except Exception as e:
            print(f"Check failed for {url}: {str(e)}")
            return False

    def fetch_page(self, url):
        try:
            response = requests.get(url, timeout=5, verify=False)
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

    def process_page(self, content):
        """
        Save the content of the page to a file
        :param page_id:
        :param content:
        :return:
        """
        soup = BeautifulSoup(content, "html.parser")
        clean_text = soup.get_text(separator=" ", strip=True)  # 保留文本空格分隔
        title_tag = soup.find('title')
        title = title_tag.text.strip() if title_tag else 'Untitled'
        try:
            with open(self.stopwords_file, "r", encoding="utf-8") as f:
                stopwords = set(line.strip().lower() for line in f)
        except FileNotFoundError:
            raise FileNotFoundError(f"The file {self.stopwords_file} does not exist.")

        words = re.findall(r'\b\w+\b', clean_text)  # 分割单词（忽略标点）
        filtered_words = [
            word for word in words
            if word.lower() not in stopwords
        ]
        processed_text = " ".join(filtered_words)
        return processed_text, title

    def tfmax(self, text):
        text_lower = text.lower()
        words = re.findall(r"[\w'-]+", text_lower)
        word_counts = Counter(words)
        if not word_counts:
            return 0
        return max(word_counts.values())
    def crawl(self):
        self.queue.append(self.start_url)
        count = 0
        self.needsProcess = True
        #FIFO
        while self.queue and self.page_id < self.max_pages:
            current_url = self.queue.pop(0)
            if current_url in self.visited:
                continue
            self.visited.add(current_url)

            #last_modified has changed, need to fetch the page again
            self.needsProcess=self.needs_fetch(current_url)


            html, last_modified = self.fetch_page(current_url)
            if not html:
                continue
            html2txt, title = self.process_page(html)
            tfmax = self.tfmax(html2txt)
            #Insert into
            doc = {'url': current_url,
                    'last_modify': parsedate_to_datetime(last_modified).isoformat() if last_modified
                    else datetime.datetime.now().isoformat(),
                    'content_hash': hashlib.sha256(html2txt.encode('utf-8')).hexdigest(),
                    'content': html2txt,
                    #TODO:add description
                    'description': 'TODO',
                    'title': title,
                    'tf_max': tfmax}
            if self.needsProcess:
                try:
                    page_id = self.dBHelper.get_page_id(current_url)
                    logging.info(f"Updating document: {current_url}")
                    self.dBHelper.update_document(doc,page_id)
                    #delete the old url linkage
                    self.dBHelper.delete_url_linkage(page_id)
                    self.linkageParent[page_id]=True
                except:
                    logging.info(f"Adding document: {current_url}")
                    self.dBHelper.add_document(doc)
                    page_id = self.dBHelper.get_page_id(current_url)
                    self.linkageParent[page_id]=True
                    self.linkageChild[page_id]=True
            else:
                page_id = self.dBHelper.get_page_id(current_url)
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

        for parent, children in self.parent_child.items():
            for child in children:
                if self.linkageParent.get(parent,False) or self.linkageChild.get(child,False):
                    logging.info(f"Adding URL linkage: {parent} -> {child}")
                    self.dBHelper.add_url_linkage(parent, child)

if __name__ == "__main__":
    spider = WebSpider(
        start_url="https://www.cse.ust.hk/~kwtleung/COMP4321/testpage.htm",
        max_pages=300
    )
    spider.crawl()
