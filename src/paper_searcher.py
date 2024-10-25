import requests
from requests.exceptions import TooManyRedirects, RequestException
import os
import xml.etree.ElementTree as ET
import logging
from bs4 import BeautifulSoup
import re
from functools import lru_cache
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import feedparser
from datetime import datetime, timedelta
from urllib.parse import quote
from dateutil.relativedelta import relativedelta

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
        self.citation_cache = {}
        self.max_concurrent_requests = 5  # 最大并发请求数
        self.cache_expiry = 24 * 60 * 60  # 缓存有效期（秒），这里设置为24小时

    @lru_cache(maxsize=1000)
    def get_citation_count(self, identifier, api_source):
        """
        获取引用次数，使用缓存来避免重复请求
        """
        current_time = time.time()
        if identifier in self.citation_cache:
            count, timestamp = self.citation_cache[identifier]
            if current_time - timestamp < self.cache_expiry:
                return count

        if api_source == 'crossref':
            count = self.get_crossref_citation_count(identifier)
        elif api_source == 'pubmed':
            count = self.get_pubmed_citation_count(identifier)
        elif api_source == 'pmc':
            count = self.get_pmc_citation_count(identifier)
        else:
            count = 0

        self.citation_cache[identifier] = (count, current_time)
        return count

    def get_crossref_citation_count(self, doi):
        # Crossref API 已经在搜索结果中提供了引用次数，所以这里不需要额外的实现
        return 0

    def fetch_citation_counts(self, papers, api_source):
        """
        使用线程池来并发获取引用次数
        """
        with ThreadPoolExecutor(max_workers=self.max_concurrent_requests) as executor:
            future_to_paper = {executor.submit(self.get_citation_count, paper.get('doi') or paper.get('pmid') or paper.get('pmcid'), api_source): paper for paper in papers}
            for future in as_completed(future_to_paper):
                paper = future_to_paper[future]
                try:
                    citation_count = future.result()
                    paper['citation_count'] = citation_count
                except Exception as exc:
                    logging.error(f'{paper.get("title")} generated an exception: {exc}')
                    paper['citation_count'] = 0

    def search_papers_crossref(self, keywords, start_year=None, end_year=None, max_results=10):
        params = {
            'query': keywords,
            'rows': max_results,
            'sort': 'relevance',
            'order': 'desc',
            'select': 'DOI,title,abstract,URL,published-print,published-online,issued,type,is-referenced-by-count,author'
        }
        if start_year and end_year:
            params['filter'] = f'from-pub-date:{start_year},until-pub-date:{end_year}'

        response = requests.get(self.crossref_url, params=params, headers=self.headers)
        if response.status_code == 200:
            data = response.json()
            papers = []
            for item in data['message']['items']:
                doi = item.get('DOI', '')
                unique_id = self.generate_unique_id(doi)
                paper = {
                    'id': str(unique_id),  # 添加唯一ID
                    'title': item.get('title', [''])[0],
                    'abstract': item.get('abstract', ''),
                    'url': item.get('URL', ''),
                    'year': item.get('published-print', {}).get('date-parts', [['']])[0][0],
                    'doi': doi,
                    'type': item.get('type', ''),
                    'authors': [author.get('family', '') + ' ' + author.get('given', '') for author in item.get('author', [])],
                    'citation_count': item.get('is-referenced-by-count', 0),
                    'api_source': 'crossref'  # 添加这一行
                }
                papers.append(paper)
                logging.info(f"Crossref paper found: {paper['title'][:100]}... DOI: {doi}")
            return papers
        else:
            logging.error(f"Crossref搜索失败，状态码: {response.status_code}")
            return []

    def search_papers_pubmed(self, keywords, start_year=None, end_year=None, max_results=10):
        params = {
            'db': 'pubmed',
            'term': keywords,
            'retmax': max_results,
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
                    paper['api_source'] = 'pubmed'  # 添加这一行
                    papers.append(paper)
                    logging.info(f"PubMed paper found: {paper['title'][:100]}... DOI: {paper.get('doi', 'N/A')}")
            self.fetch_citation_counts(papers, 'pubmed')
            return papers
        else:
            logging.error(f"PubMed搜索失败，状态码: {response.status_code}")
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
            article = root.find(".//PubmedArticle")
            if article is not None:
                doi = (article.findtext(".//ArticleId[@IdType='doi']") or
                       article.findtext(".//ELocationID[@EIdType='doi']") or
                       article.findtext(".//PubmedData/ArticleIdList/ArticleId[@IdType='doi']") or
                       '')
                
                unique_id = self.generate_unique_id(doi)
                
                paper = {
                    'id': str(unique_id),
                    'title': article.findtext(".//ArticleTitle", ''),
                    'abstract': article.findtext(".//AbstractText", ''),
                    'url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    'year': article.findtext(".//PubDate/Year", ''),
                    'pmid': pmid,
                    'type': article.findtext(".//PublicationType", ''),
                    'authors': [author.findtext(".//LastName", '') + ' ' + author.findtext(".//ForeName", '') for author in article.findall(".//Author")],
                    'doi': doi,
                    'api_source': 'pubmed'  # 添加这一行
                }
                logging.info(f"PubMed paper found: {paper['title'][:100]}... DOI: {doi}")
                return paper
        logging.warning(f"Failed to fetch paper details for PMID: {pmid}")
        return None

    def get_pubmed_citation_count(self, pmid):
        # PubMed 不直接提供引用次数，我们可以尝试获取 "Cited by" 文章数量
        cited_by_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi?dbfrom=pubmed&linkname=pubmed_pubmed_citedin&id={pmid}"
        try:
            response = requests.get(cited_by_url)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                cited_by_count = len(root.findall(".//Link"))
                return cited_by_count
            else:
                return 0
        except RequestException:
            return 0

    def search_papers_pmc(self, keywords, start_year=None, end_year=None, max_results=10):
        params = {
            'db': 'pmc',
            'term': keywords,
            'retmax': max_results,
            'sort': 'relevance',
            'retmode': 'xml'
        }
        if start_year and end_year:
            params['term'] += f" AND ({start_year}[PDAT]:{end_year}[PDAT])"

        response = requests.get(self.pmc_search_url, params=params, headers=self.headers)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            id_list = [id_elem.text for id_elem in root.findall('.//IdList/Id')]
            papers = []
            for pmcid in id_list:
                paper = self.fetch_paper_details_pmc(pmcid)
                if paper:
                    # 确保每篇论文都有一个唯一的ID
                    doi = paper.get('doi', '')
                    unique_id = self.generate_unique_id(doi)
                    paper['id'] = str(unique_id)
                    paper['api_source'] = 'pmc'  # 添加这一行
                    
                    papers.append(paper)
                    logging.info(f"PMC paper found: {paper['title'][:100]}... DOI: {paper.get('doi', 'N/A')}")
            self.fetch_citation_counts(papers, 'pmc')
            return papers
        else:
            logging.error(f"PMC搜索失败，状态码: {response.status_code}")
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
            article = root.find('.//article')
            if article is not None:
                doi = article.findtext(".//article-id[@pub-id-type='doi']", '')
                unique_id = self.generate_unique_id(doi)
                paper = {
                    'id': str(unique_id),  # 确保 id 是字符串
                    'title': article.findtext(".//article-title", ''),
                    'abstract': self.get_pmc_abstract(article),
                    'url': f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/",
                    'year': article.findtext(".//pub-date/year", ''),
                    'pmcid': pmcid,
                    'type': article.get('article-type', ''),
                    'authors': [author.findtext(".//surname", '') + ' ' + author.findtext(".//given-names", '') for author in article.findall(".//contrib[@contrib-type='author']")],
                    'doi': doi
                }
                logging.info(f"PMC paper details fetched: {paper['title'][:100]}... DOI: {doi}")
                return paper
        logging.warning(f"Failed to fetch paper details for PMCID: {pmcid}")
        return None

    def get_pmc_citation_count(self, pmcid):
        # PMC 也不直接提供引用次数，我可以尝试获取 "Cited by" 文章数量
        cited_by_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi?dbfrom=pmc&linkname=pmc_pmc_citedby&id={pmcid}"
        try:
            response = requests.get(cited_by_url)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                cited_by_count = len(root.findall(".//Link"))
                return cited_by_count
            else:
                return 0
        except RequestException:
            return 0

    def download_or_get_abstract(self, paper, api_source):
        """
        注意：PDF下载功能仅适用于PubMed和Crossref API。
        对于其他API源（如PMC），将使用其原有的下载逻辑。
        """
        doi = paper.get('doi', '')
        if api_source == 'crossref':
            return self.download_or_get_abstract_crossref(doi, doi, api_source)
        elif api_source == 'pubmed':
            return self.download_or_get_abstract_pubmed(paper['pmid'], doi, api_source)
        elif api_source == 'pmc':
            return self.download_pdf_pmc(paper['pmcid'], doi, api_source)
        else:
            logging.warning(f"Unsupported API source: {api_source}")
            return None

    def download_or_get_abstract_crossref(self, doi, title, api_source):
        url = f"https://doi.org/{doi}"
        try:
            response = self.session.get(url, allow_redirects=True, timeout=30)
            response.raise_for_status()
            if response.status_code == 200:
                pdf_url = self.extract_pdf_url(response.url, response.text)
                if pdf_url:
                    pdf_result = self.download_pdf(pdf_url, doi, api_source)
                    if pdf_result:
                        return pdf_result
                
                # 如果无法直接获取PDF，尝试使用Sci-Hub
                sci_hub_result = self.try_sci_hub(doi, title, api_source)
                if sci_hub_result:
                    return sci_hub_result

                # 如果无法获取PDF，尝试提取摘要
                abstract = self.extract_abstract(response.text)
                if abstract:
                    filename = self.get_valid_filename(doi + '.txt')  # 使用DOI作为文件名
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
        
        # 查找特定的下载按钮或链接（这部分可能需根据不同的出版商站进行定制）
        download_links = soup.find_all('a', text=re.compile(r'Download PDF', re.I))
        if download_links:
            return download_links[0]['href']
        
        return None

    def try_sci_hub(self, doi, title, api_source):
        sci_hub_url = f"{self.sci_hub_url}{doi}"
        try:
            response = self.session.get(sci_hub_url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                pdf_link = soup.find('iframe', id='pdf')
                if pdf_link and pdf_link.get('src'):
                    pdf_url = pdf_link['src']
                    if pdf_url.startswith('//'):
                        pdf_url = 'https:' + pdf_url
                    return self.download_pdf(pdf_url, doi, api_source)
        except Exception as e:
            logging.error(f"Error accessing Sci-Hub: {str(e)}")
        return None

    def extract_pdf_url_from_sci_hub(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 查找嵌入PDF查看器
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

    def download_pdf(self, url, doi, api_source):
        """
        下载PDF文件。
        使用DOI作为文件名的一部分。
        """
        if api_source not in ['pubmed', 'crossref', 'pmc']:
            logging.warning(f"PDF download not supported for API source: {api_source}")
            return None

        try:
            response = self.session.get(url, stream=True)
            if response.status_code == 200 and response.headers.get('Content-Type', '').startswith('application/pdf'):
                filename = self.get_valid_filename(doi) + '.pdf'
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

    def download_or_get_abstract_pubmed(self, pmid, doi, api_source):
        paper = self.fetch_paper_details_pubmed(pmid)
        if paper:
            if paper.get('full_text_link'):
                pdf_result = self.download_pdf(paper['full_text_link'], doi, api_source)
                if pdf_result:
                    return pdf_result
            if paper['abstract']:
                filename = self.get_valid_filename(doi) + '.txt'
                filepath = os.path.join(self.download_dir, filename)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(paper['abstract'])
                logging.info(f"Saved PubMed abstract to {filepath}")
                return {'type': 'abstract', 'path': filepath}
        logging.warning(f"无法获取PubMed摘要或全文: {pmid}")
        return None

    def download_or_get_abstract_pmc(self, pmcid, doi, api_source):
        paper = self.fetch_paper_details_pmc(pmcid)
        if paper and paper['abstract']:
            filename = self.get_valid_filename(doi) + '_abstract.txt'
            filepath = os.path.join(self.download_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(paper['abstract'])
            logging.info(f"Saved PMC abstract to {filepath}")
            return {'type': 'abstract', 'path': filepath}
        else:
            logging.warning(f"无法获取PMC摘要: {pmcid}")
            return None

    def get_valid_filename(self, text):
        """
        将文本转换为有效的文件名。
        """
        return re.sub(r'[^\w\-_\. ]', '_', text)

    def generate_unique_id(self, doi):
        """
        根据DOI生成唯一ID。
        如果DOI不可用，则使用时间戳。
        """
        if doi:
            return self.get_valid_filename(doi)
        else:
            return f"paper_{int(time.time())}"

    def download_pdf_pmc(self, pmcid, doi, api_source):
        url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/pdf/"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            filename = self.get_valid_filename(doi) + '.pdf'
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

    def get_pmc_abstract(self, article):
        # 尝试多种方式获取摘要
        abstract = ''
        abstract_element = article.find(".//abstract")
        if abstract_element is not None:
            abstract = ET.tostring(abstract_element, encoding='unicode', method='text').strip()
        if not abstract:
            abstract = ' '.join([ET.tostring(p, encoding='unicode', method='text').strip() for p in article.findall(".//abstract/p")])
        if not abstract:
            abstract = article.findtext(".//article-meta/abstract", '')
        
        return abstract

    def get_latest_papers_pubmed(self, keywords, max_results=10, weeks=None, months=None):
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        
        if weeks:
            start_date = datetime.now() - timedelta(weeks=weeks)
        elif months:
            start_date = datetime.now() - relativedelta(months=months)
        else:
            start_date = datetime.now() - relativedelta(months=1)  # 默认一个月
        
        date_string = start_date.strftime("%Y/%m/%d")
        
        params = {
            'db': 'pubmed',
            'term': f"({keywords}) AND ({date_string}[PDAT] : 3000[PDAT])",
            'retmax': max_results,
            'sort': 'date',
            'retmode': 'json'
        }
        
        logging.info(f"PubMed search URL: {base_url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}")
        
        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            data = response.json()
            id_list = data['esearchresult']['idlist']
            logging.info(f"PubMed IDs found: {len(id_list)}")
            
            papers = []
            for pmid in id_list:
                paper = self.fetch_paper_details_pubmed(pmid)
                if paper:
                    paper['api_source'] = 'pubmed'  # 确保设置 api_source
                    papers.append(paper)
                    logging.info(f"Added paper: {paper['title']} DOI: {paper.get('doi', 'N/A')}")
            
            logging.info(f"Total papers found: {len(papers)}")
            self.fetch_citation_counts(papers, 'pubmed')
            return papers
        else:
            logging.error(f"Failed to fetch papers from PubMed. Status code: {response.status_code}")
            return []

    def download_or_get_abstract(self, paper, api_source):
        """
        注意：PDF下载功能仅适用于PubMed和Crossref API。
        对于其他API源（如PMC），将使用其原有的下载逻辑。
        """
        doi = paper.get('doi', '')
        if api_source == 'crossref':
            return self.download_or_get_abstract_crossref(doi, doi, api_source)
        elif api_source == 'pubmed':
            return self.download_or_get_abstract_pubmed(paper['pmid'], doi, api_source)
        elif api_source == 'pmc':
            return self.download_pdf_pmc(paper['pmcid'], doi, api_source)
        else:
            logging.warning(f"Unsupported API source: {api_source}")
            return None

        if result and result['type'] != 'error':
            paper['downloaded'] = True
        else:
            paper['downloaded'] = False

        return result



