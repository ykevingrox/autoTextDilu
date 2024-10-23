import requests
from requests.exceptions import TooManyRedirects, RequestException
import os
import xml.etree.ElementTree as ET
import logging
from bs4 import BeautifulSoup
import re

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
        self.sci_hub_url = "https://sci-hub.se/"  # 注意：这个URL可能会经常变化
        self.session = requests.Session()
        self.session.max_redirects = 5  # 限制重定向次数
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

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
        """
        注意：PDF下载功能仅适用于PubMed和Crossref API。
        对于其他API源（如PMC），将使用其原有的下载逻辑。
        """
        if api_source == 'crossref':
            return self.download_or_get_abstract_crossref(paper['doi'], paper['title'])
        elif api_source == 'pubmed':
            return self.download_or_get_abstract_pubmed(paper['pmid'], paper['title'])
        elif api_source == 'pmc':
            return self.download_pdf_pmc(paper['pmcid'], paper['title'])
        else:
            logging.warning(f"Unsupported API source: {api_source}")
            return None

    def download_or_get_abstract_crossref(self, doi, title):
        url = f"https://doi.org/{doi}"
        try:
            response = self.session.get(url, allow_redirects=True, timeout=30)
            response.raise_for_status()
            if response.status_code == 200:
                pdf_url = self.extract_pdf_url(response.url, response.text)
                if pdf_url:
                    pdf_result = self.download_pdf(pdf_url, title, 'crossref')
                    if pdf_result:
                        return pdf_result
                
                # 如果无法直接获取PDF，尝试使用Sci-Hub
                sci_hub_result = self.try_sci_hub(doi, title)
                if sci_hub_result:
                    return sci_hub_result

                # 如果无法获取PDF，尝试提取摘要
                abstract = self.extract_abstract(response.text)
                if abstract:
                    filename = self.get_valid_filename(title + '.txt')  # 修改这里，使用 .txt 扩展名
                    filepath = os.path.join(self.download_dir, filename)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(abstract)
                    logging.info(f"Saved Crossref abstract to {filepath}")
                    return {'type': 'abstract', 'path': filepath}
                else:
                    logging.warning(f"Unable to extract abstract for DOI: {doi}")
                    return {'type': 'error', 'message': '无法提取摘要'}

            return {'type': 'error', 'message': '无法获取文章内容'}
        except TooManyRedirects:
            logging.error(f"Too many redirects when accessing DOI: {doi}")
            return {'type': 'error', 'message': '访问DOI时遇到太多重定向'}
        except RequestException as e:
            logging.error(f"Error accessing DOI {doi}: {str(e)}")
            return {'type': 'error', 'message': f'访问DOI时出错: {str(e)}'}

    def extract_pdf_url(self, url, html_content):
        # 尝试从URL中直接识别PDF链接
        if url.endswith('.pdf'):
            return url
        
        # 使用BeautifulSoup解析HTML内容
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 查找可能的PDF链接
        pdf_links = soup.find_all('a', href=re.compile(r'\.pdf$'))
        if pdf_links:
            return pdf_links[0]['href']
        
        # 查找特定的下载按钮或链接（这部分可能需要根据不同的出版商网站进行定制）
        download_links = soup.find_all('a', text=re.compile(r'Download PDF', re.I))
        if download_links:
            return download_links[0]['href']
        
        return None

    def try_sci_hub(self, doi, title):
        sci_hub_url = f"{self.sci_hub_url}{doi}"
        response = self.session.get(sci_hub_url)
        if response.status_code == 200:
            pdf_url = self.extract_pdf_url_from_sci_hub(response.text)
            if pdf_url:
                return self.download_pdf(pdf_url, title)
        return None

    def extract_pdf_url_from_sci_hub(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 查找嵌入的PDF查看器
        embed = soup.find('embed', type='application/pdf')
        if embed and 'src' in embed.attrs:
            return embed['src']
        
        # 查找下载按钮
        download_button = soup.find('button', id='download')
        if download_button and 'onclick' in download_button.attrs:
            onclick = download_button['onclick']
            match = re.search(r"location.href='(.+?)'", onclick)
            if match:
                return match.group(1)
        
        # 查找iframe
        iframe = soup.find('iframe')
        if iframe and 'src' in iframe.attrs:
            return iframe['src']
        
        return None

    def download_pdf(self, url, title, api_source):
        """
        下载PDF文件。
        注意：此方法仅用于PubMed和Crossref API。
        """
        if api_source not in ['pubmed', 'crossref']:
            logging.warning(f"PDF download not supported for API source: {api_source}")
            return None

        try:
            response = self.session.get(url, stream=True)
            if response.status_code == 200 and response.headers.get('Content-Type', '').startswith('application/pdf'):
                filename = self.get_valid_filename(title) + '.pdf'  # 修改这里，明确添加 .pdf 扩展名
                filepath = os.path.join(self.download_dir, filename)
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                logging.info(f"Saved PDF from {api_source} to {filepath}")
                return {'type': 'pdf', 'path': filepath}
            else:
                logging.warning(f"Failed to download PDF from {api_source}. URL: {url}. Status code: {response.status_code}")
        except Exception as e:
            logging.error(f"Error downloading PDF from {api_source}. URL: {url}. Error: {str(e)}")
        return None

    def download_or_get_abstract_pubmed(self, pmid, title):
        paper = self.fetch_paper_details_pubmed(pmid)
        if paper:
            if paper.get('full_text_link'):
                pdf_result = self.download_pdf(paper['full_text_link'], title, 'pubmed')
                if pdf_result:
                    return pdf_result
            if paper['abstract']:
                filename = self.get_valid_filename(title + '.txt')  # 修改这里，使用 .txt 扩展名
                filepath = os.path.join(self.download_dir, filename)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(paper['abstract'])
                logging.info(f"Saved PubMed abstract to {filepath}")
                return {'type': 'abstract', 'path': filepath}
        logging.warning(f"无法获取PubMed摘要或全文: {pmid}")
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
        # 移除文件扩展名，然后添加适当的扩展名
        name_without_ext = os.path.splitext(name)[0]
        return "".join(x for x in name_without_ext if x.isalnum() or x in [' ', '.', '_']).rstrip()[:50]

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

    def extract_abstract(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 尝试找到摘要
        abstract = soup.find('section', class_='abstract')
        if abstract:
            return abstract.get_text(strip=True)
        
        # 如果没有找到明确的摘要，尝试查找其他可能包含摘要的元素
        possible_abstract = soup.find('meta', attrs={'name': 'description'})
        if possible_abstract:
            return possible_abstract.get('content', '')

        return None

