import requests
import os
import json

class PaperSearcher:
    def __init__(self, download_dir='downloads'):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
        self.base_url = "https://api.crossref.org/works"

    def search_papers(self, keywords, start_year=None, end_year=None):
        params = {
            'query': keywords,
            'rows': 10,  # 限制结果数量
            'sort': 'relevance',
            'order': 'desc'
        }
        if start_year and end_year:
            params['filter'] = f'from-pub-date:{start_year},until-pub-date:{end_year}'

        response = requests.get(self.base_url, params=params)
        if response.status_code == 200:
            data = response.json()
            papers = []
            for item in data['message']['items']:
                paper = {
                    'title': item.get('title', [''])[0],
                    'abstract': item.get('abstract', ''),
                    'url': item.get('URL', ''),
                    'year': item.get('published-print', {}).get('date-parts', [['']])[0][0],
                    'doi': item.get('DOI', '')
                }
                papers.append(paper)
            return papers
        else:
            print(f"搜索失败，状态码: {response.status_code}")
            return []

    def download_or_get_abstract(self, doi, title):
        url = f"https://doi.org/{doi}"
        try:
            response = requests.get(url, allow_redirects=True)
            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '').lower()
                if 'application/pdf' in content_type:
                    filename = self.get_valid_filename(title + '.pdf')
                    filepath = os.path.join(self.download_dir, filename)
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    return {'type': 'pdf', 'path': filepath}
            
            # 如果不是PDF或状态码不是200，尝试获取摘要
            abstract = self.get_abstract(doi)
            if abstract:
                filename = self.get_valid_filename(title + '_abstract.txt')
                filepath = os.path.join(self.download_dir, filename)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(abstract)
                return {'type': 'abstract', 'path': filepath}
            else:
                print(f"无法获取PDF或摘要: {url}")
                return None
        except requests.RequestException as e:
            print(f"下载出错: {e}")
            return None

    def get_abstract(self, doi):
        url = f"https://api.crossref.org/works/{doi}"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                abstract = data['message'].get('abstract')
                if abstract:
                    return abstract
                else:
                    print(f"CrossRef API 中没有摘要: {doi}")
                    return "摘要不可用"
            else:
                print(f"获取摘要失败，状态码: {response.status_code}")
                return "无法获取摘要"
        except requests.RequestException as e:
            print(f"获取摘要出错: {e}")
            return "获取摘要时发生错误"

    def get_valid_filename(self, name):
        return "".join(x for x in name if x.isalnum() or x in [' ', '.', '_']).rstrip()[:50] + '.txt'
