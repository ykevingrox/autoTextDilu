import requests
import os
import xml.etree.ElementTree as ET
import logging

class PaperSearcher:
    def __init__(self, download_dir='downloads'):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
        self.crossref_url = "https://api.crossref.org/works"
        self.pubmed_search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        self.pubmed_fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        self.pmc_search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        self.pmc_fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        self.headers = {
            'User-Agent': 'YourApp/1.0 (mailto:your-email@example.com)'
        }

    def search_papers_crossref(self, keywords, start_year=None, end_year=None):
        params = {
            'query': keywords,
            'rows': 10,
            'sort': 'relevance',
            'order': 'desc',
            'select': 'DOI,title,abstract,URL,published-print,type'
        }
        if start_year and end_year:
            params['filter'] = f'from-pub-date:{start_year},until-pub-date:{end_year}'

        response = requests.get(self.crossref_url, params=params, headers=self.headers)
        if response.status_code == 200:
            data = response.json()
            papers = []
            for item in data['message']['items']:
                paper = {
                    'title': item.get('title', [''])[0],
                    'abstract': item.get('abstract', ''),
                    'url': item.get('URL', ''),
                    'year': item.get('published-print', {}).get('date-parts', [['']])[0][0],
                    'doi': item.get('DOI', ''),
                    'type': item.get('type', '')
                }
                papers.append(paper)
            return papers
        else:
            print(f"Crossref搜索失败，状态码: {response.status_code}")
            return []

    def search_papers_pubmed(self, keywords, start_year=None, end_year=None):
        params = {
            'db': 'pubmed',
            'term': keywords,
            'retmax': 10,
            'sort': 'relevance',
            'retmode': 'json'
        }
        if start_year and end_year:
            params['term'] += f" AND ({start_year}[PDAT]:{end_year}[PDAT])"

        response = requests.get(self.pubmed_search_url, params=params, headers=self.headers)
        if response.status_code == 200:
            data = response.json()
            id_list = data['esearchresult']['idlist']
            papers = []
            for pmid in id_list:
                paper = self.fetch_paper_details_pubmed(pmid)
                if paper:
                    papers.append(paper)
            return papers
        else:
            print(f"PubMed搜索失败，状态码: {response.status_code}")
            return []

    def fetch_paper_details_pubmed(self, pmid):
        params = {
            'db': 'pubmed',
            'id': pmid,
            'retmode': 'xml'
        }
        response = requests.get(self.pubmed_fetch_url, params=params, headers=self.headers)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            article = root.find(".//Article")
            if article is not None:
                return {
                    'title': article.findtext(".//ArticleTitle", ''),
                    'abstract': article.findtext(".//Abstract/AbstractText", ''),
                    'url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    'year': article.findtext(".//PubDate/Year", ''),
                    'pmid': pmid,
                    'type': article.findtext(".//PublicationType", '')
                }
        return None

    def search_papers_pmc(self, keywords, start_year=None, end_year=None):
        params = {
            'db': 'pmc',
            'term': f"{keywords} AND open access[filter]",
            'retmax': 10,
            'sort': 'relevance',
            'retmode': 'json'
        }
        if start_year and end_year:
            params['term'] += f" AND ({start_year}[PDAT]:{end_year}[PDAT])"

        response = requests.get(self.pmc_search_url, params=params, headers=self.headers)
        if response.status_code == 200:
            data = response.json()
            id_list = data['esearchresult']['idlist']
            papers = []
            for pmcid in id_list:
                paper = self.fetch_paper_details_pmc(pmcid)
                if paper:
                    papers.append(paper)
            return papers
        else:
            print(f"PMC搜索失败，状态码: {response.status_code}")
            return []

    def fetch_paper_details_pmc(self, pmcid):
        params = {
            'db': 'pmc',
            'id': pmcid,
            'retmode': 'xml'
        }
        response = requests.get(self.pmc_fetch_url, params=params, headers=self.headers)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            article = root.find(".//article")
            if article is not None:
                # 尝试多种方式获取摘要
                abstract = ''
                abstract_element = article.find(".//abstract")
                if abstract_element is not None:
                    abstract = ET.tostring(abstract_element, encoding='unicode', method='text').strip()
                if not abstract:
                    abstract = ' '.join([ET.tostring(p, encoding='unicode', method='text').strip() for p in article.findall(".//abstract/p")])
                if not abstract:
                    abstract = article.findtext(".//article-meta/abstract", '')
                
                # 记录摘要内容
                logging.info(f"PMC Abstract for {pmcid}: {abstract[:100]}...")  # 记录前100个字符

                return {
                    'title': article.findtext(".//article-title", ''),
                    'abstract': abstract,
                    'url': f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/",
                    'year': article.findtext(".//pub-date/year", ''),
                    'pmcid': pmcid,
                    'type': article.findtext(".//article-type", '')
                }
            else:
                logging.warning(f"No article found for PMC ID: {pmcid}")
        else:
            logging.error(f"Failed to fetch PMC article {pmcid}. Status code: {response.status_code}")
        return None

    def download_or_get_abstract(self, paper, api_source):
        if api_source == 'crossref':
            return self.download_or_get_abstract_crossref(paper['doi'], paper['title'])
        elif api_source == 'pubmed':
            return self.download_or_get_abstract_pubmed(paper['pmid'], paper['title'])
        elif api_source == 'pmc':
            pdf_result = self.download_pdf_pmc(paper['pmcid'], paper['title'])
            if pdf_result:
                return pdf_result
            else:
                return self.download_or_get_abstract_pmc(paper['pmcid'], paper['title'])

    def download_or_get_abstract_crossref(self, doi, title):
        url = f"https://doi.org/{doi}"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            filename = self.get_valid_filename(title + '_abstract.txt')
            filepath = os.path.join(self.download_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(response.text)
            return {'type': 'abstract', 'path': filepath}
        else:
            print(f"无法获取Crossref摘要: {doi}")
            return None

    def download_or_get_abstract_pubmed(self, pmid, title):
        paper = self.fetch_paper_details_pubmed(pmid)
        if paper and paper['abstract']:
            filename = self.get_valid_filename(title + '_abstract.txt')
            filepath = os.path.join(self.download_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(paper['abstract'])
            return {'type': 'abstract', 'path': filepath}
        else:
            print(f"无法获取PubMed摘要: {pmid}")
            return None

    def download_or_get_abstract_pmc(self, pmcid, title):
        paper = self.fetch_paper_details_pmc(pmcid)
        if paper and paper['abstract']:
            filename = self.get_valid_filename(title + '_abstract.txt')
            filepath = os.path.join(self.download_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(paper['abstract'])
            logging.info(f"Saved PMC abstract to {filepath}")
            return {'type': 'abstract', 'path': filepath}
        else:
            logging.warning(f"无法获取PMC摘要: {pmcid}")
            return None

    def get_valid_filename(self, name):
        return "".join(x for x in name if x.isalnum() or x in [' ', '.', '_']).rstrip()[:50] + '.pdf'

    def download_pdf_pmc(self, pmcid, title):
        url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/pdf/"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            filename = self.get_valid_filename(title + '.pdf')
            filepath = os.path.join(self.download_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(response.content)
            logging.info(f"Saved PMC PDF to {filepath}")
            return {'type': 'pdf', 'path': filepath}
        else:
            logging.warning(f"无法下载PMC PDF: {pmcid}")
            return None
